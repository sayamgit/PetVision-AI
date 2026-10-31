"""Photo-scoped conversations, with image context kept out of owner messages."""
import uuid
from urllib.parse import urlencode
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import PhotoCheck, Conversation
from .views import limited

def location(conversation):
    return reverse('photo_result', args=[conversation.photo_check_id]) + '?' + urlencode({'focus': conversation.photo_focus})

def result_context(request, record):
    focus = request.GET.get('focus', '')
    if not focus:
        return {}
    if focus not in [row['label'] for row in record.result['ranked']]:
        return None
    conversation = Conversation.objects.filter(owner=request.user, photo_check=record, photo_focus=focus, inline_photo=True).first()
    turns = list(conversation.turns.all()) if conversation else []
    opener = ('What changes have you noticed in the eye, and when did they start?' if focus == 'Eye Infection'
              else 'What changes have you noticed, and when did they start?')
    return {'focus': focus, 'conversation': conversation, 'turns': turns, 'opener': opener,
            'request_id': uuid.uuid4(), 'suggestions': turns[-1].suggestions if turns else []}

@login_required
@require_POST
def start(request, key):
    from . import chat_views
    record = get_object_or_404(PhotoCheck, pk=key, owner=request.user)
    focus = request.POST.get('focus', '')
    mode = request.POST.get('backend', 'gemini')
    if focus not in [row['label'] for row in record.result['ranked']] or mode not in ('gemini','reference') or request.POST.get('start_ack') != 'yes':
        return JsonResponse({'error': 'Open a photo result and select a match to begin.'}, status=400)
    form = chat_views.MessageForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'error': 'Enter a message of 1–2000 characters.'}, status=400)
    if limited(request, 'photo-followup', 40):
        return JsonResponse({'error': 'Too many requests. Please try again later.'}, status=429)
    conversation, _ = Conversation.objects.get_or_create(
        photo_check=record, photo_focus=focus, inline_photo=True,
        defaults={'owner': request.user, 'species': record.species, 'pet': record.pet,
                  'answer_mode': mode, 'gemini_consent_at': timezone.now() if mode == 'gemini' else None,
                  'title': focus + ' · photo follow-up'})
    # A stale first-message form must not silently change an existing preference.
    if conversation.answer_mode != mode:
        return JsonResponse({'error': 'This follow-up already has a reply preference. Refresh to continue it.'}, status=409)
    return chat_views.send(request, conversation.pk)
