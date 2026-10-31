"""Create an explicitly fictional local showcase without changing existing accounts."""
import getpass
import os
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from pets.forms import PetForm
from pets.models import Pet


class Command(BaseCommand):
    help = 'Create Puss and three fictional profiles using supplied photos. Existing accounts are never overwritten.'

    def add_arguments(self, parser):
        parser.add_argument('--white-cat', required=True)
        parser.add_argument('--gray-cat', required=True)
        parser.add_argument('--dog', required=True)

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Create the sample account only in the local development environment.')
        users = get_user_model().objects
        existing = users.filter(username__iexact='Puss').first()
        if existing:
            if existing.username == 'Puss' and existing.groups.filter(name='PetVision showcase').exists():
                self.stdout.write('Showcase account already exists; no password, profiles or photos were changed.')
                return
            raise CommandError('An account named Puss already exists. It was not modified.')
        password = os.environ.get('PETVISION_DEMO_PASSWORD') or getpass.getpass('Password for the local Puss showcase: ')
        if len(password) < 8:
            raise CommandError('Use at least eight characters for the showcase password.')
        examples = [
            ('white_cat', dict(name='Luna', species='cat', age_years=2, sex='female', weight_kg='3.80',
                breed='Domestic longhair', color_markings='White long coat, pink nose and ears, amber eyes.',
                handling_notes='Gentle and curious; approach slowly and support her body when lifting.',
                care_notes='Enjoys quiet sunny spots and wand toys.')),
            ('gray_cat', dict(name='Smokey', species='cat', age_years=3, sex='male', weight_kg='4.60',
                breed='Domestic longhair', color_markings='Fluffy gray coat, darker face and paws, amber eyes.',
                handling_notes='Reserved with strangers; offer space and allow him to approach first.',
                care_notes='Enjoys window watching and soft grooming brushes.')),
            ('dog', dict(name='Coco', species='dog', age_years=4, sex='female', weight_kg='3.10',
                breed='Small mixed breed', color_markings='Small brown-and-white dog with a white forehead and chest, feathered ears.',
                handling_notes='Calm with familiar people; use a secure harness outdoors and lift with support.',
                care_notes='Enjoys short walks and resting beside her person.')),
        ]
        forms = []
        for option, values in examples:
            path = Path(options[option])
            if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
                raise CommandError('Each supplied photo must exist and be under 2 MB.')
            values.update(microchip_number='',
                allergies='No known allergies.',
                medical_conditions='No ongoing medical conditions recorded.',
                medications='No current medications.',
                vaccination_notes='Vaccination review: 12 October 2026. Keep the vaccination card with the pet records.',
                vet_name='Paw & Whisker Clinic', vet_phone='+1 202-555-0147',
                emergency_contact_name='Alex', emergency_contact_phone='+1 202-555-0186')
            form = PetForm(data=values, files={'photo':SimpleUploadedFile(path.name,path.read_bytes())})
            if not form.is_valid():
                raise CommandError('A sample profile failed validation: ' + str(form.errors.as_text()))
            forms.append(form)
        # Validate all files first; roll back the account and clean only new uploads on failure.
        saved_files = []
        try:
            with transaction.atomic():
                owner = users.create_user(username='Puss', password=password, first_name='Puss', last_name='Showcase')
                group, _ = Group.objects.get_or_create(name='PetVision showcase')
                owner.groups.add(group)
                for form in forms:
                    pet = form.save(commit=False)
                    pet.owner = owner
                    pet.is_demo = True
                    # Sharing stays private until the owner enables it in the normal UI.
                    pet.medical_updated_at = timezone.now()
                    pet.save()
                    saved_files.append((pet.photo.storage,pet.photo.name))
        except Exception:
            for storage, name in saved_files:
                storage.delete(name)
            raise
        self.stdout.write(self.style.SUCCESS('Created local showcase account Puss with Luna, Smokey and Coco. Photos remain private. Contact buttons open the dialer using reserved fictional numbers.'))
