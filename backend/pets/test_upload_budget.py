from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase
from .middleware import PhotoUploadBudgetMiddleware


class UploadBudgetTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def upload(self):
        return self.factory.post('/photos/', data=b'not decoded', content_type='multipart/form-data; boundary=test')

    def test_overlapping_upload_rejected_without_processing_and_get_still_works(self):
        calls = []
        inner = PhotoUploadBudgetMiddleware(lambda request: calls.append(request.method) or HttpResponse('ok'))
        def occupied(request):
            blocked = inner(self.upload())
            self.assertEqual(blocked.status_code, 503)
            self.assertEqual(blocked['Retry-After'], '3')
            self.assertIn('no-store', blocked['Cache-Control'])
            self.assertIn(b'Return to upload', blocked.content)
            self.assertEqual(inner(self.factory.get('/care/')).status_code, 200)
            return HttpResponse('done')
        self.assertEqual(PhotoUploadBudgetMiddleware(occupied)(self.upload()).status_code, 200)
        self.assertEqual(calls, ['GET'])
        self.assertEqual(inner(self.upload()).status_code, 200)

    def test_exception_releases_upload_slot(self):
        def fail(request):
            raise RuntimeError('synthetic failure')
        with self.assertRaises(RuntimeError):
            PhotoUploadBudgetMiddleware(fail)(self.upload())
        self.assertEqual(PhotoUploadBudgetMiddleware(lambda request: HttpResponse('ok'))(self.upload()).status_code, 200)
