"""Single-instance deployment with explicit persistence and an HTTPS proxy."""
import os
from pathlib import Path
from urllib.parse import urlsplit
from django.core.exceptions import ImproperlyConfigured

# Set before loading local settings: production must never create a local secret.
if os.environ.get('PETVISION_DEBUG') != '0':
    raise ImproperlyConfigured('Production requires PETVISION_DEBUG=0.')
from .settings import *  # noqa: E402,F403

if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5:
    raise ImproperlyConfigured('Use a randomly generated PETVISION_SECRET_KEY of at least 50 characters.')
if not os.environ.get('PETVISION_ALLOWED_HOSTS') or '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('Set explicit PETVISION_ALLOWED_HOSTS; wildcard hosts are not allowed.')
if not PUBLIC_BASE_URL.startswith('https://') or urlsplit(PUBLIC_BASE_URL).hostname not in ALLOWED_HOSTS:
    raise ImproperlyConfigured('Set an HTTPS PETVISION_PUBLIC_BASE_URL whose hostname is in PETVISION_ALLOWED_HOSTS.')
storage_mode = os.environ.get('PETVISION_STORAGE_MODE', 'disk')
if storage_mode == 'supabase':
    from .cloud_storage import remote_persistence
    database, photo_storage = remote_persistence(os.environ)
    DATABASES = {'default': database}
    MEDIA_ROOT = ''
elif storage_mode == 'disk':
    if os.environ.get('RENDER'):
        raise ImproperlyConfigured('Render requires PETVISION_STORAGE_MODE=supabase; local data would be lost.')
    data_dir = Path(os.environ.get('PETVISION_DATA_DIR', ''))
    if not os.environ.get('PETVISION_DATA_DIR') or not data_dir.is_absolute() or not data_dir.is_dir():
        raise ImproperlyConfigured('PETVISION_DATA_DIR must point to an existing absolute persistent directory.')
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': data_dir/'db.sqlite3', 'OPTIONS': {'timeout': 20}}}
    MEDIA_ROOT = data_dir/'private-media'
    photo_storage = {'BACKEND': 'django.core.files.storage.FileSystemStorage'}
else:
    raise ImproperlyConfigured('PETVISION_STORAGE_MODE must be disk or supabase.')
MIDDLEWARE = [MIDDLEWARE[0], 'whitenoise.middleware.WhiteNoiseMiddleware', *MIDDLEWARE[1:]]
STORAGES = {'default': photo_storage,
            'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'}}
CSRF_TRUSTED_ORIGINS = [PUBLIC_BASE_URL]
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r'^healthz/$']
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_AGE = 60*60*24*7
SECURE_HSTS_SECONDS = 3600
# Do not assert ownership of all subdomains or request browser preload by default.
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
# Waitress sanitizes proxy headers and sets wsgi.url_scheme. Do not trust raw
# X-Forwarded-Proto in Django; configure the actual trusted proxy in serve.py.
SECURE_PROXY_SSL_HEADER = None
FILE_UPLOAD_PERMISSIONS = 0o600
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o700
