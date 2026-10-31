from pathlib import Path
import os,sys,tempfile,threading,subprocess,json,secrets
from wsgiref.simple_server import make_server,WSGIRequestHandler
stage=Path(__file__).resolve().parent
sys.path.insert(0,str(stage.parents[1]/'backend'))
os.environ.update(DJANGO_SETTINGS_MODULE='config.settings',PETVISION_DEBUG='1',PETVISION_SECRET_KEY=secrets.token_urlsafe(64),PETVISION_ALLOWED_HOSTS='localhost,127.0.0.1')
from django.conf import settings
with tempfile.TemporaryDirectory(prefix='petvision-qr-check-') as temporary:
    settings.DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':str(Path(temporary)/'qr-test.sqlite3')}}
    settings.MEDIA_ROOT=str(Path(temporary)/'media')
    settings.PUBLIC_BASE_URL=''
    import django
    django.setup()
    from django.core.management import call_command
    from django.contrib.auth import get_user_model
    from django.core.wsgi import get_wsgi_application
    from django.contrib.staticfiles.handlers import StaticFilesHandler
    from django.db import connections
    from pets.models import Pet,Sighting
    call_command('migrate',verbosity=0)
    owner=get_user_model().objects.create_user('qrcheckowner',password='QA-Only-Temporary-742!')
    pet=Pet.objects.create(owner=owner,name='QR verification cat',species='cat')
    class QuietHandler(WSGIRequestHandler):
        def log_message(self,*args): pass
    server=make_server('127.0.0.1',0,StaticFilesHandler(get_wsgi_application()),handler_class=QuietHandler)
    base=f'http://127.0.0.1:{server.server_port}'
    (Path(temporary)/'qr-check-fixture.json').write_text(json.dumps({'base':base,'public':f'{base}/p/{pet.public_token}/','pet':pet.pk}),encoding='utf-8')
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        subprocess.run([os.environ.get('NODE_BINARY','node'),str(stage/'check_qr.cjs'),str(Path(temporary)/'qr-check-fixture.json')],check=True)
        reports=list(Sighting.objects.order_by('created_at'))
        assert len(reports)==2,len(reports)
        assert str(reports[0].latitude)=='12.971600' and str(reports[0].longitude)=='77.594600'
        assert reports[1].latitude is None and reports[1].longitude is None
        print('Database verified: consented report has coordinates; denied report has no coordinates. Temporary fixture only.')
    finally:
        server.shutdown();worker.join();server.server_close();connections.close_all()
        (Path(temporary)/'qr-check-fixture.json').unlink(missing_ok=True)
