"""Synthetic full photo upload check inside an ephemeral, memory-limited container."""
import gc
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid
from io import BytesIO

sys.path.insert(0, '/app/backend')
os.environ.update(DJANGO_SETTINGS_MODULE='config.settings', PETVISION_DEBUG='1',
                  PETVISION_SECRET_KEY='container-only-synthetic-secret-not-a-deployment-key-123456789',
                  PETVISION_ALLOWED_HOSTS='testserver,localhost,127.0.0.1')
from django.conf import settings
temporary = tempfile.TemporaryDirectory(prefix='petvision-container-check-')
settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(Path(temporary.name)/'test.sqlite3')}}
settings.MEDIA_ROOT = str(Path(temporary.name)/'media')
import django
django.setup()
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from PIL import Image
from pets.image_engine import predict
import psycopg
from pets.storage import PrivatePhotoStorage
# Load production cloud-client libraries without sending a network request.
cloud_storage = PrivatePhotoStorage(access_key='synthetic', secret_key='synthetic',
    region_name='ap-southeast-1', endpoint_url='https://storage.invalid')
cloud_client = cloud_storage.connection.meta.client

def memory(label):
    result = {'phase': label}
    for name in ('memory.current','memory.peak','memory.events'):
        path = Path('/sys/fs/cgroup')/name
        if path.exists():
            content = path.read_text().strip()
            result[name] = round(int(content)/1024/1024,1) if content.isdigit() else content
    print(json.dumps(result), flush=True)

call_command('migrate', verbosity=0)
owner = get_user_model().objects.create_user('container-test-owner')
client = Client()
client.force_login(owner)
memory('django-loaded')
for species in ('cat','dog'):
    small = Image.new('RGB',(640,480),'gray')
    result = predict(small,species)
    small.close()
    assert len(result['ranked']) in (6,7)
    memory(species+'-loaded')

for species in ('cat','dog'):
    for size in ((640,480),(4000,3000)):
        buffer = BytesIO()
        image = Image.new('RGB',size,'gray')
        image.save(buffer,'JPEG',quality=85)
        image.close()
        gc.collect()
        response=client.post('/photos/', {'request_id':str(uuid.uuid4()), 'purpose':'concern',
            'species':species, 'image':SimpleUploadedFile('synthetic.jpg',buffer.getvalue(),content_type='image/jpeg')})
        assert response.status_code==302, (response.status_code,response.content[:120])
        memory(species+'-'+str(size))
        del response
        gc.collect()
print('Full cat/dog photo upload checks passed.',flush=True)
memory('finished')
for iteration in range(6):
    response=client.post('/photos/', {'request_id':str(uuid.uuid4()), 'purpose':'concern',
        'species':'cat', 'image':SimpleUploadedFile('synthetic.jpg',buffer.getvalue(),content_type='image/jpeg')})
    assert response.status_code==302,response.status_code
    del response
    memory('repeated-large-upload-'+str(iteration))
if os.environ.get('PETVISION_TEST_CONCURRENT') == '1':
    from concurrent.futures import ThreadPoolExecutor
    import threading
    clients = [Client() for _ in range(4)]
    for item in clients:
        item.force_login(owner)
    barrier = threading.Barrier(4)
    def submit(index):
        barrier.wait()
        response=clients[index].post('/photos/', {'request_id':str(uuid.uuid4()), 'purpose':'concern',
            'species':'cat', 'image':SimpleUploadedFile('synthetic.jpg',buffer.getvalue(),content_type='image/jpeg')})
        return response.status_code
    with ThreadPoolExecutor(max_workers=4) as pool:
        statuses = list(pool.map(submit,range(4)))
        assert sorted(statuses) == [302,503,503,503], statuses
        print('Concurrent upload statuses: '+str(statuses),flush=True)
    memory('four-concurrent-uploads')
