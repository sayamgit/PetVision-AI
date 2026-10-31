import json
import uuid
from types import SimpleNamespace
from django.test import TestCase, SimpleTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import Pet, Conversation, ChatTurn, PhotoCheck
from .care_ui import vet_contact
from . import gemini_engine, reference_engine
from .test_gemini import provider_result, RESULT

class CareNavigationTests(TestCase):
    def setUp(self):
        self.owner=get_user_model().objects.create_user('care-ui-owner')
        self.other=get_user_model().objects.create_user('care-ui-other')
        self.pet=Pet.objects.create(owner=self.owner,name='Milo',species='dog',vet_name='Saved Clinic',vet_phone='+91 98765 43210')
        self.private=Pet.objects.create(owner=self.other,name='Other owner pet',species='cat',vet_phone='1234567890')
        self.client.force_login(self.owner)

    def test_centre_and_pet_hub_owner_scoping_and_actions(self):
        general=Conversation.objects.create(owner=self.owner,species='dog',title='General conversation')
        own=Conversation.objects.create(owner=self.owner,pet=self.pet,title='Milo conversation')
        Conversation.objects.create(owner=self.other,pet=self.private,title='Other private conversation')
        page=self.client.get(reverse('care_home'))
        self.assertContains(page,'Help another animal')
        self.assertContains(page,'General conversation')
        self.assertNotContains(page,'Other owner pet')
        self.assertNotContains(page,'Milo conversation')
        self.assertNotContains(page,'Other private conversation')
        page=self.client.get(reverse('pet_care_hub',args=[self.pet.pk]))
        for name in ['photo_start','new_pet_chat']:
            self.assertContains(page,reverse(name,args=[self.pet.pk]))
        self.assertContains(page,'Milo conversation')
        self.assertContains(page,'tel:+919876543210')
        self.assertNotContains(page,'General conversation')
        self.assertEqual(self.client.get(reverse('pet_care_hub',args=[self.private.pk])).status_code,404)
        self.assertIsNone(vet_contact(self.private,self.owner))
        self.pet.vet_phone='javascript:alert(1)'
        self.assertIsNone(vet_contact(self.pet,self.owner))
        self.client.logout()
        self.assertEqual(self.client.get(reverse('pet_care_hub',args=[self.pet.pk])).status_code,302)

    def test_urgency_contacts_and_general_animal_do_not_borrow_vet(self):
        for pet in [self.pet,None]:
            chat=Conversation.objects.create(owner=self.owner,pet=pet,species='dog',answer_mode='reference')
            turn=ChatTurn.objects.create(conversation=chat,request_id=uuid.uuid4(),question='Collapsed',answer='Call veterinary care.',status='complete',urgency='urgent',state={'care_steps':{'avoid':['Do not give unprescribed medicine.']}})
            page=self.client.get(reverse('pet_chat',args=[chat.pk]))
            self.assertContains(page,'Seek emergency veterinary care now')
            self.assertContains(page,'What to avoid')
            if pet:self.assertContains(page,'tel:+919876543210')
            else:self.assertNotContains(page,'tel:')
            serialized=json.dumps(gemini_engine.payload_for(chat.subject,'hello',[]))
            self.assertNotIn('98765',serialized)
            self.assertNotIn('Saved Clinic',serialized)
            turn.urgency='general';turn.save()
            page=self.client.get(reverse('pet_chat',args=[chat.pk]))
            self.assertNotContains(page,'Seek emergency veterinary care now')
            self.assertNotContains(page,'Veterinary assessment recommended')
            turn.urgency='contact_vet';turn.save()
            page=self.client.get(reverse('pet_chat',args=[chat.pk]))
            self.assertContains(page,'Veterinary assessment recommended')
            self.assertNotContains(page,'Seek emergency veterinary care now')

    def test_inline_photo_uses_only_its_linked_vet_and_public_qr_unchanged(self):
        for pet in [self.pet,None]:
            photo=PhotoCheck.objects.create(owner=self.owner,pet=pet,species='dog',result={'ranked':[{'label':'Eye Infection','score':70.0}]})
            chat=Conversation.objects.create(owner=self.owner,pet=pet,species='dog',photo_check=photo,photo_focus='Eye Infection',inline_photo=True,answer_mode='reference')
            ChatTurn.objects.create(conversation=chat,request_id=uuid.uuid4(),question='Eye pain',answer='Veterinary care needed',urgency='contact_vet',status='complete')
            page=self.client.get(reverse('photo_result',args=[photo.pk])+'?focus=Eye%20Infection')
            if pet:self.assertContains(page,'tel:+919876543210')
            else:self.assertNotContains(page,'tel:')
        public=self.client.get(reverse('public_pet',args=[self.pet.public_token]))
        self.assertNotContains(public,'Saved Clinic')

class PracticalGuidanceTests(SimpleTestCase):
    def test_structured_steps_require_valid_citation_and_reject_unsafe_output(self):
        dog=SimpleNamespace(species='dog')
        result={**RESULT,'answer':'Prevent further licking while arranging care.','source_ids':['petmd-hotspots','vca-cone'],'do_now':['Use a properly fitted cone if the dog is licking the irritated area.'],'avoid':[],'watch_for':['Seek prompt care if the area grows.']}
        parsed=gemini_engine.parse_response(provider_result(result),dog)
        self.assertTrue(parsed['state']['care_steps']['do_now'])
        for changed in [{'source_ids':[]},{'do_now':['Give 50 mg']},{'avoid':['See https://fake.example']},{'watch_for':'bad'},{'source_ids':['cat-eyes']}]:
            with self.assertRaises(ValueError):gemini_engine.parse_response(provider_result({**result,**changed}),dog)
        with self.assertRaises(ValueError):gemini_engine.parse_response(provider_result(result),SimpleNamespace(species='cat'))

    def test_reference_backup_has_conditional_skin_help_without_stale_steps(self):
        pet=SimpleNamespace(species='dog')
        answer=reference_engine.reply(pet,'My dog is licking itchy skin',[])
        self.assertIn('care_steps',answer['state'])
        self.assertTrue(answer['state']['care_steps']['do_now'])
        history=[SimpleNamespace(state=answer['state'])]
        urgent=reference_engine.reply(pet,'My dog collapsed',history)
        self.assertEqual(urgent['urgency'],'urgent')
        self.assertNotIn('care_steps',urgent['state'])
