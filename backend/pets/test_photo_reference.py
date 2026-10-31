import uuid
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, SimpleTestCase
from django.urls import reverse
from django.utils import timezone
from .models import Pet, PhotoCheck, Conversation
from . import photo_reference, gemini_engine


class PhotoGuideTests(SimpleTestCase):
    def setUp(self):
        self.pet=SimpleNamespace(species='cat',photo_context={'selected_category':'Ear Mites','observations':''})

    def turn(self,result):
        return SimpleNamespace(state=result['state'],urgency=result['urgency'],question='',answer=result['answer'])

    def test_guided_choices_progress_and_preserve_context(self):
        first=photo_reference.reply(self.pet,'Since yesterday',[])
        self.assertIn('A severe sign is present',first['suggestions'])
        self.assertIn('cotton buds',str(first['state']['care_steps']))
        history=[self.turn(first)]
        for choice in ['None of these severe signs noticed','Started yesterday','One ear affected']:
            self.assertTrue(photo_reference.is_guided_answer(self.pet,choice,history))
            result=photo_reference.reply(self.pet,choice,history)
            history.append(self.turn(result))
        self.assertEqual(result['suggestions'],[])
        self.assertIn('Started yesterday',result['answer'])
        self.assertIn('One ear affected',result['answer'])
        self.assertIn('cannot identify a subtype',result['answer'])

    def test_urgent_choice_and_free_text_interrupt_guide(self):
        first=photo_reference.reply(self.pet,'Ear scratching',[])
        for question in ['A severe sign is present','My cat cannot breathe']:
            result=photo_reference.reply(self.pet,question,[self.turn(first)])
            self.assertEqual(result['urgency'],'urgent')
        self.assertFalse(photo_reference.is_guided_answer(self.pet,'Some unrelated wording',[self.turn(first)]))
        result=photo_reference.reply(self.pet,'Which medicine and dose?',[])
        self.assertIn('cannot choose a medicine',result['answer'])

    def test_no_severe_sign_choice_cannot_clear_prior_urgency(self):
        first=photo_reference.reply(self.pet,'Ear scratching',[])
        prior=self.turn(first)
        prior.urgency='urgent'
        result=photo_reference.reply(self.pet,'None of these severe signs noticed',[prior])
        self.assertEqual(result['urgency'],'urgent')
        self.assertIn('does not reassess',result['answer'])

    def test_photo_topic_cannot_hide_a_new_food_concern(self):
        result=photo_reference.reply(self.pet,'My cat is not eating for five days',[])
        self.assertEqual(result['urgency'],'urgent')
        self.assertNotIn('photo_guide',result['state'])
        first=photo_reference.reply(self.pet,'My cat is not eating',[])
        followup=photo_reference.reply(self.pet,'Five days',[self.turn(first)])
        self.assertEqual(followup['urgency'],'urgent')
        self.assertNotIn('photo_guide',followup['state'])

    def test_other_photo_categories_and_general_chat(self):
        for category in ['Eye Infection','Fungal Infection','Dental Disease']:
            self.pet.photo_context['selected_category']=category
            result=photo_reference.reply(self.pet,'Visible change',[])
            self.assertTrue(result['state'].get('photo_guide'))
            self.assertTrue(result['sources'])
        self.pet.photo_context=None
        result=photo_reference.reply(self.pet,'How should I brush my cat?',[])
        self.assertNotIn('photo_guide',result['state'])


class PhotoGuideIntegrationTests(TestCase):
    def setUp(self):
        cache.clear()
        user=get_user_model().objects.create_user('guide-user')
        self.client.force_login(user)
        pet=Pet.objects.create(owner=user,name='Milo',species='cat')
        photo=PhotoCheck.objects.create(owner=user,pet=pet,species='cat',image='not-a-real-file.jpg',result={'ranked':[{'label':'Ear Mites','score':73}]})
        self.conversation=Conversation.objects.create(owner=user,pet=pet,species='cat',photo_check=photo,photo_focus='Ear Mites',inline_photo=True,answer_mode='gemini',gemini_consent_at=timezone.now())
        self.url=reverse('chat_send',args=[self.conversation.pk])

    def post(self,question,request_id=None):
        return self.client.post(self.url,{'question':question,'request_id':request_id or uuid.uuid4()},HTTP_ACCEPT='application/json')

    def test_outage_then_choice_uses_no_cloud_call_and_new_question_retries(self):
        with patch.object(gemini_engine,'configured',return_value=True),patch.object(gemini_engine,'reply',side_effect=gemini_engine.ChatUnavailable('Safe message',diagnostic='connection_error')) as cloud:
            self.assertEqual(self.post('Head shaking since yesterday').status_code,200)
            self.assertEqual(cloud.call_count,1)
            turn=self.conversation.turns.last()
            self.assertEqual(turn.state['fallback_diagnostic'],'connection_error')
            self.assertIn('Suggested choices continue locally',turn.state['fallback_notice'])
            key=uuid.uuid4()
            self.post('None of these severe signs noticed',key)
            self.post('None of these severe signs noticed',key)
            self.assertEqual(self.conversation.turns.count(),2)
            self.assertEqual(cloud.call_count,1)
            self.post('What else could cause this?')
            self.assertEqual(cloud.call_count,2)
