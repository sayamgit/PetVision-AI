"""Uploaded photos are served only by PetVision's authorization-aware views."""
from storages.backends.s3 import S3Storage


class PrivatePhotoStorage(S3Storage):
    def url(self, name, parameters=None, expire=None, http_method=None):
        raise ValueError('Use the authorized PetVision photo endpoint, not an object-store URL.')
