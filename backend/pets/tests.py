from io import BytesIO
import tempfile
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from .models import Pet, Sighting


class RecoveryTests(TestCase):
    def test_report_card_sharing_is_explicit_and_independent(self):
        self.pet.breed = 'PRIVATE BREED'
        self.pet.allergies = 'PRIVATE ALLERGY'
        self.pet.microchip_number = 'PRIVATE CHIP'
        self.pet.emergency_contact_name = 'PRIVATE PERSON'
        self.pet.emergency_contact_phone = '+91 98765 43210'
        self.pet.save()
        url = reverse('public_pet', args=[self.pet.public_token])
        response = Client().get(url)
        for value in ('PRIVATE BREED', 'PRIVATE ALLERGY', 'PRIVATE CHIP', 'PRIVATE PERSON', '98765'):
            self.assertNotContains(response, value)
        self.pet.share_medical_details = True
        self.pet.save()
        response = Client().get(url)
        self.assertContains(response, 'PRIVATE ALLERGY')
        self.assertNotContains(response, 'PRIVATE PERSON')
        self.assertNotContains(response, 'PRIVATE BREED')
        self.pet.share_emergency_contact = True
        self.pet.share_profile_details = True
        self.pet.save()
        response = Client().get(url)
        self.assertContains(response, 'PRIVATE BREED')
        self.assertContains(response, 'PRIVATE PERSON')
        self.assertContains(response, 'tel:+919876543210')
        self.assertNotContains(response, 'PRIVATE CHIP')
        self.assertNotContains(response, 'PRIVATE MEDICAL NOTE')
        self.pet.share_medical_details = False
        self.pet.save()
        self.assertNotContains(Client().get(url), 'PRIVATE ALLERGY')

    def test_medical_review_date_and_unknown_values(self):
        url = reverse('pet_edit', args=[self.pet.pk])
        data = {'name': 'Miso', 'species': 'cat', 'allergies': 'Owner entered allergy', 'share_medical_details': 'on'}
        self.client.post(url, data)
        self.pet.refresh_from_db()
        reviewed = self.pet.medical_updated_at
        self.assertIsNotNone(reviewed)
        self.client.post(url, {**data, 'breed': 'New breed'})
        self.pet.refresh_from_db()
        self.assertEqual(reviewed, self.pet.medical_updated_at)
        self.client.post(url, {**data, 'confirm_medical_review': 'on'})
        self.pet.refresh_from_db()
        self.assertGreater(self.pet.medical_updated_at, reviewed)
        response = Client().get(reverse('public_pet', args=[self.pet.public_token]))
        self.assertContains(response, 'Not provided — unknown')
        self.assertContains(response, 'Owner reported')

    def test_invalid_contact_and_weight_are_rejected(self):
        url = reverse('pet_edit', args=[self.pet.pk])
        response = self.client.post(url, {'name': 'Miso', 'species': 'cat', 'weight_kg': '-1', 'vet_phone': 'javascript:alert(1)'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Enter a phone number')
        self.assertContains(response, 'Enter a weight greater than 0')
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.vet_phone, '')

    def setUp(self):
        cache.clear()
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.owner = get_user_model().objects.create_user('owner', password='Some-safe-test-pass!')
        self.other = get_user_model().objects.create_user('other', password='Some-safe-test-pass!')
        self.pet = Pet.objects.create(owner=self.owner, name='Miso', species='cat', age_years=3, care_notes='PRIVATE MEDICAL NOTE')
        self.client.force_login(self.owner)

    def photo(self):
        buffer = BytesIO()
        image = Image.new('RGB', (48, 48), 'orange')
        exif = Image.Exif()
        exif[270] = 'PRIVATE IMAGE METADATA'
        image.save(buffer, 'JPEG', exif=exif)
        return SimpleUploadedFile('example.jpg', buffer.getvalue(), content_type='image/jpeg')

    def test_complete_recovery_flow(self):
        self.client.post(reverse('pet_status', args=[self.pet.pk]), {'status': 'missing'})
        finder = Client()
        page = reverse('public_pet', args=[self.pet.public_token])
        self.assertContains(finder.get(page), 'Reported missing')
        response = finder.post(page, {'message': 'Seen by the library', 'location_text': 'West gate', 'finder_contact': 'Ask for Sam'})
        self.assertEqual(response.status_code, 302)
        report = Sighting.objects.get()
        self.assertContains(self.client.get(reverse('pet_detail', args=[self.pet.pk])), 'Seen by the library')
        self.client.post(reverse('read_report', args=[report.pk]))
        report.refresh_from_db()
        self.assertTrue(report.is_read)
        self.client.post(reverse('pet_status', args=[self.pet.pk]), {'status': 'home'})
        self.pet.refresh_from_db()
        self.assertFalse(self.pet.is_missing)

    def test_private_endpoints_reject_other_owner(self):
        report = Sighting.objects.create(pet=self.pet, message='Private sighting')
        self.client.force_login(self.other)
        for name in ('pet_detail', 'pet_edit', 'qr_image', 'private_photo'):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name, args=[self.pet.pk])).status_code, 404)
        for name, payload in [('pet_edit', {'name': 'Stolen', 'species': 'dog'}), ('pet_status', {'status': 'missing'}), ('rotate_qr', {'confirm': 'yes'})]:
            self.assertEqual(self.client.post(reverse(name, args=[self.pet.pk]), payload).status_code, 404)
        self.assertEqual(self.client.post(reverse('read_report', args=[report.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('dashboard')), 'Miso')

    def test_anonymous_cannot_read_owner_pages(self):
        self.client.logout()
        for name in ('pet_detail', 'pet_edit', 'qr_image', 'private_photo'):
            self.assertEqual(self.client.get(reverse(name, args=[self.pet.pk])).status_code, 302)

    def test_public_page_has_no_private_fields_or_reports(self):
        Sighting.objects.create(pet=self.pet, message='PRIVATE SIGHTING', finder_contact='PRIVATE CONTACT')
        response = Client().get(reverse('public_pet', args=[self.pet.public_token]))
        for text in ('PRIVATE MEDICAL NOTE', 'PRIVATE SIGHTING', 'PRIVATE CONTACT'):
            self.assertNotContains(response, text)
        self.assertEqual(set(response.context['pet']), {'name', 'species', 'is_missing', 'token', 'has_photo'})
        self.assertIn('no-store', response['Cache-Control'])

    def test_qr_rotation_revokes_old_page_and_photo(self):
        old_token = self.pet.public_token
        self.client.post(reverse('rotate_qr', args=[self.pet.pk]), {'confirm': 'yes'})
        self.pet.refresh_from_db()
        self.assertNotEqual(old_token, self.pet.public_token)
        for name in ('public_pet', 'public_photo', 'report_received'):
            self.assertEqual(Client().get(reverse(name, args=[old_token])).status_code, 404)
        self.assertEqual(Client().get(reverse('public_pet', args=[self.pet.public_token])).status_code, 200)

    def test_mutations_require_post_and_rotation_confirmation(self):
        for name in ('pet_status', 'rotate_qr'):
            self.assertEqual(self.client.get(reverse(name, args=[self.pet.pk])).status_code, 405)
        self.assertEqual(self.client.post(reverse('rotate_qr', args=[self.pet.pk])).status_code, 400)
        self.assertEqual(self.client.post(reverse('pet_status', args=[self.pet.pk]), {'status': 'invalid'}).status_code, 400)

    def test_public_form_requires_csrf(self):
        secure = Client(enforce_csrf_checks=True)
        self.assertEqual(secure.post(reverse('public_pet', args=[self.pet.public_token]), {'message': 'Hi'}).status_code, 403)
        self.assertFalse(Sighting.objects.exists())

    def test_coordinates_need_consent_pair_and_valid_range(self):
        url = reverse('public_pet', args=[self.pet.public_token])
        for payload in ({'latitude': '12'}, {'latitude': '12', 'longitude': '77'}, {'latitude': '95', 'longitude': '77', 'share_location': 'on'}):
            self.assertEqual(Client().post(url, {'message': 'Found pet', **payload}).status_code, 200)
        self.assertFalse(Sighting.objects.exists())
        self.assertEqual(Client().post(url, {'message': 'Found pet', 'latitude': '12.123456', 'longitude': '77.123456', 'share_location': 'on'}).status_code, 302)
        self.assertEqual(str(Sighting.objects.get().latitude), '12.123456')

    def test_rate_limit_public_submissions(self):
        url = reverse('public_pet', args=[self.pet.public_token])
        finder = Client()
        for _ in range(8):
            self.assertEqual(finder.post(url, {'message': 'Saw pet'}).status_code, 302)
        self.assertEqual(finder.post(url, {'message': 'Saw pet'}).status_code, 429)
        self.assertEqual(Sighting.objects.count(), 8)

    def test_photo_upload_strips_metadata_and_requires_public_opt_in(self):
        self.client.post(reverse('pet_edit', args=[self.pet.pk]), {'name': 'Miso', 'species': 'cat', 'photo': self.photo()})
        self.pet.refresh_from_db()
        with self.pet.photo.open('rb') as handle:
            self.assertNotIn(b'PRIVATE IMAGE METADATA', handle.read())
        public_photo = reverse('public_photo', args=[self.pet.public_token])
        self.assertEqual(Client().get(public_photo).status_code, 404)
        response = self.client.get(reverse('private_photo', args=[self.pet.pk]))
        self.assertEqual(response.status_code, 200)
        response.close()
        old_name = self.pet.photo.name
        self.client.post(reverse('pet_edit', args=[self.pet.pk]), {'name': 'Miso', 'species': 'cat', 'share_photo': 'on'})
        self.pet.refresh_from_db()
        self.assertEqual(old_name, self.pet.photo.name)
        response = Client().get(public_photo)
        self.assertEqual(response.status_code, 200)
        response.close()
        self.client.post(reverse('pet_edit', args=[self.pet.pk]), {'name': 'Miso', 'species': 'cat', 'remove_photo': 'on'})
        self.pet.refresh_from_db()
        self.assertFalse(self.pet.photo)
        self.assertFalse(self.pet.share_photo)
        self.assertEqual(Client().get(public_photo).status_code, 404)

    def test_invalid_photo_and_age_rejected(self):
        response = self.client.post(reverse('pet_create'), {'name': 'Bad', 'species': 'cat', 'photo': SimpleUploadedFile('bad.jpg', b'not an image')})
        self.assertContains(response, 'Upload a valid')
        self.assertEqual(Pet.objects.count(), 1)
        self.assertContains(self.client.post(reverse('pet_create'), {'name': 'Bad', 'species': 'cat', 'age_years': 80}), 'between 0 and 40')

    def test_create_cannot_choose_another_owner(self):
        self.client.post(reverse('pet_create'), {'name': 'Luna', 'species': 'dog', 'owner': self.other.pk})
        self.assertEqual(Pet.objects.get(name='Luna').owner_id, self.owner.pk)

    @override_settings(PUBLIC_BASE_URL='https://pets.example.org')
    def test_qr_png_and_configured_origin(self):
        response = self.client.get(reverse('qr_image', args=[self.pet.pk]) + '?download=1')
        image_bytes = b''.join(response.streaming_content)
        self.assertTrue(image_bytes.startswith(b'\x89PNG'))
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertContains(self.client.get(reverse('pet_detail', args=[self.pet.pk])), f'https://pets.example.org/p/{self.pet.public_token}/')

    def test_html_in_report_is_escaped(self):
        Sighting.objects.create(pet=self.pet, message='<script>alert(1)</script>')
        response = self.client.get(reverse('pet_detail', args=[self.pet.pk]))
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_signup_login_logout(self):
        client = Client()
        response = client.post(reverse('signup'), {'username': 'new-owner', 'password1': 'Paws-and-leaves-834!', 'password2': 'Paws-and-leaves-834!'})
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(client.get(reverse('logout')).status_code, 405)
        self.assertEqual(client.post(reverse('logout')).status_code, 302)
        self.assertRedirects(client.post(reverse('login'), {'username': 'new-owner', 'password': 'Paws-and-leaves-834!'}), reverse('dashboard'))
