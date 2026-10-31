"""Small, explicit follow-up guide when the photo conversation cannot use Gemini."""
import re
from copy import deepcopy
from . import reference_engine
from .reference_library import source_rows, EYE_NOTES
from .practical_care import local_steps

EAR_SOURCES = {
    'cat': {'id':'cat-ear-care', 'title':'Cornell — Feline ear disorders',
        'url':'https://www.vet.cornell.edu/departments-centers-and-institutes/cornell-feline-health-center/health-information/feline-health-topics/feline-ear-disorders', 'checked_on':'2026-10-19'},
    'dog': {'id':'dog-ear-care', 'title':'Merck — Ear infections in dogs',
        'url':'https://www.merckvetmanual.com/dog-owners/ear-disorders-of-dogs/ear-infections-and-otitis-externa-in-dogs', 'checked_on':'2026-10-19'},
}
CAT_CLEAN = {'id':'cat-ear-cleaning', 'title':'VCA — Ear cleaning in cats',
    'url':'https://vcahospitals.com/know-your-pet/instructions-for-ear-cleaning-in-cats','checked_on':'2026-10-19'}
SAFETY = ('safety', 'Is there severe pain, heavy bleeding, or trouble breathing?',
    ['A severe sign is present', 'None of these severe signs noticed', 'Not sure about severe signs'])
DURATION = ('duration', 'When did you first notice the change?',
    ['Started today', 'Started yesterday', 'More than two days ago', 'Not sure when it started'])
DETAILS = {
    'eyes': ('area', 'Is one eye affected or are both eyes affected?', ['One eye affected', 'Both eyes affected', 'Not sure which eye']),
    'ears': ('area', 'Have you noticed the problem in one ear or both ears?', ['One ear affected', 'Both ears affected', 'Not sure which ear']),
    'skin': ('area', 'Is the visible change limited to one patch or in several areas?', ['One patch noticed', 'Several areas affected', 'Not sure about the areas']),
    'dental': ('eating', 'Have you noticed difficulty eating?', ['Difficulty eating noticed', 'No eating difficulty noticed', 'Not sure about eating']),
}


def topic_for(pet):
    context = getattr(pet, 'photo_context', None)
    if not context:
        return None
    label = context.get('selected_category','').lower()
    if 'eye' in label: return 'eyes'
    if 'ear' in label: return 'ears'
    if 'dental' in label: return 'dental'
    if any(word in label for word in ('fungal','ringworm','mange','scabies','skin','hot spot','tick')): return 'skin'
    return None


def prior_guide(pet, history):
    previous = deepcopy(history[-1].state.get('photo_guide', {})) if history else {}
    if previous.get('topic') != topic_for(pet):
        return {}
    return previous


def question_row(topic, answers):
    return next((row for row in (SAFETY, DURATION, DETAILS[topic]) if row[0] not in answers), None)


def is_guided_answer(pet, question, history):
    previous = prior_guide(pet, history)
    if not previous: return False
    row = question_row(previous['topic'], previous.get('answers',{}))
    return bool(row and question in row[2])


def reply(pet, question, history):
    topic = topic_for(pet)
    if not topic or reference_engine.emergency_mode(question) or re.search(r'\b(dose|dosage|medicine|medication|antibiotic|prescribe)\b', question, re.I):
        return reference_engine.reply(pet, question, history)
    # A photo's topic must never override a newly reported concern, such as no food.
    ranked = reference_engine.rank(question, pet.species)
    if ranked and ranked[0][1]['id'].split('-')[0] != topic:
        return reference_engine.reply(pet, question, history)
    if history and history[-1].state.get('topic') and history[-1].state['topic'].split('-')[0] != topic:
        return reference_engine.reply(pet, question, history)
    previous = prior_guide(pet, history)
    answers = previous.get('answers',{})
    row = question_row(topic, answers)
    if row and question in row[2]:
        answers[row[0]] = question
    state = {'photo_guide': {'topic':topic, 'answers':answers}, 'provider':'guided_reference'}
    if answers.get('safety') == 'A severe sign is present':
        return dict(answer='You reported a severe sign. Contact an emergency veterinarian now; do not wait to finish this guide. Tell the clinic which sign you saw and when it began.',
            sources=source_rows(['emergency','visit']), urgency='urgent', model='guided-photo-1',state=state,suggestions=[])
    sources = source_rows(['visit'])
    if topic == 'ears':
        answer = 'Ear scratching, head shaking or discharge can have different causes. The image category cannot confirm mites or an infection. An ear examination is needed to identify the cause; contact your veterinarian about persistent signs.'
        sources.append(EAR_SOURCES[pet.species])
        if pet.species == 'cat': sources.append(CAT_CLEAN)
        state['care_steps'] = {'do_now':['Note which ear is affected and when signs began. Tell the clinic about discharge, head shaking or discomfort.'],
            'avoid':['Do not probe the ear canal or use cotton buds. Use only ear products and cleaning methods recommended by your veterinarian.'], 'watch_for':[]}
    elif topic == 'eyes':
        answer = 'Cloudiness, squinting or vision changes need prompt veterinary assessment. The selected image category cannot establish the cause. '
        answer += EYE_NOTES[pet.species][0]['summary']
        sources += source_rows(EYE_NOTES[pet.species][0]['source_ids'])
    elif topic == 'skin':
        answer = 'Different skin conditions can look alike. Record the affected areas and whether the change is spreading or causing licking or scratching. An examination and sometimes tests are needed to identify the cause.'
        sources += source_rows(['skin'])
        steps, ids = local_steps('skin', pet.species)
        if steps: state['care_steps'] = steps
        sources += source_rows(ids)
    else:
        entry = reference_engine.BY_ID['dental-' + pet.species]
        answer = entry['answer'] + ' The photo cannot confirm which dental condition is present.'
        sources += source_rows(entry['sources'])
    if answers:
        answer += '\n\nYour recorded choices:\n' + '\n'.join(answers.values())
    row = question_row(topic, answers)
    if row:
        answer += '\n\n' + row[1]
        suggestions = row[2]
    else:
        answer += '\n\nThese details are ready to discuss with your veterinarian. This guide cannot identify a subtype. You can type another question; automatic mode will try Gemini again.'
        suggestions = []
    answer += '\n\nThis is a guided reference follow-up. Suggested choices continue locally without using Gemini. Other wording may need Gemini or a different reference.'
    urgency = 'contact_vet'
    if history and history[-1].urgency == 'urgent':
        urgency = 'urgent'
        answer = 'Earlier guidance recommended urgent veterinary care. This guide does not reassess or clear that concern.\n\n' + answer
    return dict(answer=answer,sources=sources,urgency=urgency,model='guided-photo-1',state=state,suggestions=suggestions)
