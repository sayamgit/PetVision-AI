import tempfile
from pathlib import Path
from io import StringIO
from unittest.mock import patch
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Pet
from .care_ui import vet_contact


class ShowcaseTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.settings_override = override_settings(MEDIA_ROOT=self.path/'media', DEBUG=True)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.photo = self.path/'input.png'
        Image.new('RGB',(40,50),'gray').save(self.photo)
        self.options = {'white_cat':str(self.photo),'gray_cat':str(self.photo),'dog':str(self.photo),'stdout':StringIO()}

    def create(self):
        with patch.dict('os.environ',{'PETVISION_DEMO_PASSWORD':'Synthetic-test-pass!'}):
            call_command('create_showcase',**self.options)

    def test_showcase_private_images_credentials_and_idempotence(self):
        self.create()
        user = get_user_model().objects.get(username='Puss')
        self.assertTrue(user.check_password('Synthetic-test-pass!'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        pets = list(Pet.objects.filter(owner=user))
        self.assertEqual({pet.name for pet in pets},{'Luna','Smokey','Coco'})
        self.assertEqual([pet.species for pet in pets].count('cat'),2)
        self.assertEqual([pet.species for pet in pets].count('dog'),1)
        self.assertTrue(all(pet.is_demo and pet.photo and not pet.share_photo and not pet.share_medical_details for pet in pets))
        files = {pet.photo.name for pet in pets}
        self.create()
        self.assertEqual(Pet.objects.filter(owner=user).count(),3)
        self.assertEqual({p.photo.name for p in Pet.objects.filter(owner=user)},files)
        self.client.force_login(user)
        self.assertNotContains(self.client.get(reverse('dashboard')),'Showcase account')
        self.assertEqual(self.client.get(reverse('private_photo',args=[pets[0].pk])).status_code,200)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('private_photo',args=[pets[0].pk])).status_code,302)
        self.assertEqual(self.client.get(reverse('public_photo',args=[pets[0].public_token])).status_code,404)

    def test_existing_real_account_is_never_changed(self):
        user=get_user_model().objects.create_user('Puss',password='Existing-owner-pass!')
        with self.assertRaises(CommandError): self.create()
        user.refresh_from_db()
        self.assertTrue(user.check_password('Existing-owner-pass!'))
        self.assertEqual(Pet.objects.count(),0)

    def test_invalid_photo_does_not_leave_partial_account(self):
        self.photo.write_bytes(b'not an image')
        with self.assertRaises(CommandError): self.create()
        self.assertFalse(get_user_model().objects.filter(username='Puss').exists())

    def test_contacts_use_normal_links_and_still_require_public_sharing(self):
        self.create()
        pet=Pet.objects.get(name='Luna')
        self.assertEqual(vet_contact(pet,pet.owner)['dial'], '+12025550147')
        outsider=get_user_model().objects.create_user('outsider')
        self.assertIsNone(vet_contact(pet,outsider))
        self.client.force_login(pet.owner)
        for name in ['pet_detail','pet_care_hub']:
            response=self.client.get(reverse(name,args=[pet.pk]))
            self.assertNotContains(response,'Showcase account')
            self.assertNotContains(response,'Calling disabled')
            self.assertContains(response,'tel:+12025550147')
        self.client.logout()
        response=self.client.get(reverse('public_pet',args=[pet.public_token]))
        self.assertNotContains(response,'tel:')
        pet.share_medical_details=True
        pet.share_emergency_contact=True
        pet.save()
        response=self.client.get(reverse('public_pet',args=[pet.public_token]))
        self.assertContains(response,'tel:+12025550147')
        self.assertContains(response,'tel:+12025550186')
        self.assertNotContains(response,'Fictional care details')

    def test_local_only_creation_and_real_profiles_unaffected(self):
        with override_settings(DEBUG=False):
            with self.assertRaises(CommandError): self.create()
        user=get_user_model().objects.create_user('actual-owner')
        pet=Pet.objects.create(owner=user,name='Actual pet',species='dog',vet_phone='1234567890')
        self.assertFalse(pet.is_demo)
        self.assertIsNotNone(vet_contact(pet,user))
        self.client.force_login(user)
        self.assertNotContains(self.client.get(reverse('pet_detail',args=[pet.pk])),'Showcase account')
