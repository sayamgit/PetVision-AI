from io import BytesIO
import re
from decimal import Decimal
import warnings
from PIL import Image, ImageOps
from django import forms
from django.core.files.base import ContentFile
from .models import Pet, Sighting

class PetForm(forms.ModelForm):
    photo = forms.FileField(required=False, help_text='JPEG, PNG or WebP, up to 2 MB and 12 million pixels. Replaces the previous photo.', widget=forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}))
    remove_photo = forms.BooleanField(required=False)
    confirm_medical_review = forms.BooleanField(required=False, label='I have reviewed the medical details and they are up to date.', help_text='Updates the medical review date even if the information has not changed.')
    class Meta:
        model = Pet
        fields = ['name', 'species', 'age_years', 'breed', 'sex', 'color_markings', 'weight_kg', 'microchip_number', 'allergies', 'medical_conditions', 'medications', 'vaccination_notes', 'handling_notes', 'vet_name', 'vet_phone', 'emergency_contact_name', 'emergency_contact_phone', 'care_notes', 'photo', 'share_photo', 'share_profile_details', 'share_medical_details', 'share_emergency_contact']
        labels = {
            'care_notes': 'Private care notes', 'age_years': 'Age in years (optional)',
            'color_markings': 'Color and identifying markings', 'weight_kg': 'Weight (kg)',
            'microchip_number': 'Microchip number (always private)',
            'allergies': 'Known allergies / adverse reactions', 'medical_conditions': 'Medical conditions',
            'medications': 'Current medications (as prescribed)', 'vaccination_notes': 'Vaccination record summary',
            'handling_notes': 'Handling and behavior notes', 'vet_name': 'Veterinarian / clinic',
            'vet_phone': 'Veterinarian phone', 'emergency_contact_name': 'Emergency contact name',
            'emergency_contact_phone': 'Emergency contact phone',
            'share_photo': 'Publish the pet photo',
            'share_profile_details': 'Publish age, breed, sex, markings, and weight',
            'share_medical_details': 'Publish medical details, handling notes, and veterinarian contact',
            'share_emergency_contact': 'Publish the emergency contact name and phone',
        }
        widgets = {name: forms.Textarea(attrs={'rows': 3}) for name in ['care_notes', 'allergies', 'medical_conditions', 'medications', 'vaccination_notes', 'handling_notes']}
        help_texts = {
            'allergies': 'Leave blank if unknown. Only enter “none known” if you have confirmed that.',
            'medications': 'Copy the current prescription details; this card does not recommend treatment.',
            'vaccination_notes': 'Include vaccine names and dates if known. This is not a verified certificate.',
            'emergency_contact_phone': 'Only publish a number you have permission to share.',
        }

    def sections(self):
        groups = [
            ('01', 'Identity', 'The details that help someone recognize your pet.', ['name', 'species', 'age_years', 'breed', 'sex', 'color_markings', 'weight_kg', 'photo', 'remove_photo']),
            ('02', 'Emergency medical card', 'Owner-entered information for a finder or veterinarian. Blank fields mean unknown, not an absence of a condition.', ['allergies', 'medical_conditions', 'medications', 'vaccination_notes', 'handling_notes', 'vet_name', 'vet_phone', 'confirm_medical_review']),
            ('03', 'Emergency contact', 'A person who can be contacted if your pet needs help.', ['emergency_contact_name', 'emergency_contact_phone']),
            ('04', 'Private records', 'These fields never appear on the public QR report card.', ['microchip_number', 'care_notes']),
            ('05', 'QR sharing controls', 'Anyone with the QR code or its link can see the sections you publish. Name, species, and missing status are always visible.', ['share_photo', 'share_profile_details', 'share_medical_details', 'share_emergency_contact']),
        ]
        return [{'number': number, 'title': title, 'description': description, 'fields': [self[name] for name in names]} for number, title, description, names in groups]

    def clean_weight_kg(self):
        value = self.cleaned_data.get('weight_kg')
        if value is not None and not Decimal('0') < value <= Decimal('200'):
            raise forms.ValidationError('Enter a weight greater than 0 and no more than 200 kg.')
        return value

    def clean_phone(self, name):
        value = self.cleaned_data.get(name, '').strip()
        if value and (not re.fullmatch(r'\+?[0-9 ()-]+', value) or not 7 <= len(re.sub(r'\D', '', value)) <= 15):
            raise forms.ValidationError('Enter a phone number with 7–15 digits, optionally using +, spaces, brackets or hyphens.')
        return value

    def clean_vet_phone(self):
        return self.clean_phone('vet_phone')

    def clean_emergency_contact_phone(self):
        return self.clean_phone('emergency_contact_phone')

    def clean_age_years(self):
        age = self.cleaned_data['age_years']
        if age is not None and age > 40:
            raise forms.ValidationError('Enter an age between 0 and 40 years.')
        return age

    def clean_photo(self):
        if 'photo' not in self.files:
            return self.instance.photo
        upload = self.cleaned_data.get('photo')
        if not upload:
            return upload
        if upload.size > 2 * 1024 * 1024:
            raise forms.ValidationError('Choose a photo smaller than 2 MB.')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(upload) as source:
                    if source.format not in ('JPEG', 'PNG', 'WEBP') or source.width * source.height > 12000000:
                        raise ValueError('Unsupported image')
                    source.load()
                    converted = ImageOps.exif_transpose(source).convert('RGB')
                    converted.thumbnail((1200, 1200))
                    # A fresh image strips EXIF, GPS, comments, and other source metadata.
                    clean = Image.new('RGB', converted.size)
                    clean.paste(converted)
                    output = BytesIO()
                    clean.save(output, 'JPEG', quality=88)
            return ContentFile(output.getvalue(), name='pet.jpg')
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombWarning, Image.DecompressionBombError):
            raise forms.ValidationError('Upload a valid JPEG, PNG or WebP photo under 12 million pixels.')

class SightingForm(forms.ModelForm):
    share_location = forms.BooleanField(required=False, label='I agree to share these coordinates with the pet owner.')
    website = forms.CharField(required=False, widget=forms.HiddenInput)
    class Meta:
        model = Sighting
        fields = ['message', 'location_text', 'finder_contact', 'latitude', 'longitude']
        labels = {'message': 'What did you see?', 'location_text': 'Location or landmark (optional)', 'finder_contact': 'How can the owner reach you? (optional)'}
        widgets = {'message': forms.Textarea(attrs={'rows': 4}), 'latitude': forms.HiddenInput, 'longitude': forms.HiddenInput}

    def clean(self):
        data = super().clean()
        lat, lon = data.get('latitude'), data.get('longitude')
        if (lat is None) != (lon is None):
            raise forms.ValidationError('Share both coordinates or clear the location.')
        if lat is not None:
            if not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise forms.ValidationError('The coordinates are outside the valid range.')
            if not data.get('share_location'):
                raise forms.ValidationError('Confirm location sharing or clear the coordinates.')
        if data.get('website'):
            raise forms.ValidationError('The report could not be accepted.')
        return data
