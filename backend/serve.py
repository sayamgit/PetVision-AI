"""Production entry point; one process shares the model and throttle cache."""
import os
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.production')
import django
django.setup()
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application
from waitress import serve

def main():
    call_command('check', deploy=True, fail_level='ERROR')
    call_command('verify_release')
    call_command('migrate', interactive=False)
    call_command('collectstatic', interactive=False, verbosity=0)
    options = {'listen':os.environ.get('PETVISION_BIND','0.0.0.0')+':'+os.environ.get('PORT','8000'),
               'threads':4,'max_request_body_size':3*1024*1024,'channel_timeout':120,
               'clear_untrusted_proxy_headers':True}
    proxy=os.environ.get('PETVISION_TRUSTED_PROXY','')
    if proxy:
        if proxy == '*' and os.environ.get('PETVISION_PROXY_ONLY_NETWORK') != '1':
            raise RuntimeError('Wildcard proxy trust requires PETVISION_PROXY_ONLY_NETWORK=1 and a proxy-only network.')
        options.update(trusted_proxy=proxy,trusted_proxy_count=int(os.environ.get('PETVISION_PROXY_COUNT','1')),
                       trusted_proxy_headers={'x-forwarded-for','x-forwarded-proto'})
    serve(get_wsgi_application(), **options)

if __name__ == '__main__':
    main()
