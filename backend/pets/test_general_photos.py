from copy import deepcopy
from urllib.parse import urlencode
from unittest.mock import patch
import uuid
from django.contrib.auth import get_user_model
from django.urls import reverse
from .test_images import PhotoFlowTests,RESULT,upload
from .models import Pet,PhotoCheck,Conversation

class GeneralPhotoTests(PhotoFlowTests):
    def general(self,**extra):
        return self.client.post(reverse('photo_general'),{'request_id':uuid.uuid4(),'purpose':'concern','species':'cat','image':upload(),**extra})

    def test_no_profile_required_and_all_scores_displayed(self):
        self.pet.delete()
        with patch('pets.image_views.predict',return_value=deepcopy(RESULT)) as predict:
            self.assertEqual(self.general().status_code,302)
            self.assertEqual(predict.call_args.args[1],'cat')
        record=PhotoCheck.objects.get()
        self.assertIsNone(record.pet)
        self.assertEqual(record.owner,self.owner)
        self.assertEqual(Pet.objects.count(),0)
        page=self.client.get(reverse('photo_result',args=[record.pk]))
        self.assertContains(page,'data-score="80.0"')
        self.assertContains(page,'Other possibilities — remaining 20.0%')
        self.assertContains(page,'<details class="chat-sources other-possibilities">')
        self.assertContains(page,'Animal type: Cat')
        self.assertContains(page,'15.0%')
        self.assertContains(page,'5.0%')
        self.assertEqual(record.result['ranked'],RESULT['ranked'])

    def test_species_required_and_profile_scope(self):
        other=Pet.objects.create(owner=self.other,name='Other',species='cat')
        with patch('pets.image_views.predict') as predict:
            self.general(species='')
            self.general(species='rabbit')
            self.general(pet=other.pk)
            self.general(pet=self.pet.pk,species='dog')
            predict.assert_not_called()
        self.assertEqual(PhotoCheck.objects.count(),0)
        with patch('pets.image_views.predict',return_value=deepcopy(RESULT)):
            self.general(pet=self.pet.pk)
        self.assertEqual(PhotoCheck.objects.get().pet,self.pet)

    def test_general_photo_and_chat_are_owner_private(self):
        with patch('pets.image_views.predict',return_value=deepcopy(RESULT)):
            self.general()
        record=PhotoCheck.objects.get()
        entry=reverse('new_general_chat')+'?'+urlencode({'photo':str(record.pk),'focus':'Fungal skin condition'})
        with patch('pets.chat_views.gemini_engine.reply') as cloud:
            response=self.client.post(entry,{'start_ack':'yes','backend':'gemini'})
            self.assertEqual(response.status_code,302)
            page=self.client.get(response.url)
            self.assertEqual(page.context['draft_question'], '')
            self.assertNotContains(page,'Do not confirm a subtype or change the image scores')
            cloud.assert_not_called()
        conversation=Conversation.objects.get()
        self.assertIsNone(conversation.pet)
        self.assertEqual(conversation.subject.species,'cat')
        self.client.force_login(self.other)
        for name in ['photo_result','photo_image']:
            self.assertEqual(self.client.get(reverse(name,args=[record.pk])).status_code,404)
        self.assertEqual(self.client.get(entry).status_code,404)
        self.assertEqual(self.client.get(reverse('pet_chat',args=[conversation.pk])).status_code,404)
        self.assertEqual(self.client.post(reverse('chat_send',args=[conversation.pk]),{'question':'hello','request_id':uuid.uuid4()}).status_code,404)

    def test_invalid_focus_and_species_kept_after_photo_deleted(self):
        with patch('pets.image_views.predict',return_value=deepcopy(RESULT)):
            self.general()
        record=PhotoCheck.objects.get()
        entry=reverse('new_general_chat')+'?photo='+str(record.pk)
        self.assertEqual(self.client.get(entry+'&focus=Invented').status_code,400)
        self.client.post(entry,{'start_ack':'yes','backend':'reference'})
        conversation=Conversation.objects.get()
        with self.captureOnCommitCallbacks(execute=True):
            response=self.client.post(reverse('photo_delete',args=[record.pk]),{'confirm':'yes'})
        self.assertRedirects(response,reverse('photo_general'))
        conversation.refresh_from_db()
        self.assertIsNone(conversation.photo_check)
        self.assertEqual(conversation.subject.species,'cat')
        self.assertEqual(self.client.get(reverse('pet_chat',args=[conversation.pk])).status_code,200)
        with patch('pets.chat_views.reply',return_value={'answer':'Reference answer','sources':[],'urgency':'general','model':'reference'}) as engine:
            self.client.post(reverse('chat_send',args=[conversation.pk]),{'question':'How should I brush this cat?','request_id':uuid.uuid4()})
            self.assertEqual(engine.call_args.args[0].species,'cat')
        self.assertRedirects(self.client.post(reverse('chat_delete',args=[conversation.pk]),{'confirm':'yes'}),reverse('new_general_chat'))

    def test_saved_scores_are_unchanged_by_collapsed_alternatives(self):
        for species, score in [('dog', 98.65065813064575), ('cat', 44.54808235168457)]:
            with self.subTest(species=species):
                result = deepcopy(RESULT)
                result['species'] = species
                result['ranked'] = [{'label': 'Eye Infection', 'score': score}, {'label': 'Dental Disease', 'score': 100 - score}]
                record = PhotoCheck.objects.create(owner=self.owner, species=species, result=result)
                with patch('pets.image_views.predict') as predict:
                    page = self.client.get(reverse('photo_result', args=[record.pk]))
                    predict.assert_not_called()
                self.assertContains(page, f'Other possibilities — remaining {100-score:.1f}%')
                self.assertContains(page, f'data-score="{score:.1f}"')
                self.assertContains(page, f'Animal type: {species.title()}')
                record.refresh_from_db()
                self.assertEqual(record.result, result)
