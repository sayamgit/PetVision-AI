from io import BytesIO
import warnings
from django import forms
from .models import Pet
from PIL import Image, ImageOps, UnidentifiedImageError

class PhotoCheckForm(forms.Form):
    purpose = forms.ChoiceField(label='What would you like to do?', choices=[('', 'Choose a check'), ('general', 'General pet check — no disease prediction'), ('concern', 'Check a visible concern — use the image model')], help_text='Choose general for an ordinary pet photo. Choose a visible concern only when you have noticed a change.')
    species = forms.ChoiceField(label='Animal type',choices=[('', 'Choose cat or dog'),('cat','Cat'),('dog','Dog')])
    pet = forms.ModelChoiceField(label='Link to a saved pet (optional)',queryset=Pet.objects.none(),required=False,empty_label='No profile — another animal')
    request_id = forms.UUIDField(widget=forms.HiddenInput)
    image = forms.FileField(label='Photo',help_text='JPEG, PNG or WebP. Maximum 2 MB and 12 million pixels.',widget=forms.FileInput(attrs={'accept':'image/jpeg,image/png,image/webp'}))
    observations = forms.CharField(required=False,max_length=1200,label='What have you noticed? (optional)',widget=forms.Textarea(attrs={'rows':3,'placeholder':'Describe the change and how long it has been happening.'}))

    def __init__(self, *args, user=None, pet=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['species'].required = user is not None
        if user is not None:
            self.fields['pet'].queryset = Pet.objects.filter(owner=user)
        if pet:
            self.fields['pet'].initial = pet.pk
            self.fields['pet'].disabled = True
            self.fields['species'].initial = pet.species
            self.fields['species'].disabled = True

    def clean(self):
        values = super().clean()
        pet = values.get('pet')
        if pet and pet.species != values.get('species'):
            self.add_error('species', 'Choose the same animal type as the saved profile, or leave the profile unlinked.')
        return values

    def clean_image(self):
        upload = self.cleaned_data['image']
        if upload.size > 2*1024*1024:
            raise forms.ValidationError('Choose a photo smaller than 2 MB.')
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('error',Image.DecompressionBombWarning)
                raw = upload.read()
                with Image.open(BytesIO(raw)) as source:
                    if source.format not in ('JPEG','PNG','WEBP') or source.width*source.height>12000000 or getattr(source,'n_frames',1)!=1:
                        raise ValueError('Unsupported image')
                    source.verify()
                with Image.open(BytesIO(raw)) as source:
                    source.load()
                    converted = ImageOps.exif_transpose(source).convert('RGB')
                    if min(converted.size)<64:
                        raise ValueError('Image too small')
                    clean = Image.new('RGB',converted.size)
                    clean.paste(converted)
                    converted.close()
                    return clean
        except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombError,Image.DecompressionBombWarning):
            raise forms.ValidationError('Choose a valid, still JPEG, PNG or WebP photo at least 64 pixels on each side and no more than 12 million pixels.')
