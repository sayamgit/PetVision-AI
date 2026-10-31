import json
import uuid
from copy import deepcopy
from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from .models import PhotoCheck, Conversation, ChatTurn
from .test_images import RESULT
from . import gemini_engine

class InlinePhotoTests(TestCase):
    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user=get_user_model().objects.create_user('inline-owner')
        self.other=get_user_model().objects.create_user('inline-other')
        self.client.force_login(self.user)
        self.result=deepcopy(RESULT)
        self.result['ranked']=[{'label':'Eye Infection','score':98.7},{'label':'Dental Disease','score':1.3}]
        self.photo=PhotoCheck.objects.create(owner=self.user,species='cat',result=self.result, observations='Started yesterday')
        self.url=reverse('photo_followup',args=[self.photo.pk])
        self.page=reverse('photo_result',args=[self.photo.pk])+'?focus=Eye%20Infection'

    def send(self, **extra):
        return self.client.post(self.url,{'focus':'Eye Infection','start_ack':'yes','backend':'gemini','request_id':uuid.uuid4(),'question':'The left eye is red since yesterday.',**extra},HTTP_ACCEPT='application/json')

    @patch('pets.chat_views.gemini_engine.configured',return_value=True)
    def test_inline_context_and_history_without_synthetic_owner_prompt(self, configured):
        old=Conversation.objects.create(owner=self.user,species='cat',title='Existing chat')
        result=dict(answer='Is one eye affected or both?', sources=[], urgency='uncertain', model=gemini_engine.MODEL)
        with patch('pets.chat_views.gemini_engine.reply',return_value=result) as cloud:
            page=self.client.get(self.page)
            self.assertContains(page,'What changes have you noticed in the eye')
            self.assertEqual(Conversation.objects.count(),1)
            cloud.assert_not_called()
            key=uuid.uuid4()
            response=self.send(request_id=key)
            self.assertEqual(response.status_code,200)
            self.assertIn('/photos/',response.json()['url'])
            conversation=Conversation.objects.get(inline_photo=True)
            subject,question,history=cloud.call_args.args
            self.assertEqual(question,'The left eye is red since yesterday.')
            self.assertEqual(subject.photo_context,{'selected_category':'Eye Infection','observations':'Started yesterday'})
            payload=gemini_engine.payload_for(subject,question,history)
            context=json.loads(payload['systemInstruction']['parts'][0]['text'].split('REFERENCE DATA:\n')[1])
            self.assertNotIn('98.7',json.dumps(context))
            self.assertNotIn('Dental Disease',json.dumps(context))
            self.assertEqual(payload['contents'][-1]['parts'][0]['text'],question)
            self.send(request_id=key)
            self.assertEqual(cloud.call_count,1)
            self.send(question='Only the left eye.')
            self.assertEqual(len(cloud.call_args.args[2]),1)
            self.assertEqual(conversation.turns.count(),2)
            self.assertEqual(old.turns.count(),0)
        page=self.client.get(self.page)
        self.assertContains(page,'Is one eye affected or both?')
        self.assertNotContains(page,'I want to discuss the Eye Infection match')
        self.assertNotContains(page,'name="start_ack" value="yes" type="checkbox"')
        self.assertEqual(self.client.get(reverse('pet_chat',args=[conversation.pk])).status_code,302)
        self.photo.refresh_from_db()
        self.assertEqual(self.photo.result,self.result)

    def test_invalid_focus_consent_and_cross_owner_blocked(self):
        with patch('pets.chat_views.gemini_engine.reply') as cloud:
            self.assertEqual(self.send(focus='Invented disease').status_code,400)
            self.assertEqual(self.send(start_ack='').status_code,400)
            self.assertEqual(self.send(question='').status_code,400)
            self.assertEqual(self.client.get(self.page.replace('Eye%20Infection','Invalid')).status_code,400)
            self.client.force_login(self.other)
            self.assertEqual(self.send().status_code,404)
            self.assertEqual(self.client.get(self.page).status_code,404)
            self.assertEqual(Conversation.objects.count(),0)
            cloud.assert_not_called()

    @patch('pets.chat_views.gemini_engine.configured',return_value=True)
    def test_quota_notice_local_mode_and_focus_isolation(self, configured):
        with patch('pets.chat_views.gemini_engine.reply',side_effect=gemini_engine.ChatUnavailable('Limit','usage_limit')) as cloud:
            self.assertEqual(self.send(question='Since yesterday').status_code,200)
            self.assertContains(self.client.get(self.page),'free-tier usage limit has been reached')
            turn=ChatTurn.objects.get()
            self.assertIn('conjunctivitis',turn.answer.lower())
            self.assertEqual(turn.model,'guided-photo-1')
            self.assertEqual(turn.state['photo_guide']['topic'],'eyes')
            self.send(focus='Dental Disease', backend='reference', question='Bad breath')
            self.assertEqual(cloud.call_count,1)
        self.assertEqual(Conversation.objects.filter(inline_photo=True).count(),2)
        self.assertNotContains(self.client.get(self.page),'Bad breath')

    def test_non_javascript_send_stays_on_photo_and_emergency_not_delayed(self):
        response=self.client.post(self.url,{'focus':'Eye Infection','start_ack':'yes','backend':'reference','request_id':uuid.uuid4(),'question':'My cat collapsed'})
        self.assertEqual(response.status_code,302)
        self.assertIn('/photos/',response.url)
        self.assertIn('#chat-end',response.url)
        turn=ChatTurn.objects.get()
        self.assertEqual(turn.urgency,'urgent')
        self.assertContains(self.client.get(self.page),'Seek emergency veterinary care now')
