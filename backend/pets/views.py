import hashlib
import re
from io import BytesIO
import uuid
import qrcode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.db.models import Count, Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import PetForm, SightingForm
from .models import Pet, Sighting

def limited(request, scope, maximum=10, window=600):
    # Single-process local prototype. Use a shared cache before multi-worker hosting.
    digest = hashlib.sha256(request.META.get('REMOTE_ADDR', 'unknown').encode()).hexdigest()
    key = f'limit:{scope}:{digest}'
    if cache.add(key, 1, window):
        return False
    try:
        return cache.incr(key) > maximum
    except ValueError:
        cache.set(key, 1, window)
        return False

def too_many():
    response = HttpResponse('Too many attempts. Please wait 10 minutes and try again.', status=429)
    response['Retry-After'] = '600'
    return response

class OwnerLoginView(LoginView):
    template_name = 'registration/login.html'
    def post(self, request, *args, **kwargs):
        if limited(request, 'login', 20):
            return too_many()
        return super().post(request, *args, **kwargs)

def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST' and limited(request, 'signup', 10):
        return too_many()
    form = UserCreationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.save())
        return redirect('dashboard')
    return render(request, 'registration/signup.html', {'form': form})

@login_required
def dashboard(request):
    pets = Pet.objects.filter(owner=request.user).annotate(unread=Count('sightings', filter=Q(sightings__is_read=False)))
    return render(request, 'pets/dashboard.html', {'pets': pets, 'pet_count': pets.count(), 'missing_count': pets.filter(is_missing=True).count(), 'unread_count': Sighting.objects.filter(pet__owner=request.user, is_read=False).count()})

def owned_pet(request, pk):
    return get_object_or_404(Pet, pk=pk, owner=request.user)

@login_required
def pet_edit(request, pk=None):
    pet = owned_pet(request, pk) if pk else Pet(owner=request.user)
    old_photo = pet.photo.name
    form = PetForm(request.POST or None, request.FILES or None, instance=pet)
    if request.method == 'POST' and form.is_valid():
        pet = form.save(commit=False)
        if form.cleaned_data.get('remove_photo'):
            pet.photo = ''
            pet.share_photo = False
        medical_fields = {'allergies', 'medical_conditions', 'medications', 'vaccination_notes', 'handling_notes', 'vet_name', 'vet_phone'}
        if medical_fields.intersection(form.changed_data) or form.cleaned_data.get('confirm_medical_review'):
            pet.medical_updated_at = timezone.now()
        pet.save()
        if old_photo and old_photo != pet.photo.name:
            pet._meta.get_field('photo').storage.delete(old_photo)
        messages.success(request, 'Pet profile saved.')
        return redirect('pet_detail', pk=pet.pk)
    return render(request, 'pets/pet_form.html', {'form': form, 'pet': pet})

def public_url(request, pet):
    path = reverse('public_pet', args=[pet.public_token])
    return settings.PUBLIC_BASE_URL + path if settings.PUBLIC_BASE_URL else request.build_absolute_uri(path)

@login_required
def pet_detail(request, pk):
    pet = owned_pet(request, pk)
    return render(request, 'pets/pet_detail.html', {'pet': pet, 'public_url': public_url(request, pet), 'sightings': pet.sightings.all(), 'card': pet_card(pet, private=True)})

@login_required
@require_POST
def pet_status(request, pk):
    pet = owned_pet(request, pk)
    value = request.POST.get('status')
    if value not in ('missing', 'home'):
        return HttpResponse('Invalid status.', status=400)
    pet.is_missing = value == 'missing'
    pet.save(update_fields=['is_missing'])
    messages.success(request, 'Marked as missing.' if pet.is_missing else 'Marked as safely home.')
    return redirect('pet_detail', pk=pk)

@login_required
@require_POST
def rotate_qr(request, pk):
    pet = owned_pet(request, pk)
    if request.POST.get('confirm') != 'yes':
        return HttpResponse('Confirm that the old QR code will stop working.', status=400)
    pet.public_token = uuid.uuid4()
    pet.save(update_fields=['public_token'])
    messages.success(request, 'New QR created. Replace any printed copies of the old code.')
    return redirect('pet_detail', pk=pk)

@login_required
def qr_image(request, pk):
    pet = owned_pet(request, pk)
    buffer = BytesIO()
    qrcode.make(public_url(request, pet)).save(buffer, format='PNG')
    buffer.seek(0)
    return FileResponse(buffer, content_type='image/png', as_attachment=request.GET.get('download') == '1', filename=f'petvision-{pet.pk}-qr.png')

@login_required
def private_photo(request, pk):
    pet = owned_pet(request, pk)
    return photo_response(pet)

def photo_response(pet):
    if not pet.photo:
        raise Http404
    try:
        return FileResponse(pet.photo.open('rb'), content_type='image/jpeg')
    except FileNotFoundError:
        raise Http404

def public_photo(request, token):
    pet = get_object_or_404(Pet, public_token=token, share_photo=True)
    return photo_response(pet)

def pet_card(pet, private=False):
    card = {'name': pet.name, 'species': pet.get_species_display(), 'is_missing': pet.is_missing, 'token': pet.public_token, 'has_photo': bool(pet.photo and pet.share_photo)}
    if private or pet.share_profile_details:
        card['details'] = {'age_years': pet.age_years, 'breed': pet.breed, 'sex': pet.get_sex_display(), 'color_markings': pet.color_markings, 'weight_kg': pet.weight_kg}
    if private or pet.share_medical_details:
        card['medical'] = {field: getattr(pet, field) for field in ['allergies', 'medical_conditions', 'medications', 'vaccination_notes', 'handling_notes', 'vet_name', 'vet_phone', 'medical_updated_at']}
        card['medical']['vet_dial'] = re.sub(r'[^+0-9]', '', pet.vet_phone)
    if private or pet.share_emergency_contact:
        card['contact'] = {'name': pet.emergency_contact_name, 'phone': pet.emergency_contact_phone, 'dial': re.sub(r'[^+0-9]', '', pet.emergency_contact_phone)}
    return card

def public_pet(request, token):
    pet = get_object_or_404(Pet, public_token=token)
    if request.method == 'POST' and limited(request, 'sighting', 8):
        return too_many()
    form = SightingForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        report = form.save(commit=False)
        report.pet = pet
        report.save()
        return redirect('report_received', token=token)
    # Explicit public projection: never pass the private Pet instance to this template.
    public = pet_card(pet)
    return render(request, 'pets/public_pet.html', {'pet': public, 'form': form})

def report_received(request, token):
    get_object_or_404(Pet, public_token=token)
    return render(request, 'pets/report_received.html')

@login_required
@require_POST
def read_report(request, pk):
    report = get_object_or_404(Sighting, pk=pk, pet__owner=request.user)
    report.is_read = True
    report.save(update_fields=['is_read'])
    return redirect('pet_detail', pk=report.pet_id)
