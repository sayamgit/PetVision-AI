from datetime import timedelta
import uuid
from types import SimpleNamespace
from django import forms
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Conversation, ChatTurn, PhotoCheck
from .views import owned_pet, limited, too_many
from .photo_reference import reply, is_guided_answer
from . import gemini_engine
from .reference_library import ENTRIES
from .care_ui import vet_contact

class MessageForm(forms.Form):
    question = forms.CharField(max_length=2000, strip=True)
    request_id = forms.UUIDField()

def introduction_url(conversation):
    return reverse('new_pet_chat',args=[conversation.pet_id]) if conversation.pet_id else reverse('new_general_chat')

@login_required
def new_chat(request, pk=None):
    pet = owned_pet(request,pk) if pk is not None else None
    photo_check = None
    resuming = None
    for parameter in ('photo','resume'):
        if not request.GET.get(parameter):
            continue
        try:
            key = forms.UUIDField().clean(request.GET[parameter])
        except forms.ValidationError:
            return HttpResponse('Invalid conversation or photo check.',status=400)
        if parameter == 'photo':
            photo_check=get_object_or_404(PhotoCheck,pk=key,owner=request.user)
            if pet and photo_check.pet_id != pet.pk:
                return HttpResponse('Photo check not found.',status=404)
        else:
            resuming=get_object_or_404(Conversation,pk=key,owner=request.user,pet=pet)
    focus = request.GET.get('focus','')
    if focus and (not photo_check or focus not in [row['label'] for row in photo_check.result['ranked']]):
        return HttpResponse('Invalid prediction selection.',status=400)
    species = resuming.species if resuming else photo_check.species if photo_check else pet.species if pet else request.POST.get('species','')
    if request.method=='POST':
        if limited(request,'new-chat',30):
            return too_many()
        mode=request.POST.get('backend','gemini')
        if mode not in ('gemini','reference') or request.POST.get('start_ack')!='yes' or species not in ('cat','dog'):
            return HttpResponse('Choose cat or dog and start from the conversation introduction.',status=400)
        conversation=resuming or Conversation(pet=pet,owner=request.user,species=species)
        if photo_check and not resuming:
            conversation.photo_check=photo_check
            conversation.photo_focus=focus
        conversation.answer_mode=mode
        if mode=='gemini' and not conversation.gemini_consent_at:
            conversation.gemini_consent_at=timezone.now()
        conversation.save()
        return redirect('pet_chat',key=conversation.pk)
    subject=pet or SimpleNamespace(name='this '+species if species else 'an animal',pk=None)
    return render(request,'chat/new.html',{'pet':subject,'photo_check':photo_check,'resuming':resuming,
        'intro_url':reverse('new_pet_chat',args=[pet.pk]) if pet else reverse('new_general_chat'),
        'choose_species':not pet and not photo_check and not resuming,
        'recent':Conversation.objects.filter(owner=request.user,pet=pet)[:10], 'gemini_configured':gemini_engine.configured()})

@login_required
def chat(request,key):
    conversation=get_object_or_404(Conversation.objects.select_related('pet','photo_check'),pk=key,owner=request.user)
    if conversation.inline_photo and conversation.photo_check_id:
        from .photo_followup import location
        return redirect(location(conversation) + '#photo-followup')
    if not conversation.answer_mode and not conversation.gemini_consent_at:
        return redirect(introduction_url(conversation)+'?resume='+str(conversation.pk))
    turns=list(conversation.turns.all())
    return render(request,'chat/conversation.html',{'conversation':conversation,'pet':conversation.subject,'intro_url':introduction_url(conversation),
        'care_pet':conversation.pet,'vet_contact':vet_contact(conversation.pet, request.user),'turns':turns,'draft_question':'',
        'request_id':uuid.uuid4(),'suggestions':turns[-1].suggestions if turns else ['The animal is not eating food','There is so much hair fall']})


def respond(request, conversation, error=None, status=200):
    from .photo_followup import location
    url = location(conversation) if conversation.inline_photo and conversation.photo_check_id else reverse('pet_chat', args=[conversation.pk])
    if 'application/json' in request.headers.get('Accept', ''):
        return JsonResponse({'url':url,'error':error}, status=status)
    return redirect(url + '#chat-end')

@login_required
@require_POST
def send(request, key):
    conversation = get_object_or_404(Conversation.objects.select_related('pet'), pk=key, owner=request.user)
    form = MessageForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'error':'Enter a message of 1–2000 characters and refresh the page if needed.'},status=400)
    if limited(request, 'chat-send', 40):
        return JsonResponse({'error':'Too many requests. Please try again later.'},status=429)
    request_id = form.cleaned_data['request_id']
    old = ChatTurn.objects.filter(request_id=request_id).first()
    if old:
        if old.conversation_id != conversation.pk:
            return JsonResponse({'error':'Invalid request identifier.'},status=400)
        return respond(request, conversation)
    backend = request.POST.get('backend', conversation.answer_mode or 'gemini')
    if backend not in ('gemini','reference'):
        return JsonResponse({'error':'Choose Gemini or the reference guide.'},status=400)
    cloud_ready = gemini_engine.configured() if backend == 'gemini' else False
    if backend == 'gemini' and not conversation.gemini_consent_at:
        return JsonResponse({'error':'Open All conversations and continue from the introduction before sending a message.'},status=400)
    now = timezone.now()
    locked = Conversation.objects.filter(pk=key).filter(Q(busy_until__isnull=True)|Q(busy_until__lt=now)).update(busy_until=now + timedelta(seconds=180))
    if not locked:
        return JsonResponse({'error':'A reply is already being prepared. Wait a moment, then refresh.'},status=409)
    try:
        history = list(conversation.turns.filter(status='complete').order_by('-pk')[:6])[::-1]
        turn = ChatTurn.objects.create(conversation=conversation,request_id=request_id,question=form.cleaned_data['question'])
        if conversation.title == 'New conversation':
            Conversation.objects.filter(pk=key).update(title=turn.question[:90])
        try:
            fallback_reason = None
            if backend == 'reference' or is_guided_answer(conversation.subject, turn.question, history):
                result = reply(conversation.subject, turn.question, history)
            else:
                try:
                    if not cloud_ready:
                        raise gemini_engine.ChatUnavailable('Gemini is not configured.')
                    result = gemini_engine.reply(conversation.subject, turn.question, history)
                except gemini_engine.ChatUnavailable as error:
                    fallback_reason = error.code
                    result = reply(conversation.subject, turn.question, history)
                    notice = gemini_engine.failure_notice(error)
                    notice += ('This reply uses the limited reference guide. It may not understand every question or earlier follow-up. ')
                    notice += ('Suggested choices continue locally; a new typed question will try Gemini again. '
                               if result.get('state', {}).get('photo_guide') else 'We will try Gemini again when you send another message. ')
                    notice += 'No paid service has been enabled.'
                    result.setdefault('state', {})['fallback_notice'] = notice
                    result['state']['fallback_reason'] = fallback_reason
                    result['state']['fallback_diagnostic'] = error.diagnostic
                    # A provider switch must not hide an earlier urgent recommendation.
                    if history and history[-1].urgency == 'urgent':
                        result['urgency'] = 'urgent'
                        result['answer'] = ('Earlier guidance recommended urgent veterinary care. This reference reply does not reassess or clear that concern.\n\n' + result['answer'])
            if fallback_reason is None:
                # Reference dialogue state may have been copied from a fallback turn.
                result.get('state', {}).pop('fallback_notice', None)
                result.get('state', {}).pop('fallback_reason', None)
                result.get('state', {}).pop('fallback_diagnostic', None)
            turn.answer = result['answer']
            turn.sources = result['sources']
            turn.urgency = result['urgency']
            turn.model = result['model']
            turn.state = result.get('state',{})
            turn.suggestions = result.get('suggestions',[])
            turn.status = 'complete'
        except gemini_engine.ChatUnavailable as error:
            turn.status = 'failed'
            turn.model = gemini_engine.MODEL
            turn.error = str(error)
        except (ValueError, KeyError, TypeError):
            turn.status = 'failed'
            turn.error = 'The guide could not complete this response. Please try again. For urgent symptoms, contact a veterinarian now.'
        turn.save()
        return respond(request, conversation)
    finally:
        Conversation.objects.filter(pk=key).update(busy_until=None, updated_at=timezone.now())

@login_required
@require_POST
def delete(request, key):
    conversation = get_object_or_404(Conversation, pk=key, owner=request.user)
    if request.POST.get('confirm') != 'yes':
        return HttpResponse('Confirm deletion.', status=400)
    if conversation.busy_until and conversation.busy_until > timezone.now():
        return HttpResponse('Wait until the current reply finishes before deleting.',status=409)
    pk = conversation.pet_id
    conversation.delete()
    return redirect('new_pet_chat', pk=pk) if pk else redirect('new_general_chat')
