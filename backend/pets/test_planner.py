from datetime import datetime, timedelta, timezone as utc
import uuid
from unittest.mock import patch
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, Client, SimpleTestCase
from django.urls import reverse
from django.utils import timezone
from .models import Pet, Reminder, PhotoCheck, Conversation, ChatTurn
from .planner_views import report_data, fold_ical
from . import gemini_engine


class PlannerTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = get_user_model().objects.create_user('planner-owner')
        self.other = get_user_model().objects.create_user('planner-other')
        self.pet = Pet.objects.create(owner=self.owner, name='Milo', species='dog', medical_conditions='PRIVATE MEDICAL DETAIL')
        self.other_pet = Pet.objects.create(owner=self.other, name='PRIVATE OTHER PET', species='cat')
        self.client.force_login(self.owner)
        self.now = datetime(2026, 10, 19, 9, 0, tzinfo=utc.utc)
        self.url = reverse('pet_reminders', args=[self.pet.pk])

    def reminder(self, **kwargs):
        return Reminder.objects.create(pet=self.pet, title='Vet appointment', due_at=self.now + timedelta(days=1), **kwargs)

    def test_create_validates_future_time_and_owner_from_url(self):
        with patch('django.utils.timezone.now', return_value=self.now):
            response = self.client.post(self.url, {'title':'Grooming', 'kind':'grooming', 'due_at':'2026-10-20T15:00', 'pet':self.other_pet.pk})
            self.assertEqual(response.status_code, 302)
            saved = Reminder.objects.get()
            self.assertEqual(saved.pet, self.pet)
            self.assertEqual(saved.due_at, datetime(2026, 10, 20, 9, 30, tzinfo=utc.utc))
            response = self.client.post(self.url, {'title':'Old', 'kind':'other', 'due_at':'2026-10-18T15:00'})
            self.assertContains(response, 'Choose a future date and time.')
            self.assertEqual(Reminder.objects.count(), 1)

    def test_all_routes_are_owner_only_and_actions_require_post(self):
        reminder = self.reminder()
        other = Client()
        other.force_login(self.other)
        routes = [self.url, reverse('pet_activity_report',args=[self.pet.pk,'weekly']),
            reverse('pet_activity_report',args=[self.pet.pk,'monthly'])+'?download=text',
            reverse('reminder_calendar',args=[self.pet.pk, reminder.pk])]
        for url in routes:
            self.assertEqual(other.get(url).status_code, 404)
            self.assertEqual(Client().get(url).status_code, 302)
        action = reverse('reminder_action',args=[self.pet.pk,reminder.pk])
        self.assertEqual(other.post(action, {'action':'complete'}).status_code, 404)
        self.assertEqual(self.client.get(action).status_code, 405)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.owner)
        self.assertEqual(csrf.post(action, {'action':'complete'}).status_code, 403)
        self.assertEqual(self.client.get(reverse('pet_activity_report',args=[self.pet.pk,'yearly'])).status_code, 404)

    def test_completion_idempotent_and_delete_requires_confirmation(self):
        reminder = self.reminder()
        action = reverse('reminder_action',args=[self.pet.pk, reminder.pk])
        with patch('django.utils.timezone.now', return_value=self.now):
            self.client.post(action, {'action':'complete'})
        self.client.post(action, {'action':'complete'})
        reminder.refresh_from_db()
        self.assertEqual(reminder.completed_at, self.now)
        self.assertEqual(self.client.get(reverse('reminder_calendar',args=[self.pet.pk,reminder.pk])).status_code,404)
        self.assertEqual(self.client.post(action,{'action':'delete'}).status_code,400)
        self.assertTrue(Reminder.objects.filter(pk=reminder.pk).exists())
        self.client.post(action,{'action':'delete','confirm':'yes'})
        self.assertFalse(Reminder.objects.filter(pk=reminder.pk).exists())

    def test_calendar_utc_time_private_fields_escaping_and_stable_uid(self):
        reminder = self.reminder(notes='DO NOT EXPORT PRIVATE NOTES')
        reminder.title = 'Check; ears, café\\skin\nBEGIN:VEVENT'
        reminder.save()
        url = reverse('reminder_calendar',args=[self.pet.pk,reminder.pk])
        with patch('django.utils.timezone.now', return_value=self.now):
            response = self.client.get(url)
            again = self.client.get(url)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.content,again.content)
        text=response.content.decode()
        self.assertIn('DTSTART:20261020T090000Z',text)
        self.assertIn('TRIGGER:-PT30M',text)
        self.assertIn('CLASS:PRIVATE',text)
        self.assertEqual(text.count('\r\nBEGIN:VEVENT\r\n'),1)
        self.assertIn('Check\\; ears\\, café\\\\skin\\nBEGIN:VEVENT',text)
        self.assertNotIn('PRIVATE MEDICAL DETAIL',text)
        self.assertNotIn('DO NOT EXPORT',text)
        self.assertIn('no-store',response['Cache-Control'])
        self.assertTrue(all(len(line)<=75 for line in response.content.split(b'\r\n')))

    def test_calendar_rejects_past_due_and_wrong_pet(self):
        reminder = self.reminder()
        with patch('django.utils.timezone.now',return_value=self.now+timedelta(days=2)):
            self.assertEqual(self.client.get(reverse('reminder_calendar',args=[self.pet.pk,reminder.pk])).status_code,400)
        own_second = Pet.objects.create(owner=self.owner,name='Luna',species='cat')
        self.assertEqual(self.client.get(reverse('reminder_calendar',args=[own_second.pk,reminder.pk])).status_code,404)

    def test_report_boundaries_include_followups_not_just_new_chats(self):
        conversation=Conversation.objects.create(pet=self.pet,owner=self.owner,species='dog')
        start=datetime(2026,10,12,18,30,tzinfo=utc.utc)  # Oct 13 midnight IST: weekly start
        questions=[('Before window',start-timedelta(microseconds=1)),('At window start',start),('Today',self.now),('Future',self.now+timedelta(seconds=1))]
        for question, stamp in questions:
            turn=ChatTurn.objects.create(conversation=conversation,request_id=uuid.uuid4(),question=question,status='complete')
            ChatTurn.objects.filter(pk=turn.pk).update(created_at=stamp)
        foreign=Conversation.objects.create(pet=self.other_pet,owner=self.other,species='cat')
        ChatTurn.objects.create(conversation=foreign,request_id=uuid.uuid4(),question='PRIVATE FOREIGN QUESTION',status='complete')
        data=report_data(self.pet,7,self.now)
        self.assertEqual(data['counts']['turns'],2)
        self.assertEqual({t.question for t in data['turns']},{'At window start','Today'})
        self.assertEqual(report_data(self.pet,30,self.now)['counts']['turns'],3)
        with patch('django.utils.timezone.now',return_value=self.now), patch.object(gemini_engine,'reply') as cloud:
            response=self.client.get(reverse('pet_activity_report',args=[self.pet.pk,'weekly']))
            self.assertContains(response,'At window start')
            self.assertNotContains(response,'Before window')
            self.assertNotContains(response,'PRIVATE FOREIGN')
            text=self.client.get(reverse('pet_activity_report',args=[self.pet.pk,'weekly'])+'?download=text')
            self.assertContains(text,'not a diagnosis or a measure of health improvement')
            self.assertNotContains(text,'PRIVATE FOREIGN')
            cloud.assert_not_called()

    def test_report_completion_window_distinct_from_due_window(self):
        reminder=self.reminder(completed_at=self.now)
        data=report_data(self.pet,7,self.now)
        self.assertEqual(data['counts']['due'],0)
        self.assertEqual(data['counts']['completed'],1)

    def test_hub_reminders_and_escaping_empty_reports(self):
        self.reminder()
        response=self.client.get(reverse('pet_care_hub',args=[self.pet.pk]))
        self.assertContains(response,'Weekly report')
        self.assertContains(response,'Vet appointment')
        response=self.client.get(reverse('pet_activity_report',args=[self.pet.pk,'weekly']))
        self.assertContains(response,'No photo checks recorded')
        self.assertContains(response,'No records does not mean no symptoms')
        reminder=self.reminder()
        reminder.title='<script>alert(1)</script>'
        reminder.save()
        response=self.client.get(self.url)
        self.assertNotContains(response,'<script>alert(1)</script>')
        self.assertContains(response,'&lt;script&gt;')


class CalendarFormatTests(SimpleTestCase):
    def test_folding_unicode_preserves_content(self):
        line='SUMMARY:'+('🐈é'*90)
        folded=fold_ical(line)
        self.assertEqual(folded.replace('\r\n ',''),line)
        self.assertTrue(all(len(row.encode())<=75 for row in folded.split('\r\n')))

    def test_provider_diagnostics_are_safe_and_distinct(self):
        errors=[(HTTPError('url',429,'secret',{},None),'usage_limit'),
                (HTTPError('url',403,'secret',{},None),'access_denied'),
                (URLError('secret'),'connection_error')]
        for error, diagnostic in errors:
            with patch.object(gemini_engine,'configuration',return_value=('not-a-real-key',True)),patch.object(gemini_engine.urllib.request,'build_opener') as opener:
                opener.return_value.open.side_effect=error
                with self.assertRaises(gemini_engine.ChatUnavailable) as caught:
                    gemini_engine.reply(SimpleNamespace(species='dog',age_years=2),'hello',[])
                self.assertEqual(caught.exception.diagnostic,diagnostic)
                self.assertNotIn('secret',str(caught.exception))
