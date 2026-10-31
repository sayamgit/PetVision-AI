import uuid
from types import SimpleNamespace
from django.conf import settings
from django.db import models

def photo_path(instance, filename):
    return f'pet-photos/{uuid.uuid4().hex}.jpg'

class Pet(models.Model):
    is_demo = models.BooleanField(default=False, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=60)
    species = models.CharField(max_length=3, choices=[('cat', 'Cat'), ('dog', 'Dog')])
    age_years = models.PositiveSmallIntegerField(null=True, blank=True)
    breed = models.CharField(max_length=100, blank=True)
    sex = models.CharField(max_length=10, blank=True, choices=[('female', 'Female'), ('male', 'Male'), ('unknown', 'Unknown')])
    color_markings = models.CharField(max_length=200, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    microchip_number = models.CharField(max_length=40, blank=True)
    allergies = models.TextField(max_length=1500, blank=True)
    medical_conditions = models.TextField(max_length=1500, blank=True)
    medications = models.TextField(max_length=1500, blank=True)
    vaccination_notes = models.TextField(max_length=1500, blank=True)
    handling_notes = models.TextField(max_length=1000, blank=True)
    vet_name = models.CharField(max_length=150, blank=True)
    vet_phone = models.CharField(max_length=30, blank=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=30, blank=True)
    share_profile_details = models.BooleanField(default=False)
    share_medical_details = models.BooleanField(default=False)
    share_emergency_contact = models.BooleanField(default=False)
    medical_updated_at = models.DateTimeField(null=True, blank=True)
    care_notes = models.TextField(blank=True, max_length=2000)
    photo = models.ImageField(upload_to=photo_path, blank=True)
    share_photo = models.BooleanField(default=False)
    is_missing = models.BooleanField(default=False)
    public_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

class Sighting(models.Model):
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='sightings')
    message = models.TextField(max_length=2000)
    location_text = models.CharField(max_length=250, blank=True)
    finder_contact = models.CharField(max_length=200, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Assessment(models.Model):
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='assessments')
    draft_id = models.UUIDField(unique=True)
    concern = models.TextField(max_length=1200)
    topic = models.CharField(max_length=20)
    observations = models.JSONField(default=dict)
    pet_snapshot = models.JSONField(default=dict)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']


def check_image_path(instance, filename):
    return f'photo-checks/{uuid.uuid4().hex}.jpg'

class PhotoCheck(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='photo_checks')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pet = models.ForeignKey(Pet, null=True, blank=True, on_delete=models.SET_NULL, related_name='photo_checks')
    species = models.CharField(max_length=3, choices=[('cat','Cat'),('dog','Dog')])
    image = models.ImageField(upload_to=check_image_path)
    observations = models.TextField(max_length=1200, blank=True)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.owner_id and self.pet_id:
            self.owner_id = self.pet.owner_id
        super().save(*args, **kwargs)

    @property
    def is_general_check(self):
        return self.result.get('purpose') == 'general'

    @property
    def has_split_scores(self):
        rows = self.result.get('ranked', [])
        return bool(rows) and rows[0]['score'] <= 50

    @property
    def display_label(self):
        if self.is_general_check:
            return 'General pet check'
        rows = self.result.get('ranked', [])
        return 'Inconclusive image match' if self.has_split_scores else (rows[0]['label'] if rows else 'No saved category')

    def chat_summary(self, focus=""):
        if self.is_general_check:
            return 'General pet check. No image analysis was performed. My observations: ' + (self.observations or 'No changes described yet.')
        focus_note = (f"I want to discuss the {focus} match. Ask follow-up questions about the symptoms and explain possible causes only when supported by your reference notes. Do not confirm a subtype or change the image scores. " if focus else "")
        matches = '; '.join(f"{row['label']} ({row['score']:.1f}% model score)" for row in self.result['ranked'][:3])
        return (focus_note + f"This {self.species}'s PetVision photo check ({self.result['version']}) ranked: {matches}. "
                'These are uncalibrated image-model scores, not a diagnosis. Normal-looking skin does not establish health; fungal classification is unreliable. '
                'You have not seen the photo. Please help me understand the limitations and what observations to discuss with a veterinarian. '
                + ('My observations: '+self.observations if self.observations else 'What additional symptoms should I describe?'))

class Conversation(models.Model):
    inline_photo = models.BooleanField(default=False)
    photo_focus = models.CharField(max_length=80, blank=True, default='')
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pet_conversations')
    species = models.CharField(max_length=3, blank=True, default='', choices=[('cat','Cat'),('dog','Dog')])
    photo_check = models.ForeignKey(PhotoCheck, null=True, blank=True, on_delete=models.SET_NULL, related_name='conversations')
    answer_mode = models.CharField(max_length=10, blank=True, default='', choices=[('gemini', 'Automatic'), ('reference', 'Local reference guide')])
    gemini_consent_at = models.DateTimeField(null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pet = models.ForeignKey(Pet, null=True, blank=True, on_delete=models.SET_NULL, related_name='conversations')
    title = models.CharField(max_length=100, default='New conversation')
    busy_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.pet_id:
            if not self.owner_id:
                self.owner_id = self.pet.owner_id
            if not self.species:
                self.species = self.pet.species
        super().save(*args, **kwargs)

    @property
    def subject(self):
        species = self.species or (self.pet.species if self.pet_id else '')
        return SimpleNamespace(name=self.pet.name if self.pet_id else 'this '+species,
            species=species, age_years=self.pet.age_years if self.pet_id and self.pet.species==species else None,
            get_species_display=lambda: species.title(),
            photo_context={'selected_category': self.photo_focus or ('General pet check — no image analysis performed' if self.photo_check.is_general_check else self.photo_check.display_label), 'observations': self.photo_check.observations} if self.photo_check_id else None)

    class Meta:
        ordering = ['-updated_at']
        constraints = [models.UniqueConstraint(fields=['photo_check','photo_focus'], condition=models.Q(inline_photo=True), name='unique_inline_photo_focus')]

class ChatTurn(models.Model):
    state = models.JSONField(default=dict)
    suggestions = models.JSONField(default=list)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='turns')
    request_id = models.UUIDField(unique=True)
    question = models.TextField(max_length=2000)
    answer = models.TextField(blank=True)
    sources = models.JSONField(default=list)
    status = models.CharField(max_length=12, default='pending')
    urgency = models.CharField(max_length=20, blank=True)
    model = models.CharField(max_length=100, blank=True)
    error = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']


class Reminder(models.Model):
    pet = models.ForeignKey(Pet, on_delete=models.CASCADE, related_name='reminders')
    calendar_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    title = models.CharField(max_length=120)
    kind = models.CharField(max_length=20, default='other', choices=[
        ('appointment', 'Vet appointment'), ('vaccination', 'Vaccination'),
        ('grooming', 'Grooming'), ('medication', 'Prescribed medication'), ('other', 'Other care')])
    notes = models.TextField(max_length=500, blank=True)
    due_at = models.DateTimeField(db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['due_at', 'pk']
