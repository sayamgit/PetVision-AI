"""Explicit remote persistence for ephemeral hosts; no credentials in source."""
from urllib.parse import urlsplit
from django.core.exceptions import ImproperlyConfigured


def remote_persistence(env):
    def required(name):
        value = env.get(name, '')
        if not value:
            raise ImproperlyConfigured(f'Set {name} in the hosting secret settings.')
        return value

    host = required('PETVISION_DB_HOST')
    if any(char in host for char in '/@ \t\n'):
        raise ImproperlyConfigured('PETVISION_DB_HOST must be a hostname only.')
    try:
        port = int(env.get('PETVISION_DB_PORT', '5432'))
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise ImproperlyConfigured('PETVISION_DB_PORT must be a valid port.') from None
    options = {'sslmode': 'require', 'connect_timeout': 10,
               'options': '-c search_path=petvision', 'prepare_threshold': None}
    # Use the downloaded Supabase CA for full hostname verification when supplied.
    if env.get('PETVISION_DB_SSL_ROOT_CERT'):
        options.update(sslmode='verify-full', sslrootcert=env['PETVISION_DB_SSL_ROOT_CERT'])
    database = {'ENGINE': 'django.db.backends.postgresql',
                'HOST': host, 'PORT': port,
                'NAME': required('PETVISION_DB_NAME'),
                'USER': required('PETVISION_DB_USER'),
                'PASSWORD': required('PETVISION_DB_PASSWORD'),
                'CONN_MAX_AGE': 60, 'CONN_HEALTH_CHECKS': True,
                'DISABLE_SERVER_SIDE_CURSORS': True, 'OPTIONS': options}
    endpoint = required('PETVISION_S3_ENDPOINT')
    parsed = urlsplit(endpoint)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment):
        raise ImproperlyConfigured('PETVISION_S3_ENDPOINT must be a credential-free HTTPS endpoint.')
    bucket = required('PETVISION_S3_BUCKET')
    if '/' in bucket or bucket.strip() != bucket:
        raise ImproperlyConfigured('PETVISION_S3_BUCKET must be a bucket name only.')
    from botocore.config import Config
    storage = {'BACKEND': 'pets.storage.PrivatePhotoStorage', 'OPTIONS': {
        'access_key': required('PETVISION_S3_ACCESS_KEY_ID'),
        'secret_key': required('PETVISION_S3_SECRET_ACCESS_KEY'),
        'bucket_name': bucket, 'endpoint_url': endpoint,
        'region_name': required('PETVISION_S3_REGION'),
        'default_acl': None, 'file_overwrite': False, 'querystring_auth': True,
        'max_memory_size': 2 * 1024 * 1024,
        'object_parameters': {'CacheControl': 'private, no-store'},
        'client_config': Config(signature_version='s3v4', s3={'addressing_style': 'path'},
            connect_timeout=10, read_timeout=30, retries={'max_attempts': 2},
            request_checksum_calculation='when_required', response_checksum_validation='when_required'),
    }}
    return database, storage
