from copy import deepcopy
from io import BytesIO
from pathlib import Path
import tempfile
import uuid
from unittest.mock import patch
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase,SimpleTestCase,override_settings
from django.urls import reverse
from .models import Pet,PhotoCheck,Conversation
from .image_forms import PhotoCheckForm
from .image_engine import square_image,ModelUnavailable

RESULT={'version':'curated-v2','species':'cat','model_sha256':'test','ranked':[{'label':'Normal-looking skin','score':80.0},{'label':'Fungal skin condition','score':15.0},{'label':'Scabies','score':5.0}], 'test_accuracy':60.4938,'test_count':81,'test_macro_f1':0.604}

def upload(size=(128,96)):
    buffer=BytesIO()
    image=Image.new('RGB',size,'red')
    exif=Image.Exif();exif[270]='PRIVATE IMAGE METADATA'
    image.save(buffer,'JPEG',exif=exif)
    return SimpleUploadedFile('private-name.jpg',buffer.getvalue(),content_type='image/jpeg')

class ImageInputTests(SimpleTestCase):
    def test_square_letterbox_and_orientation(self):
        image=Image.new('RGB',(400,100),'red')
        result=square_image(image)
        self.assertEqual(result.size,(224,224))
        self.assertEqual(result.getpixel((0,0)),(128,128,128))
        self.assertEqual(result.getpixel((112,112)),(255,0,0))
        image.getexif()[274]=6
        rotated=square_image(image)
        self.assertEqual(rotated.getpixel((112,0)),(255,0,0))
        self.assertEqual(rotated.getpixel((0,112)),(128,128,128))

    def test_bad_large_small_and_animated_inputs(self):
        inputs=[SimpleUploadedFile('fake.jpg',b'not an image'),upload((32,32)),SimpleUploadedFile('huge.jpg',b'x'*(2*1024*1024+1))]
        buffer=BytesIO();Image.new('RGB',(64,64)).save(buffer,'GIF',save_all=True,append_images=[Image.new('RGB',(64,64),'red')])
        inputs.append(SimpleUploadedFile('animation.gif',buffer.getvalue()))
        for item in inputs:
            form=PhotoCheckForm({'request_id':uuid.uuid4(),'purpose':'concern'},{'image':item})
            self.assertFalse(form.is_valid())
            self.assertIn('image',form.errors)

    def test_metadata_stripped_before_inference(self):
        form=PhotoCheckForm({'request_id':uuid.uuid4(),'purpose':'concern'},{'image':upload()})
        self.assertTrue(form.is_valid(),form.errors)
        self.assertFalse(form.cleaned_data['image'].getexif())
        self.assertEqual(form.cleaned_data['image'].mode,'RGB')

class PhotoFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.override=override_settings(MEDIA_ROOT=self.folder.name)
        self.override.enable();self.addCleanup(self.override.disable)
        self.owner=get_user_model().objects.create_user('photo-owner')
        self.other=get_user_model().objects.create_user('photo-other')
        self.pet=Pet.objects.create(owner=self.owner,name='Miso',species='cat')
        self.client.force_login(self.owner)

    def send(self,**kwargs):
        return self.client.post(reverse('photo_start',args=[self.pet.pk]),{'request_id':uuid.uuid4(),'purpose':'concern','image':upload(),'observations':'Itching for two days',**kwargs})

    def create(self):
        with patch('pets.image_views.predict',return_value=deepcopy(RESULT)):
            self.assertEqual(self.send().status_code,302)
        return PhotoCheck.objects.latest('created_at')

    def test_species_selection_and_saved_private_result(self):
        with patch('pets.image_views.predict',return_value=deepcopy(RESULT)) as predict:
            self.send()
            self.assertEqual(predict.call_args.args[1],'cat')
        record=PhotoCheck.objects.get()
        with record.image.open() as file,Image.open(file) as image:
            self.assertFalse(image.getexif())
            self.assertEqual(image.format,'JPEG')
        page=self.client.get(reverse('photo_result',args=[record.pk]))
        self.assertContains(page,'does not establish that the animal is healthy')
        self.assertContains(page,'not the probability')
        self.assertContains(page,'Itching for two days')
        self.pet.species='dog';self.pet.save()
        with patch('pets.image_views.predict',return_value=deepcopy(RESULT)) as predict:
            self.send()
            self.assertEqual(predict.call_args.args[1],'dog')

    def test_split_scores_are_inconclusive_without_rewriting_model_results(self):
        record=self.create()
        record.result['ranked']=[{'label':'Scabies','score':47.2},{'label':'Normal-looking skin','score':32.8},{'label':'Ear Mites','score':20.0}]
        record.save()
        original=deepcopy(record.result)
        page=self.client.get(reverse('photo_result',args=[record.pk]))
        self.assertContains(page,'<h2>Inconclusive image match</h2>')
        self.assertContains(page,'Highest-ranked category: Scabies')
        self.assertContains(page,'data-score="47.2"')
        self.assertContains(page,'remaining 52.8%')
        record.refresh_from_db()
        self.assertEqual(record.result,original)
        record.result['ranked'][0]['score']=98.7
        self.assertFalse(record.has_split_scores)
        self.assertEqual(record.display_label,'Scabies')

    def test_owner_isolation_and_no_public_qr_leak(self):
        record=self.create()
        public=self.client.get(reverse('public_pet',args=[self.pet.public_token]))
        self.assertNotContains(public,'Itching for two days')
        self.assertNotContains(public,str(record.pk))
        self.client.force_login(self.other)
        for name in ['photo_result','photo_image']:
            self.assertEqual(self.client.get(reverse(name,args=[record.pk])).status_code,404)
        self.assertEqual(self.send().status_code,404)
        self.assertEqual(self.client.post(reverse('photo_delete',args=[record.pk]),{'confirm':'yes'}).status_code,404)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('photo_image',args=[record.pk])).status_code,302)

    def test_invalid_photo_and_model_failure_create_no_record(self):
        with patch('pets.image_views.predict') as predict:
            self.send(image=SimpleUploadedFile('bad.jpg',b'bad'))
            predict.assert_not_called()
        with patch('pets.image_views.predict',side_effect=ModelUnavailable('Photo analysis is temporarily unavailable.')):
            self.assertContains(self.send(),'temporarily unavailable')
        self.assertEqual(PhotoCheck.objects.count(),0)
        self.assertFalse(list(Path(self.folder.name).rglob('*.jpg')))

    def test_double_submit_is_idempotent(self):
        key=uuid.uuid4()
        with patch('pets.image_views.predict',return_value=deepcopy(RESULT)) as predict:
            self.send(request_id=key);self.send(request_id=key)
            self.assertEqual(predict.call_count,1)
        self.assertEqual(PhotoCheck.objects.count(),1)

    def test_delete_confirmation_and_file_removal(self):
        record=self.create();path=record.image.path
        conversation=Conversation.objects.create(pet=self.pet,photo_check=record)
        url=reverse('photo_delete',args=[record.pk])
        self.assertEqual(self.client.get(url).status_code,405)
        self.assertEqual(self.client.post(url).status_code,400)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(url,{'confirm':'yes'}).status_code,302)
        self.assertFalse(Path(path).exists())
        conversation.refresh_from_db();self.assertIsNone(conversation.photo_check)

    def test_chat_handoff_is_editable_and_does_not_call_google(self):
        record=self.create()
        url=reverse('new_pet_chat',args=[self.pet.pk])+'?photo='+str(record.pk)
        with patch('pets.chat_views.gemini_engine.reply') as cloud:
            self.assertContains(self.client.get(url),'Your photo and model percentages stay on the app server')
            response=self.client.post(url,{'start_ack':'yes','backend':'gemini'})
            self.assertEqual(response.status_code,302)
            chat=Conversation.objects.get()
            page=self.client.get(response.url)
            self.assertEqual(page.context['draft_question'], '')
            self.assertEqual(chat.subject.photo_context['observations'],'Itching for two days')
            self.assertEqual(chat.turns.count(),0)
            cloud.assert_not_called()
        self.client.force_login(self.other)
        otherpet=Pet.objects.create(owner=self.other,name='Other',species='dog')
        self.assertEqual(self.client.get(reverse('new_pet_chat',args=[otherpet.pk])+'?photo='+str(record.pk)).status_code,404)
