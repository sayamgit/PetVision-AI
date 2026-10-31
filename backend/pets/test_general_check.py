from unittest.mock import patch
from django.urls import reverse
from .test_images import PhotoFlowTests
from .models import PhotoCheck, Conversation

class GeneralCheckTests(PhotoFlowTests):
    def test_general_never_predicts_and_private_result_has_no_scores(self):
        with patch('pets.image_views.predict') as predict:
            response = self.send(purpose='general')
            self.assertEqual(response.status_code,302)
            predict.assert_not_called()
        record=PhotoCheck.objects.get()
        self.assertEqual(record.result['ranked'],[])
        self.assertEqual(record.display_label,'General pet check')
        page=self.client.get(response.url)
        self.assertContains(page,'No disease prediction performed')
        self.assertNotContains(page,'data-score=')
        self.assertNotContains(page,'Scabies')
        self.assertEqual(self.client.get(response.url+'?focus=Scabies').status_code,400)
        self.assertEqual(self.client.post(reverse('photo_followup',args=[record.pk]),{'focus':'Scabies','start_ack':'yes'}).status_code,400)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(response.url).status_code,404)
        self.assertEqual(self.client.get(reverse('photo_image',args=[record.pk])).status_code,404)

    def test_general_chat_preserves_observations_without_invented_category(self):
        self.send(purpose='general')
        record=PhotoCheck.objects.get()
        url=reverse('new_pet_chat',args=[self.pet.pk])+'?photo='+str(record.pk)
        response=self.client.post(url,{'backend':'reference','start_ack':'yes'})
        self.assertEqual(response.status_code,302)
        chat=Conversation.objects.get()
        self.assertIn('no image analysis',chat.subject.photo_context['selected_category'])
        self.assertEqual(chat.subject.photo_context['observations'],'Itching for two days')
        self.assertEqual(self.client.get(response.url).status_code,200)

    def test_missing_or_invalid_purpose_does_not_run_model(self):
        with patch('pets.image_views.predict') as predict:
            for purpose in ('','healthy','unsupported'):
                response=self.send(purpose=purpose)
                self.assertEqual(response.status_code,200)
                self.assertIn('purpose',response.context['form'].errors)
            predict.assert_not_called()
        self.assertFalse(PhotoCheck.objects.exists())
