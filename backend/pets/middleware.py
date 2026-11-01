from django.utils.cache import patch_cache_control

class PrivateResponseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        patch_cache_control(response, private=True, no_store=True)
        response['X-Robots-Tag'] = 'noindex, nofollow'
        return response



# Decoding several 12 MP photos at once can exhaust a small hosting instance.
# Keep the whole upload/validation/inference/save path inside one admission slot.
# Other requests (including viewing photos) continue normally.
import gc
from threading import BoundedSemaphore
from django.shortcuts import render

_photo_upload_slot = BoundedSemaphore(1)


class PhotoUploadBudgetMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != 'POST' or request.content_type != 'multipart/form-data':
            return self.get_response(request)
        if not _photo_upload_slot.acquire(blocking=False):
            response = render(request, 'images/upload_busy.html', status=503)
            response['Retry-After'] = '3'
            patch_cache_control(response, private=True, no_store=True)
            response['X-Robots-Tag'] = 'noindex, nofollow'
            return response
        try:
            return self.get_response(request)
        finally:
            # Forms can retain cycles holding decoded images until a later GC.
            # Reclaim them before admitting another large upload.
            gc.collect()
            _photo_upload_slot.release()
