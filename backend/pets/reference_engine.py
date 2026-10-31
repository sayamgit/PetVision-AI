"""Deterministic retrieval and dialogue. Standard library only; no model or API."""
from copy import deepcopy
from .practical_care import local_steps
from difflib import get_close_matches
import re
from .reference_library import ENTRIES, VERSION, source_rows, EYE_NOTES

STOP = set('my pet cat dog kitten puppy he she it is has have a the to of for how what can should do does i his her their and with please about me this that'.split())
VOCAB = {w for e in ENTRIES for a in e['aliases'] for w in a.split() if len(w) >= 5}
BY_ID = {e['id']:e for e in ENTRIES}

def normalize(text):
    text = text.lower().replace('’', "'")
    for pattern, replacement in [
        (r'\bnot (?:eeting|eatin|eatiing)\b','not eating'),
        (r"\b(?:isn't|isnt|won't|wont|doesn't|doesnt|hasn't|hasnt|not been|will not|does not|has not)\s+(?:eat|eaten|eating)\b", 'not eating'),
        (r'\b(?:refus\w*|reject\w*)\s+(?:to eat|food|meals?)\b','refusing food'),
        (r'\b(?:no|poor|low|reduced|loss of|lost his|lost her) appetite\b','lost appetite'),
        (r'\beating (?:less|nothing)\b','not eating'),
        (r'\bnot eat\b','not eating'),
    ]:
        text = re.sub(pattern,replacement,text)
    return text

def tokens(text):
    result = []
    for word in re.findall(r'[a-z]+', normalize(text)):
        if word in STOP:
            continue
        # Spelling tolerance is only for retrieval, never the emergency screen.
        if len(word) >= 5 and word not in VOCAB:
            matched = get_close_matches(word, VOCAB, n=1, cutoff=.82)
            word = matched[0] if matched else word
        result.append(word)
    return set(result)

def rank(question, species):
    text = normalize(question)
    words = tokens(text)
    ranked = []
    for entry in ENTRIES:
        if entry['species'] not in (species,'both'):
            continue
        score = 0
        for alias in entry['aliases']:
            keys = tokens(alias)
            if keys and keys <= words:
                score = max(score, len(keys)*3)
            if re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',text):
                score = max(score,len(alias.split())*4)
        if entry['id'].startswith('appetite') and re.search(r'not eating|refusing food|lost appetite|stopped eating|off food|skipping meals',text):
            score += 15
        if score:
            ranked.append((score,entry))
    return sorted(ranked,key=lambda pair:pair[0],reverse=True)

RED_FLAGS = re.compile(r"\b(can'?t breathe|cannot breathe|not breathing|difficulty breathing|trouble breathing|breathing (?:trouble|difficulty|problems)|struggling to breathe|choking|unconscious|unresponsive|can'?t wake|cannot wake|won'?t wake|not waking|collapsed?|seizures?|convulsions?|heavy bleeding|bleeding heavily|hit by (?:a )?car|severe pain|pale gums|blue gums|can'?t (?:pee|urinate)|cannot (?:pee|urinate)|unable to (?:pee|urinate)|straining.{0,20}(?:no urine|nothing)|retching.{0,25}nothing|swollen painful (?:belly|abdomen)|poison(?:ed|ing)?|(?:ate|swallowed|ingested).{0,35}(?:medicine|medication|pills|paracetamol|ibuprofen|chocolate|grapes|raisins|lily|lilies|toxin))\b")

def emergency_mode(text):
    """Conservative flags, limited English negation; no absence-of-risk inference."""
    educational = False
    for clause in re.split(r'[.!?;\n]|\bbut\b',normalize(text)):
        for match in RED_FLAGS.finditer(clause):
            before = clause[:match.start()]
            after = clause[match.end():]
            # Negate only a nearby prefix, not a negative elsewhere in the sentence.
            if re.search(r"\b(?:no|not|without|never|isn't|isnt|is not|doesn't have|does not have)\s+(?:any\s+)?$",before):
                continue
            if re.search(r'\b(?:what if|if|in case|prevent|prevention|signs of|what is|what are)\b',before) or re.search(r'\b(?:last year|last month|years? ago|previously|used to)\b',clause):
                educational = True
            elif re.search(r'\b(?:not anymore|resolved|no longer)\b',after):
                educational = True
            else:
                return 'urgent'
    return 'education' if educational else ''

def duration(text):
    text = normalize(text)
    number_words = {'one':'1','two':'2','three':'3','four':'4','five':'5','six':'6','a':'1','an':'1'}
    for word,number in number_words.items():
        text = re.sub(r'\b'+word+r'(?=\s+(?:hours?|days?|weeks?)\b)',number,text)
    match = re.search(r'\b(\d+(?:\.\d+)?)\s*(hours?|hrs?|days?|weeks?)\b',text)
    if match:
        value = float(match[1]) * (168 if match[2].startswith('week') else 24 if match[2].startswith('day') else 1)
        return match[0],value
    match = re.search(r'\b(?:since )?(?:yesterday(?: morning| evening)?|this morning|last night|today)\b',text)
    return (match[0],None) if match else (None,None)

def package(answer, sources=(), urgency='general', state=None, suggestions=()):
    return dict(answer=answer,sources=source_rows(sources),urgency=urgency,model=VERSION,
                state=state or {},suggestions=list(suggestions))

def reply(pet,question,history):
    text = normalize(question)
    previous = deepcopy(getattr(history[-1],'state',{}) or {}) if history else {}
    previous.pop('care_steps', None)
    mode = emergency_mode(text)
    if mode:
        prefix = 'Your message mentions a possible emergency.' if mode == 'urgent' else 'If this happens, treat it as an emergency.'
        return package(prefix+' Contact a veterinarian or the nearest emergency veterinary clinic immediately. Do not wait for another chat reply. Tell the clinic what happened and when; take relevant pet records with you. This guide cannot assess severity remotely.', ['emergency'], 'urgent' if mode=='urgent' else 'uncertain', previous)
    if re.search(r'\b(dose|dosage|prescribe|medicine|medication|paracetamol|ibuprofen|acetaminophen|antibiotic)\b',text):
        return package('This guide cannot choose a medicine, check interactions, or calculate a dose. Ask your veterinarian with the product name and your pet’s details. If your pet has already swallowed a medicine unintentionally, contact veterinary care immediately.', ['emergency'], 'contact_vet',previous)
    if re.fullmatch(r'(hi|hello|hey|thanks|thank you)[! .]*',text):
        return package('You can ask about appetite, feeding, sleep, grooming, skin, toilet habits, or other topics in the reference library. Tell me what you have noticed.',state=previous,suggestions=['My pet is not eating food','How should I brush my pet?'])

    ranked = rank(text,pet.species)
    if not ranked and getattr(pet, 'photo_context', None):
        # Use the selected category only as a topic hint, never as a symptom.
        ranked = rank(pet.photo_context['selected_category'], pet.species)
    prior_id = previous.get('topic')
    pending = previous.get('pending')
    followup = bool(prior_id and (re.match(r'^(since|for \d|yes\b|no\b|not sure|normally|nothing|only in drops|not at all|drinking|not drinking|he is drinking|she is drinking|more than usual|normal routine)',text) or duration(text)[0]))
    if pending == 'other' and re.search(r'vomit|less playful|lower energy|no other',text):
        followup = True
    if pending == 'location' and re.search(r'\b(ears?|paws?|legs?|belly|back|face|tail|neck|spreading)\b',text):
        followup = True
    explicit_new = bool(re.search(r'\b(how|what|which|can i|should i|new question|another question)\b',text))
    if explicit_new:
        followup = False
    if prior_id and re.search(r'\b(?:now eating normally|eating again|appetite is back)\b',text):
        return package('You reported that eating has improved. That does not establish that the cause has resolved; update your veterinarian about the change if you have contacted them. You can start a new question below.', ['appetite'] if pet.species=='cat' else ['visit'], 'uncertain')
    # A specific fresh concern takes priority over context, except an answer to a pending observation.
    if followup and prior_id in BY_ID:
        entry = BY_ID[prior_id]
    elif ranked:
        top_score,entry = ranked[0]
        if len(ranked)>1 and ranked[1][0] == top_score and top_score>=4:
            choices = [e for s,e in ranked if s==top_score][:3]
            return package('I found more than one relevant topic. Which should we discuss first? '+', '.join(e['title'] for e in choices)+'.',state=previous,suggestions=[e['aliases'][0] for e in choices])
    else:
        return package('I could not find a reliable answer for that wording in this library. Please name the concern or describe what changed. Questions outside this guide’s coverage need another trusted resource. For a health concern, contact your veterinarian rather than relying on an unmatched answer.',urgency='uncertain',state=previous,suggestions=['My pet is not eating food','Sleep and energy','Itching skin'])

    continuing = entry['id']==prior_id
    state = previous if continuing else {'topic':entry['id'],'observations':{}}
    state['topic']=entry['id']
    obs = state.setdefault('observations',{})
    if continuing and pending and followup:
        # Store the owner's words; never turn an arbitrary reply into a confirmed symptom.
        if pending != 'duration' or duration(text)[0] or re.search(r'unsure|not sure|don.t know',text):
            obs[pending]=question[:250]
    time_text,hours = duration(text)
    if time_text:
        obs['duration']=time_text
        state['hours']=hours
    if re.search(r'\b(?:drinking|drink)\b',text) and entry['id'].startswith('appetite'):
        obs['drinking']=question[:250]
    if re.search(r'\b(no other changes|no other symptoms)\b',text):
        obs['other']=question[:250]

    # Follow-up answers can themselves reveal an emergency.
    if entry['id']=='urine' and continuing and followup and re.search(r'not at all|nothing|only in drops|no urine',text):
        return package('Passing no urine or only drops may mean difficulty urinating. Contact an emergency veterinarian immediately; do not wait for more chat questions.', ['emergency'],'urgent',state)
    if entry['id'].startswith('appetite') and state.get('hours') is not None and state['hours']>=24:
        return package('You reported an appetite problem lasting at least 24 hours. If no food has been eaten, immediate veterinary attention is needed. Contact your veterinarian now and describe exactly how much was eaten or drunk; do not wait longer for this chat.', ['visit','appetite'] if pet.species=='cat' else ['visit'],'urgent',state)

    answer = entry['answer']
    sources = list(entry['sources'])
    if entry['id'] == 'eyes' and getattr(pet, 'photo_context', None):
        for note in EYE_NOTES.get(pet.species, []):
            answer += '\n\n' + note['summary']
            sources.extend(note['source_ids'])
    if continuing and followup:
        answer = 'I have recorded your update for '+entry['title'].lower()+'. '+answer
    if obs:
        answer += '\n\nYour reported details (not a diagnosis):\n'+'\n'.join(k.replace('_',' ').capitalize()+': '+v for k,v in obs.items())
    next_question = next(((key,prompt) for key,prompt in entry['questions'] if key not in obs),None)
    state['pending']=next_question[0] if next_question else ''
    if next_question:
        answer += '\n\n'+next_question[1]
    else:
        answer += '\n\nYou can ask a new question here. For a more specific answer, open the reference below; this summary does not cover every situation.'
    suggestions = {'duration':['6 hours','Since yesterday','2 days','Not sure'], 'drinking':['Drinking normally','Drinking less','Not drinking at all'], 'other':['No other changes','Vomiting','Less playful'], 'urine':['Normally','Only in drops','Not at all'], 'change':['More than usual','Normal routine']}.get(state['pending'],[])
    steps, step_sources = local_steps(entry['id'], pet.species)
    if steps:
        state['care_steps'] = steps
    sources.extend(step_sources)
    return package(answer,sources,'contact_vet' if entry['clinical'] else 'general',state,suggestions)
