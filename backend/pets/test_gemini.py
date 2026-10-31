import json
import uuid
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from . import gemini_engine as engine
from .models import Pet, Conversation

RESULT={'answer':'Hair fall can describe different patterns. Is it patchy, and is there itching? The earlier report of no food for five days needs immediate veterinary attention.','source_ids':['skin','visit'],'urgency':'urgent','suggestions':['Patchy with itching']}

def provider_result(result=RESULT,finish='STOP'):
    return {'candidates':[{'finishReason':finish,'content':{'parts':[{'text':json.dumps(result)}]}}]}

class GeminiEngineTests(SimpleTestCase):
    def setUp(self):
        self.pet=SimpleNamespace(species='cat',age_years=3,name='Private name',owner_phone='1234567890',medical_conditions='private diagnosis')

    def test_hair_fall_does_not_need_keyword_match_and_keeps_prior_context(self):
        history=[SimpleNamespace(question='My pet is not eating food',answer='How long?'),SimpleNamespace(question='last 5 days',answer='Contact a vet now.')]
        payload=engine.payload_for(self.pet,'there is so much hair fall',history)
        self.assertEqual(payload['contents'][-1]['parts'][0]['text'],'there is so much hair fall')
        self.assertIn('last 5 days',json.dumps(payload))
        self.assertIn('Itching and skin changes',json.dumps(payload))
        self.assertNotIn('Private name',json.dumps(payload))
        self.assertNotIn('private diagnosis',json.dumps(payload))
        self.assertNotIn('tools',payload)

    def test_recent_history_bounded_and_obvious_contact_details_removed(self):
        history=[SimpleNamespace(question=f'question {i}',answer='answer') for i in range(9)]
        payload=engine.payload_for(self.pet,'Email owner@example.com or call +91 98765 43210',history)
        serialized=json.dumps(payload)
        self.assertEqual(len(payload['contents']),13)
        self.assertNotIn('question 0',serialized)
        self.assertNotIn('owner@example.com',serialized)
        self.assertNotIn('98765',serialized)

    def test_request_headers_fixed_endpoint_and_schema(self):
        with patch.object(engine,'configuration',return_value=('fake-secret-key',True)),patch.object(engine.urllib.request,'build_opener') as mocked:
            mocked.return_value.open.return_value.__enter__.return_value.read.return_value=json.dumps(provider_result()).encode()
            answer=engine.reply(self.pet,'hair fall',[])
            req=mocked.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url,engine.ENDPOINT)
            self.assertNotIn('fake-secret',req.full_url)
            self.assertEqual(req.get_header('X-goog-api-key'),'fake-secret-key')
            self.assertEqual(mocked.return_value.open.call_count,1)
            self.assertEqual(answer['model'],engine.MODEL)
            self.assertEqual(answer['sources'][0]['id'],'skin')

    def test_missing_key_or_free_tier_confirmation_never_calls_network(self):
        for config in [('',True),('fake-key',False)]:
            with patch.object(engine,'configuration',return_value=config),patch.object(engine.urllib.request,'build_opener') as mocked:
                with self.assertRaises(engine.ChatUnavailable): engine.reply(self.pet,'hello',[])
                mocked.assert_not_called()

    def test_errors_no_retry_no_secret_or_provider_body_leak(self):
        for error in [HTTPError(engine.ENDPOINT,429,'raw secret',{},None),HTTPError(engine.ENDPOINT,403,'raw secret',{},None),URLError('raw secret')]:
            with patch.object(engine,'configuration',return_value=('fake-key',True)),patch.object(engine.urllib.request,'build_opener') as mocked:
                mocked.return_value.open.side_effect=error
                with self.assertRaises(engine.ChatUnavailable) as caught: engine.reply(self.pet,'hair fall',[])
                self.assertNotIn('raw secret',str(caught.exception))
                self.assertEqual(caught.exception.code, 'usage_limit' if getattr(error,'code',None)==429 else 'unavailable')
                self.assertEqual(mocked.return_value.open.call_count,1)

    def test_output_validation_rejects_fabricated_sources_links_doses_and_truncation(self):
        for raw in [provider_result({**RESULT,'source_ids':['invented']}),provider_result({**RESULT,'answer':'Give 50 mg'}),provider_result({**RESULT,'answer':'See https://fake.example'}),provider_result(finish='MAX_TOKENS'),{},provider_result({**RESULT,'suggestions':'bad'})]:
            with self.assertRaises((ValueError,KeyError)):
                engine.parse_response(raw,self.pet)

    def test_schema_prevents_excess_steps_and_unsupported_source_ids(self):
        schema=engine.payload_for(self.pet,'hello',[])['generationConfig']['responseSchema']
        for field in ('suggestions','do_now','avoid','watch_for'):
            self.assertEqual(schema['properties'][field]['maxItems'],3)
        self.assertIn('skin',schema['properties']['source_ids']['items']['enum'])
        self.assertNotIn('enum',engine.SCHEMA['properties']['source_ids']['items'])

    def test_distinct_failure_notices_do_not_leak_raw_provider_errors(self):
        for diagnostic in ('truncated_response','blocked_response','connection_error','provider_error','unusable_response'):
            error=engine.ChatUnavailable('private provider details',diagnostic=diagnostic)
            notice=engine.failure_notice(error)
            self.assertNotIn('private provider details',notice)
            self.assertNotIn('quota',notice)
        with patch.object(engine,'configuration',return_value=('fake-key',True)),patch.object(engine.urllib.request,'build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value=json.dumps(provider_result(finish='MAX_TOKENS')).encode()
            with self.assertRaises(engine.ChatUnavailable) as caught:engine.reply(self.pet,'hello',[])
            self.assertEqual(caught.exception.diagnostic,'truncated_response')

    def test_cross_species_reference_rejected(self):
        with self.assertRaises(ValueError):
            engine.parse_response(provider_result({**RESULT,'source_ids':['catfood']}),SimpleNamespace(species='dog'))

@patch('pets.chat_views.gemini_engine.configured',return_value=True)
class GeminiViewTests(TestCase):
    def setUp(self):
        cache.clear()
        user=get_user_model().objects.create_user('gemini-owner')
        self.pet=Pet.objects.create(owner=user,name='Miso',species='cat')
        self.conversation=Conversation.objects.create(pet=self.pet)
        self.client.force_login(user)

    def start(self, mode='gemini'):
        return self.client.post(reverse('new_pet_chat',args=[self.pet.pk])+'?resume='+str(self.conversation.pk), {'start_ack':'yes','backend':mode})

    def send(self,**extra):
        if extra.pop('cloud_consent',None) == 'yes':
            self.start()
        return self.client.post(reverse('chat_send',args=[self.conversation.pk]),{'question':'there is so much hair fall','request_id':uuid.uuid4(),**extra},HTTP_ACCEPT='application/json')

    def test_consent_required_before_any_cloud_call(self,status):
        with patch('pets.chat_views.gemini_engine.reply') as cloud:
            self.assertEqual(self.send().status_code,400)
            cloud.assert_not_called()
        self.assertEqual(self.conversation.turns.count(),0)

    def test_consent_and_real_provider_path_save_answer(self,status):
        result=engine.parse_response(provider_result(),self.pet)
        with patch('pets.chat_views.gemini_engine.reply',return_value=result) as cloud:
            self.assertEqual(self.send(cloud_consent='yes').status_code,200)
            self.assertEqual(self.send().status_code,200)
            self.assertEqual(cloud.call_count,2)
        self.conversation.refresh_from_db()
        self.assertIsNotNone(self.conversation.gemini_consent_at)
        self.assertEqual(self.conversation.turns.last().model,engine.MODEL)
        page=self.client.get(reverse('pet_chat',args=[self.conversation.pk]))
        self.assertContains(page,'GEMINI ANSWER')

    def test_quota_failure_has_labeled_reference_fallback(self,status):
        with patch('pets.chat_views.gemini_engine.reply',side_effect=engine.ChatUnavailable('Usage limit reached', code='usage_limit')) as cloud:
            self.send(cloud_consent='yes')
            self.assertEqual(cloud.call_count,1)
        turn=self.conversation.turns.last()
        self.assertEqual(turn.status,'complete')
        self.assertNotEqual(turn.model,engine.MODEL)
        self.assertEqual(turn.state['fallback_reason'],'usage_limit')
        page=self.client.get(reverse('pet_chat',args=[self.conversation.pk]))
        self.assertContains(page,'free-tier usage limit has been reached')
        self.assertContains(page,'REFERENCE GUIDE')
        with patch('pets.chat_views.gemini_engine.reply',return_value=engine.parse_response(provider_result(),self.pet)) as cloud:
            self.send()
            cloud.assert_called_once()
        self.assertNotIn('fallback_notice',self.conversation.turns.last().state)

    def test_explicit_local_mode_never_calls_gemini(self,status):
        with patch('pets.chat_views.gemini_engine.reply') as cloud:
            self.assertEqual(self.send(backend='reference').status_code,200)
            cloud.assert_not_called()
        self.conversation.refresh_from_db()
        self.assertIsNone(self.conversation.gemini_consent_at)

    def test_missing_configuration_and_invalid_mode(self,status):
        self.assertEqual(self.send(backend='unknown').status_code,400)
        self.start()
        with patch('pets.chat_views.gemini_engine.configured',return_value=False):
            with patch('pets.chat_views.gemini_engine.reply') as cloud:
                self.assertEqual(self.send().status_code,200)
                cloud.assert_not_called()
        self.assertEqual(self.conversation.turns.count(),1)
        self.assertEqual(self.conversation.turns.last().state['fallback_reason'],'unavailable')

    def test_fallback_keeps_urgent_context_and_does_not_label_outage_as_quota(self,status):
        with patch('pets.chat_views.gemini_engine.reply',return_value=engine.parse_response(provider_result(),self.pet)):
            self.send(cloud_consent='yes')
        with patch('pets.chat_views.gemini_engine.reply',side_effect=engine.ChatUnavailable('Unavailable')):
            self.send(question='How should I brush my cat?')
        turn=self.conversation.turns.last()
        self.assertEqual(turn.urgency,'urgent')
        self.assertIn('does not reassess',turn.answer)
        self.assertNotIn('quota',turn.state['fallback_notice'])
        self.send(backend='reference',question='How should I brush my cat?')
        self.assertNotIn('fallback_notice',self.conversation.turns.last().state)

    def test_explanation_only_on_start_page_and_preference_persists(self,status):
        entry=reverse('new_pet_chat',args=[self.pet.pk])
        page=self.client.get(entry)
        self.assertContains(page,'How answers work')
        self.assertNotContains(page,'Gemini is configured')
        self.assertNotContains(page,'name="cloud_consent"')
        self.assertEqual(self.client.post(entry,{'start_ack':'yes','backend':'reference'}).status_code,302)
        self.conversation=Conversation.objects.order_by('-created_at').first()
        with patch('pets.chat_views.gemini_engine.reply') as cloud:
            self.send()
            cloud.assert_not_called()
        self.assertEqual(self.conversation.answer_mode,'reference')
        page=self.client.get(reverse('pet_chat',args=[self.conversation.pk]))
        for text in ['How answers work','name="cloud_consent"','Reply preference','Conversation privacy','Delete conversation','Browse the reference topics']:
            self.assertNotContains(page,text)
        self.assertContains(page,'Your message')

    def test_legacy_chat_returns_to_intro_without_losing_history(self,status):
        self.conversation.turns.create(request_id=uuid.uuid4(),question='Existing question',answer='Existing reply',status='complete')
        url=reverse('pet_chat',args=[self.conversation.pk])
        response=self.client.get(url)
        self.assertRedirects(response,reverse('new_pet_chat',args=[self.pet.pk])+'?resume='+str(self.conversation.pk))
        with patch('pets.chat_views.gemini_engine.reply') as cloud:
            self.start()
            cloud.assert_not_called()
        self.assertContains(self.client.get(url),'Existing reply')
        self.conversation.refresh_from_db()
        self.assertIsNotNone(self.conversation.gemini_consent_at)

    def test_intro_requires_ack_and_cannot_update_another_owners_chat(self,status):
        entry=reverse('new_pet_chat',args=[self.pet.pk])
        self.assertEqual(self.client.post(entry,{}).status_code,400)
        self.assertEqual(self.client.get(entry+'?resume=bad').status_code,400)
        other=get_user_model().objects.create_user('other-intro-owner')
        otherpet=Pet.objects.create(owner=other,name='Other',species='cat')
        otherchat=Conversation.objects.create(pet=otherpet)
        self.assertEqual(self.client.post(entry+'?resume='+str(otherchat.pk),{'start_ack':'yes'}).status_code,404)

    def test_start_records_ack_without_api_call_and_local_switch_sticks(self,status):
        with patch('pets.chat_views.gemini_engine.reply') as cloud:
            self.start()
            cloud.assert_not_called()
        self.conversation.refresh_from_db()
        self.assertIsNotNone(self.conversation.gemini_consent_at)
        self.start('reference')
        with patch('pets.chat_views.gemini_engine.reply') as cloud:
            self.send()
            cloud.assert_not_called()
