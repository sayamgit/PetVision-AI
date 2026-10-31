import uuid
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Assessment, Pet, Conversation, PhotoCheck, Reminder
from .care_ui import vet_contact
from .views import owned_pet, limited, too_many
from .care_forms import CareStartForm, FollowupForm
from .care_content import assess, immediate_reason, TOPIC_NAMES, EMERGENCY_DESCRIPTION, SOURCES

def stash(request, key, draft):
    drafts = request.session.get('care_drafts', {})
    drafts[key] = draft
    request.session['care_drafts'] = dict(list(drafts.items())[-5:])

def load_draft(request, pet, key):
    draft = request.session.get('care_drafts', {}).get(str(key))
    if not draft or draft.get('owner_id') != request.user.pk or draft.get('pet_id') != pet.pk:
        raise Http404('This draft is not available. Please start a new care check.')
    if timezone.now().timestamp() - draft['started'] > 3600:
        raise Http404('This draft expired. Please start a new care check.')
    return draft

@login_required
def care_home(request):
    return render(request, 'care/home.html', {'pets': Pet.objects.filter(owner=request.user), 'recent_chats': Conversation.objects.filter(owner=request.user,pet__isnull=True)[:5], 'recent_photos': PhotoCheck.objects.filter(owner=request.user,pet__isnull=True)[:5]})

@login_required
def pet_hub(request, pk):
    pet = owned_pet(request, pk)
    return render(request, 'care/pet_hub.html', {'pet':pet, 'reminders':Reminder.objects.filter(pet=pet, completed_at__isnull=True).order_by('due_at')[:3], 'now':timezone.now(), 'vet_contact':vet_contact(pet, request.user), 'recent_chats':Conversation.objects.filter(owner=request.user,pet=pet)[:5], 'recent_photos':PhotoCheck.objects.filter(owner=request.user,pet=pet)[:5]})

@login_required
def start(request, pk):
    pet = owned_pet(request, pk)
    form = CareStartForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        if limited(request, 'care-start', 30):
            return too_many()
        data = dict(form.cleaned_data)
        if data['topic'] == 'other' and any(phrase in data['concern'].lower() for phrase in ('not eating', 'not eat', 'won’t eat', "won't eat", 'appetite', 'refusing food')):
            data['topic'] = 'appetite'
        draft = {**data, 'owner_id': request.user.pk, 'pet_id': pet.pk, 'started': timezone.now().timestamp()}
        key = str(uuid.uuid4())
        stash(request, key, draft)
        destination = 'care_preview' if immediate_reason(draft) or draft['topic'] == 'other' else 'care_questions'
        return redirect(destination, pk=pet.pk, key=key)
    return render(request, 'care/start.html', {'pet': pet, 'form': form, 'emergency': EMERGENCY_DESCRIPTION, 'source': SOURCES['emergency']})

@login_required
def questions(request, pk, key):
    pet = owned_pet(request, pk)
    draft = load_draft(request, pet, key)
    if immediate_reason(draft) or draft['topic'] == 'other':
        return redirect('care_preview', pk=pk, key=key)
    form = FollowupForm(request.POST or None, topic=draft['topic'], initial=draft.get('answers'))
    if request.method == 'POST' and form.is_valid():
        draft['answers'] = form.cleaned_data
        stash(request, str(key), draft)
        return redirect('care_preview', pk=pk, key=key)
    return render(request, 'care/questions.html', {'pet': pet, 'draft': draft, 'form': form})

def snapshot(pet):
    return {'name': pet.name, 'species': pet.get_species_display(), 'age_years': pet.age_years, 'allergies': pet.allergies, 'medical_conditions': pet.medical_conditions, 'medications': pet.medications}

def observations(draft):
    rows = [{'question': 'Emergency sign check', 'answer': dict(CareStartForm().fields['safety'].choices)[draft['safety']]}]
    form = FollowupForm(topic=draft['topic'])
    for name, value in draft.get('answers', {}).items():
        field = form.fields.get(name)
        if field:
            rows.append({'question': field.label, 'answer': dict(field.choices).get(value, value)})
    return rows

def ready(draft):
    return bool(immediate_reason(draft) or draft['topic'] == 'other' or draft.get('answers'))

@login_required
def preview(request, pk, key):
    pet = owned_pet(request, pk)
    draft = load_draft(request, pet, key)
    if not ready(draft):
        return redirect('care_questions', pk=pk, key=key)
    result = assess(draft, draft.get('answers', {}))
    return render(request, 'care/result.html', {'pet': pet, 'draft_key': key, 'concern': draft['concern'], 'topic': TOPIC_NAMES[draft['topic']], 'result': result, 'observations': observations(draft), 'snapshot': snapshot(pet), 'is_preview': True, 'vet_contact':vet_contact(pet, request.user)})

@login_required
@require_POST
def save(request, pk, key):
    pet = owned_pet(request, pk)
    draft = load_draft(request, pet, key)
    if not ready(draft):
        return redirect('care_questions', pk=pk, key=key)
    record, _ = Assessment.objects.get_or_create(draft_id=key, defaults={'pet': pet, 'concern': draft['concern'], 'topic': draft['topic'], 'observations': observations(draft), 'pet_snapshot': snapshot(pet), 'result': assess(draft, draft.get('answers', {}))})
    if record.pet_id != pet.pk:
        raise Http404
    return redirect('care_record', pk=record.pk)

@login_required
def history(request):
    records = Assessment.objects.filter(pet__owner=request.user).select_related('pet')
    return render(request, 'care/history.html', {'page': Paginator(records, 15).get_page(request.GET.get('page'))})

@login_required
def record(request, pk):
    assessment = get_object_or_404(Assessment.objects.select_related('pet'), pk=pk, pet__owner=request.user)
    return render(request, 'care/result.html', {'pet': assessment.pet, 'assessment': assessment, 'concern': assessment.concern, 'topic': TOPIC_NAMES.get(assessment.topic, assessment.topic), 'result': assessment.result, 'observations': assessment.observations, 'snapshot': assessment.pet_snapshot, 'vet_contact':vet_contact(assessment.pet, request.user)})

@login_required
def download(request, pk):
    record = get_object_or_404(Assessment, pk=pk, pet__owner=request.user)
    result = record.result
    lines = ['PETVISION — PRIVATE CARE SUMMARY', f"Pet: {record.pet_snapshot['name']} ({record.pet_snapshot['species']})", f'Saved: {record.created_at.isoformat()}', f"Mode: {result['mode']}", f"Version: {result['version']}", '', 'OWNER QUESTION', record.concern, '', 'OBSERVATIONS']
    lines.extend(f"{row['question']}: {row['answer']}" for row in record.observations)
    lines.extend(['', 'GUIDANCE', result['title'], result['reason'], result['action'], *result['notes'], '', 'OWNER-ENTERED PET CONTEXT'])
    lines.extend(f"{key}: {value or 'Not provided'}" for key, value in record.pet_snapshot.items())
    lines.extend(['', 'REFERENCES'])
    lines.extend(f"{source['title']} — {source['url']} (checked {source['checked_on']})" for source in result['sources'])
    lines.extend(['', result['limitation']])
    response = HttpResponse('\n'.join(lines), content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="petvision-care-{record.pk}.txt"'
    return response
