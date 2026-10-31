"""Small, versioned reference collection; not an LLM or validated clinical triage model."""
import re

VERSION = 'guided-care-1.0'
SOURCES = {
    'visit': {'id': 'visit', 'title': 'Merck Veterinary Manual — When to See a Veterinarian', 'url': 'https://www.merckvetmanual.com/multimedia/table/when-to-see-a-veterinarian', 'checked_on': '2026-10-07'},
    'emergency': {'id': 'emergency', 'title': 'Cornell University — Emergency and Critical Care', 'url': 'https://www.vet.cornell.edu/hospitals/services/emergency-and-critical-care-0', 'checked_on': '2026-10-07'},
    'skin': {'id': 'skin', 'title': 'Merck Veterinary Manual — Diagnosis of Skin Diseases in Small Animals', 'url': 'https://www.merckvetmanual.com/integumentary-system/integumentary-system-introduction/diagnosis-of-skin-diseases-in-small-animals', 'checked_on': '2026-10-07'},
}
TOPICS = [('sleep', 'Sleep or energy'), ('appetite', 'Eating or drinking'), ('skin', 'Itching or skin'), ('other', 'Another question')]
TOPIC_NAMES = dict(TOPICS)
EMERGENCY_DESCRIPTION = 'Trouble breathing; collapse or difficulty waking; seizures; serious injury or heavy bleeding; suspected poisoning; inability to pass urine; severe pain; repeated unsuccessful retching or a swollen painful belly.'
# A conservative flag, never an all-clear. Negation, timing, and other languages are not interpreted.
URGENT_WORDS = re.compile(r"\b(can'?t breathe|cannot breathe|difficulty breathing|struggling to breathe|unconscious|unresponsive|won'?t wake|not waking|collapsed|seizure|seizures|poison|poisoned|poisoning|hit by a car|heavy bleeding|can'?t pee|cannot urinate)\b", re.I)
MEDICATION_REQUEST = re.compile(r'\b(dose|dosage|prescribe|prescription|ibuprofen|paracetamol|acetaminophen)\b', re.I)

def immediate_reason(draft):
    if draft['safety'] == 'yes':
        return 'You reported a possible emergency sign.'
    if draft['safety'] == 'unsure':
        return 'You are unsure whether an emergency sign is present.'
    if URGENT_WORDS.search(draft['concern']):
        return 'Your text mentions a possible emergency sign. This simple guide cannot reliably interpret whether it is current, historical, or negated.'
    return ''

def assess(draft, answers):
    reason = immediate_reason(draft)
    if answers.get('activity') == 'extreme':
        reason = 'You reported extreme weakness or difficulty waking your pet.'
    if answers.get('intake') == 'none24':
        reason = 'You reported no food or water intake for at least 24 hours.'
    if reason:
        return make_result('urgent', 'Contact a veterinarian now', reason, 'Get immediate veterinary guidance. If an emergency sign is present, go to the nearest emergency veterinary service rather than waiting for this guide.', ['emergency', 'visit'], ['Tell the clinic what happened and when.', 'Bring the medication list and relevant pet records if available.'], ['emergency-screen'])
    if MEDICATION_REQUEST.search(draft['concern']):
        return make_result('limited', 'Ask your veterinarian about medication', 'Medication selection and dosing are outside this guide.', 'Share the question and your pet’s current medication list with your veterinarian. This guide cannot prescribe or check a dose.', [], ['Record the product name and what you want to ask your veterinarian.'], ['medication-boundary'])
    topic = draft['topic']
    if topic == 'other':
        return make_result('limited', 'This question needs a different resource', 'This version supports sleep/energy, appetite, and skin concerns only. It has not assessed this question.', 'Contact your veterinarian for health concerns. You can save your question as a record to discuss.', [], ['Keep your original question and any changes you have noticed.'], ['unsupported-topic'])
    source_ids = ['visit'] + (['skin'] if topic == 'skin' else [])
    if answers.get('intake') in ('reduced', 'none_recent'):
        return make_result('contact', 'Contact your veterinarian today', 'You reported reduced or absent intake. Lack of appetite warrants veterinary attention; do not wait for a 24-hour threshold to ask for advice.', 'Arrange veterinary advice within 24 hours, or sooner if your pet worsens. No intake for 24 hours or any emergency sign needs immediate attention.', source_ids, ['Note the last food and water intake and any other symptoms.'], ['reduced-intake'])
    if answers.get('changed') == 'yes' or answers.get('activity') == 'reduced' or answers.get('skin_signs') == 'yes':
        return make_result('contact', 'Contact your veterinarian today', 'You reported a change in behavior, reduced activity, or persistent skin signs. These observations need professional assessment.', 'Arrange veterinary advice within 24 hours. Use the emergency guidance immediately if a severe sign develops.', source_ids, topic_notes(topic), ['reported-change'])
    if 'unknown' in answers.values():
        return make_result('limited', 'More information is needed', 'Some observations are unknown, so the guide cannot assess your concern reliably.', 'Contact your veterinarian if you are worried or cannot check how your pet is doing. This result does not rule out illness.', source_ids, topic_notes(topic), ['unknown-observations'])
    return make_result('limited', 'Keep a clear record of the concern', 'Your answers do not establish a diagnosis or confirm that your pet is healthy. A sleep duration alone is not enough to assess illness.' if topic == 'sleep' else 'These answers are not enough to determine the cause or confirm that your pet is healthy.', 'Use these notes to discuss any continuing concern with your veterinarian. Seek help sooner for new or worsening signs.', source_ids, topic_notes(topic), ['limited-information'])

def topic_notes(topic):
    if topic == 'skin':
        return ['Record where the problem began, its duration, scratching or licking, and previous treatments.', 'Similar-looking skin problems can have different causes; examination and tests may be needed.']
    if topic == 'appetite':
        return ['Record recent food and water intake, behavior changes, and when the change began.']
    return ['Record sleep changes compared with your pet’s usual routine and how they behave when awake.']

def make_result(level, title, reason, action, sources, notes, rules):
    return {'level': level, 'title': title, 'reason': reason, 'action': action, 'notes': notes, 'sources': [dict(SOURCES[key]) for key in sources], 'rule_ids': rules, 'version': VERSION, 'mode': 'Guided care — reference-based questionnaire', 'limitation': 'Development prototype, not a diagnosis or a validated emergency screening service. No image model or language model was used.'}
