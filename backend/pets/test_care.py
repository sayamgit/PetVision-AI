import uuid
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from .care_content import assess, SOURCES
from .models import Pet, Assessment


class ContentTests(SimpleTestCase):
    def draft(self, topic='sleep', safety='no', concern='Sleeping ten hours'):
        return {'topic': topic, 'safety': safety, 'concern': concern}

    def test_emergency_overrides_every_topic(self):
        for topic in ('sleep', 'appetite', 'skin', 'other'):
            for safety in ('yes', 'unsure'):
                result = assess(self.draft(topic, safety), {})
                self.assertEqual(result['level'], 'urgent')
                self.assertTrue(result['sources'])

    def test_severe_followups_override_other_answers(self):
        for answers in ({'activity': 'extreme'}, {'intake': 'none24'}):
            self.assertEqual(assess(self.draft(), answers)['level'], 'urgent')

    def test_sleep_duration_does_not_become_healthy_diagnosis(self):
        result = assess(self.draft(), {'activity': 'usual', 'intake': 'usual', 'changed': 'no', 'duration': 'today'})
        self.assertEqual(result['level'], 'limited')
        self.assertIn('not enough', result['reason'])
        self.assertNotIn('confidence', result)

    def test_unknown_and_unsupported_never_get_clearance(self):
        self.assertEqual(assess(self.draft(), {'duration': 'unknown'})['level'], 'limited')
        self.assertEqual(assess(self.draft('other'), {})['rule_ids'], ['unsupported-topic'])
        self.assertEqual(assess(self.draft(concern='What dose should I give?'), {})['rule_ids'], ['medication-boundary'])

    def test_keywords_are_cautious_not_a_negation_parser(self):
        result = assess(self.draft(concern='There were no seizures'), {})
        self.assertEqual(result['level'], 'urgent')
        self.assertIn('negated', result['reason'])

    def test_skin_guidance_has_primary_references(self):
        result = assess(self.draft('skin'), {'skin_signs': 'yes'})
        self.assertEqual(result['level'], 'contact')
        self.assertIn(SOURCES['skin'], result['sources'])


class CareFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user('care-owner', password='Test-paws-815!')
        self.other = get_user_model().objects.create_user('care-other', password='Test-paws-815!')
        self.pet = Pet.objects.create(owner=self.user, name='Miso', species='cat', allergies='Private allergy')
        self.client.force_login(self.user)

    def start(self, **overrides):
        data = {'concern': 'Sleeping for ten hours', 'topic': 'sleep', 'safety': 'no', **overrides}
        response = self.client.post(reverse('care_start', args=[self.pet.pk]), data)
        return list(self.client.session['care_drafts'])[-1], response

    def finish(self):
        key, _ = self.start()
        self.client.post(reverse('care_questions', args=[self.pet.pk, key]), {'duration': 'today', 'changed': 'yes', 'activity': 'reduced', 'intake': 'usual'})
        return key

    def test_preview_then_explicit_save_is_idempotent(self):
        key = self.finish()
        self.assertFalse(Assessment.objects.exists())
        response = self.client.get(reverse('care_preview', args=[self.pet.pk, key]))
        self.assertContains(response, 'Contact your veterinarian today')
        self.assertFalse(Assessment.objects.exists())
        url = reverse('care_save', args=[self.pet.pk, key])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url, {'result': 'invented healthy diagnosis'})
        self.client.post(url)
        self.assertEqual(Assessment.objects.count(), 1)
        saved = Assessment.objects.get()
        self.assertEqual(saved.result['level'], 'contact')
        self.pet.name = 'New name'
        self.pet.save()
        self.assertContains(self.client.get(reverse('care_record', args=[saved.pk])), "Miso's care summary")

    def test_emergency_skips_followups(self):
        key, response = self.start(safety='yes')
        self.assertRedirects(response, reverse('care_preview', args=[self.pet.pk, key]))
        self.assertContains(self.client.get(response.url), 'Contact a veterinarian now')

    def test_unknown_topic_and_empty_form(self):
        response = self.client.post(reverse('care_start', args=[self.pet.pk]), {'concern': 'Hello'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Assessment.objects.exists())
        key, response = self.start(topic='other')
        self.assertContains(self.client.get(response.url), 'different resource')

    def test_drafts_and_records_are_owner_scoped(self):
        key = self.finish()
        self.client.post(reverse('care_save', args=[self.pet.pk, key]))
        record = Assessment.objects.get()
        self.client.force_login(self.other)
        for name, args in [('care_start', [self.pet.pk]), ('care_questions', [self.pet.pk, key]), ('care_preview', [self.pet.pk, key]), ('care_record', [record.pk]), ('care_download', [record.pk])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 404)
        self.assertEqual(self.client.post(reverse('care_save', args=[self.pet.pk, key])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('care_history')), 'Sleeping for ten hours')

    def test_public_qr_never_contains_assessments(self):
        key = self.finish()
        self.client.post(reverse('care_save', args=[self.pet.pk, key]))
        response = Client().get(reverse('public_pet', args=[self.pet.public_token]))
        self.assertNotContains(response, 'Sleeping for ten hours')
        self.assertNotContains(response, 'Private allergy')

    def test_cannot_skip_questions_and_save(self):
        key, _ = self.start()
        response = self.client.post(reverse('care_save', args=[self.pet.pk, key]))
        self.assertRedirects(response, reverse('care_questions', args=[self.pet.pk, key]))
        self.assertFalse(Assessment.objects.exists())
        self.assertEqual(self.client.get(reverse('care_preview', args=[self.pet.pk, uuid.uuid4()])).status_code, 404)

    def test_expired_draft_and_download_provenance(self):
        key = self.finish()
        self.client.post(reverse('care_save', args=[self.pet.pk, key]))
        record = Assessment.objects.get()
        response = self.client.get(reverse('care_download', args=[record.pk]))
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertContains(response, 'guided-care-1.0')
        self.assertContains(response, 'https://www.merckvetmanual.com/')
        session = self.client.session
        drafts = session['care_drafts']
        drafts[key]['started'] = 0
        session['care_drafts'] = drafts
        session.save()
        self.assertEqual(self.client.get(reverse('care_preview', args=[self.pet.pk, key])).status_code, 404)
