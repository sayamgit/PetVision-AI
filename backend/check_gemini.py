"""Explicit live smoke check; sends only invented pet examples, never owner records."""
import os
from types import SimpleNamespace
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from pets.gemini_engine import reply,configured,ChatUnavailable

if not configured():
    raise SystemExit('Setup pending: run configure-gemini.ps1 first. No API request sent.')
pet=SimpleNamespace(species='cat',age_years=3)
history=[SimpleNamespace(question='My cat has not eaten any food for five days',answer='Contact an emergency veterinarian now.')]
try:
    result=reply(pet,'there is so much hair fall',history)
except ChatUnavailable as error:
    raise SystemExit(str(error))
print('Live Gemini response (synthetic test only):')
print(result['answer'])
print('Urgency:',result['urgency'])
print('References:',', '.join(s['title'] for s in result['sources']))
print('Review the response for relevance and retained appetite concern; this is not clinical validation.')
