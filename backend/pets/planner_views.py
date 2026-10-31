"""Owner-only care records and portable calendar reminders; no cloud calls."""
from datetime import datetime, time, timedelta, timezone as utc_timezone
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from .models import Reminder, PhotoCheck, ChatTurn, Assessment
from .views import owned_pet, limited, too_many


class ReminderForm(forms.ModelForm):
    due_at = forms.DateTimeField(label='Date and time (India Standard Time)',
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'type': 'datetime-local'}))

    class Meta:
        model = Reminder
        fields = ['title', 'kind', 'due_at', 'notes']
        widgets = {'notes': forms.Textarea(attrs={'rows': 3})}
        help_texts = {'title': 'For example: annual check-up or grooming appointment.',
            'notes': 'Optional private notes. These are not included in the calendar file.'}

    def clean_due_at(self):
        value = self.cleaned_data['due_at']
        if value <= timezone.now():
            raise forms.ValidationError('Choose a future date and time.')
        return value


@login_required
def reminders(request, pk):
    pet = owned_pet(request, pk)
    form = ReminderForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        if limited(request, 'reminder-create', 30):
            return too_many()
        if Reminder.objects.filter(pet=pet, completed_at__isnull=True).count() >= 100:
            form.add_error(None, 'This pet has 100 open reminders. Complete or remove some before adding more.')
        else:
            reminder = form.save(commit=False)
            reminder.pet = pet
            reminder.save()
            messages.success(request, 'Reminder saved. Open it below to add it to your phone calendar.')
            return redirect(reverse('pet_reminders', args=[pet.pk]) + f'#reminder-{reminder.pk}')
    view = 'completed' if request.GET.get('view') == 'completed' else 'open'
    rows = Reminder.objects.filter(pet=pet, completed_at__isnull=(view == 'open'))
    rows = rows.order_by('due_at', 'pk') if view == 'open' else rows.order_by('-completed_at', '-pk')
    return render(request, 'care/reminders.html', {'pet': pet, 'form': form,
        'page': Paginator(rows, 15).get_page(request.GET.get('page')), 'view': view, 'now': timezone.now()})


@login_required
@require_POST
def reminder_action(request, pk, reminder_id):
    pet = owned_pet(request, pk)
    reminder = get_object_or_404(Reminder, pk=reminder_id, pet=pet)
    action = request.POST.get('action')
    if action == 'complete':
        Reminder.objects.filter(pk=reminder.pk, completed_at__isnull=True).update(completed_at=timezone.now())
        messages.success(request, 'Marked as done. Update or remove the separate calendar event if needed.')
    elif action == 'delete' and request.POST.get('confirm') == 'yes':
        reminder.delete()
        messages.success(request, 'Reminder removed from PetVision. Remove the calendar event separately if you added it.')
    else:
        return HttpResponse('Choose a valid reminder action.', status=400)
    return redirect('pet_reminders', pk=pet.pk)


def ical_text(value):
    return str(value).replace('\\', '\\\\').replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def fold_ical(line):
    # RFC 5545: fold at 75 octets without splitting a UTF-8 character.
    lines, current = [], ''
    for char in line:
        if len((current + char).encode('utf-8')) > 75:
            lines.append(current)
            current = ' '
        current += char
    lines.append(current)
    return '\r\n'.join(lines)


@login_required
def reminder_calendar(request, pk, reminder_id):
    pet = owned_pet(request, pk)
    reminder = get_object_or_404(Reminder, pk=reminder_id, pet=pet, completed_at__isnull=True)
    if reminder.due_at <= timezone.now():
        return HttpResponse('This reminder is past due. Create a new reminder with a future time.', status=400)
    stamp = lambda value: value.astimezone(utc_timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//PetVision//Care reminder//EN',
        'CALSCALE:GREGORIAN', 'BEGIN:VEVENT', f'UID:{reminder.calendar_id}@petvision.local',
        'DTSTAMP:' + stamp(reminder.created_at), 'DTSTART:' + stamp(reminder.due_at),
        'DTEND:' + stamp(reminder.due_at + timedelta(minutes=15)),
        'SUMMARY:' + ical_text(f'{pet.name}: {reminder.title}'),
        'DESCRIPTION:' + ical_text('Owner-created PetVision reminder. Check the event time and notification setting after saving. Changes in PetVision do not update this calendar event.'),
        'CLASS:PRIVATE', 'TRANSP:TRANSPARENT', 'BEGIN:VALARM', 'TRIGGER:-PT30M',
        'ACTION:DISPLAY', 'DESCRIPTION:PetVision care reminder', 'END:VALARM', 'END:VEVENT', 'END:VCALENDAR']
    response = HttpResponse('\r\n'.join(fold_ical(line) for line in lines) + '\r\n', content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="petvision-reminder-{reminder.pk}.ics"'
    return response


def report_data(pet, days, now):
    # Calendar days in the configured local timezone, including today up to generation.
    first_date = timezone.localdate(now) - timedelta(days=days - 1)
    start = timezone.make_aware(datetime.combine(first_date, time.min))
    window = {'created_at__gte': start, 'created_at__lte': now}
    photos = PhotoCheck.objects.filter(pet=pet, owner=pet.owner, **window).order_by('-created_at')
    turns = ChatTurn.objects.filter(conversation__pet=pet, conversation__owner=pet.owner,
        status='complete', **window).select_related('conversation').order_by('-created_at', '-pk')
    assessments = Assessment.objects.filter(pet=pet, **window).order_by('-created_at', '-pk')
    due = Reminder.objects.filter(pet=pet, due_at__gte=start, due_at__lte=now).order_by('due_at')
    completed = Reminder.objects.filter(pet=pet, completed_at__gte=start, completed_at__lte=now).order_by('-completed_at')
    groups = {'photos': photos, 'turns': turns, 'assessments': assessments, 'due': due, 'completed': completed}
    data = {'pet': pet, 'days': days, 'start': start, 'end': now, 'timezone_name': timezone.get_current_timezone_name()}
    data['counts'] = {key: rows.count() for key, rows in groups.items()}
    data['truncated'] = any(count > 200 for count in data['counts'].values())
    data.update({key: list(rows[:200]) for key, rows in groups.items()})
    return data


def report_text(data):
    local = lambda value: timezone.localtime(value).strftime('%d %b %Y, %H:%M')
    lines = ['PETVISION — PRIVATE CARE ACTIVITY REPORT',
        f"Pet: {data['pet'].name} ({data['pet'].get_species_display()})",
        f"Period: {local(data['start'])} to {local(data['end'])} ({data['timezone_name']})",
        'This summarizes recorded activity, not a diagnosis or a measure of health improvement.',
        'No records does not mean no symptoms. Deleted records and unlinked animal checks are not included.',
        'Historical guidance is not a current assessment. No new AI assessment was performed.', '']
    if data['truncated']:
        lines.append('Each section shows at most 200 records. Counts below include all matching records.')
    lines += [f"{key}: {value}" for key, value in data['counts'].items()]
    lines += ['', 'OWNER QUESTIONS']
    for turn in data['turns']:
        lines += [local(turn.created_at), turn.question, '']
    lines += ['PHOTO CHECKS — MODEL SUGGESTIONS, NOT DIAGNOSES']
    for photo in data['photos']:
        top = photo.result.get('ranked', [{}])[0] if photo.result.get('ranked') else {}
        lines += [f"{local(photo.created_at)}: {photo.display_label}", 'Owner observations: ' + (photo.observations or 'Not entered'), '']
    lines += ['SAVED QUESTIONNAIRES']
    for record in data['assessments']:
        lines += [local(record.created_at), record.concern, '']
    lines += ['REMINDERS DUE IN THIS PERIOD']
    for reminder in data['due']:
        state = 'Completed' if reminder.completed_at and reminder.completed_at <= data['end'] else 'Not marked done'
        lines += [f'{local(reminder.due_at)}: {reminder.title} — {state}']
    lines += ['', 'REMINDERS MARKED DONE IN THIS PERIOD']
    for reminder in data['completed']:
        lines += [f'{local(reminder.completed_at)}: {reminder.title}']
    return '\n'.join(lines)


@login_required
def report(request, pk, period):
    pet = owned_pet(request, pk)
    if period not in ('weekly', 'monthly'):
        raise Http404
    data = report_data(pet, 7 if period == 'weekly' else 30, timezone.now())
    data['period'] = period
    if request.GET.get('download') == 'text':
        response = HttpResponse(report_text(data), content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="petvision-{period}-{pet.pk}.txt"'
        return response
    return render(request, 'care/activity_report.html', data)
