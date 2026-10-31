"""Brief original summaries from individually checked veterinary references.
PetMD hot spots: Heather Hoffmann DVM, reviewed Sandra Mitchell DVM DABVP (2024-06-25).
PetMD dog eye injuries: Sandra Mitchell DVM DABVP (2024-02-09).
VCA collars: Courtney Barnes DVM, Ryan Llera DVM, Ernest Ward DVM.
AVMA first aid brochure: 2025 edition. All links checked 2026-10-19.
No full articles, product recommendations or medication instructions are stored.
"""
from copy import deepcopy

DOG_SKIN = {
 'do_now': ['If your dog is licking or chewing an irritated area, a properly fitted recovery cone can help prevent further self-injury. Supervise them while they adjust and ask the clinic for fitting help if needed.'],
 'avoid': ['Do not let the cone restrict breathing or swallowing. Avoid unsupervised outdoor roaming while wearing it.'],
 'watch_for': ['Seek veterinary attention promptly for an enlarging area, persistent bleeding, discharge, odor or pain, or if you cannot prevent further licking.'],
}
NOTES = [
 {'species':'dog','topic':'Protecting irritated skin while arranging care','source_ids':['petmd-hotspots','vca-cone'],
  'summary':'Hot spots can worsen with repeated licking, chewing or scratching. A properly fitted recovery cone can limit further injury; supervise the dog as it adjusts and ask the clinic for help if it cannot be fitted safely. It must not interfere with breathing or swallowing, and dogs wearing it should not roam outdoors unsupervised. A cone protects the area but does not treat its cause. An enlarging lesion, persistent bleeding, discharge, odor, pain or uncontrollable licking warrants prompt veterinary assessment. These signs do not confirm that a lesion is a hot spot.'},
 {'species':'dog','topic':'Protecting an injured eye','source_ids':['petmd-eye-injury','vca-cone'],
  'summary':'An eye injury needs prompt veterinary examination. Pawing and rubbing can worsen the injury; a correctly fitted recovery cone can help prevent rubbing while arranging care, with supervision and fitting assistance if needed. Do not delay veterinary care to try home treatment. Severe trauma or an eye displaced from its socket is an emergency.'},
 {'species':'both','topic':'Practical steps in specific emergencies','source_ids':['avma-firstaid'],
  'summary':'For suspected poisoning, contact veterinary emergency care immediately and keep the product container available; do not induce vomiting or give medication unless a veterinarian or poison-control professional directs it. During a seizure, clear nearby hazards, do not restrain the animal or place hands near its mouth, and time the event if safe. Injured animals may bite: keep your face away from their mouth, and limit movement during transport using a ventilated carrier where appropriate. Do not pull an embedded object from a wound. These steps support, not replace, emergency veterinary care.'},
]

def notes_for(species):
    return [{k:v for k,v in note.items() if k != 'species'} for note in NOTES if note['species'] in ('both',species)]

def local_steps(topic, species):
    if topic == 'skin' and species == 'dog':
        return deepcopy(DOG_SKIN), ['petmd-hotspots','vca-cone']
    return {}, []
