from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from config.cloud_storage import remote_persistence, apply_render_origin_defaults
from .storage import PrivatePhotoStorage


class CloudConfigTests(SimpleTestCase):
    def setUp(self):
        self.env = {'PETVISION_DB_HOST': 'session-pooler.example.com',
            'PETVISION_DB_USER': 'postgres.example', 'PETVISION_DB_NAME': 'postgres',
            'PETVISION_DB_PASSWORD': 'synthetic:pass@word/with#symbols',
            'PETVISION_S3_ENDPOINT': 'https://example.storage.supabase.co/storage/v1/s3',
            'PETVISION_S3_REGION': 'ap-southeast-1', 'PETVISION_S3_BUCKET': 'petvision-photos',
            'PETVISION_S3_ACCESS_KEY_ID': 'synthetic-access',
            'PETVISION_S3_SECRET_ACCESS_KEY': 'synthetic-secret'}

    def test_remote_configuration_keeps_password_and_private_storage(self):
        database, storage = remote_persistence(self.env)
        self.assertEqual(database['PASSWORD'], self.env['PETVISION_DB_PASSWORD'])
        self.assertEqual(database['OPTIONS']['sslmode'], 'require')
        self.assertEqual(database['OPTIONS']['options'], '-c search_path=petvision')
        self.assertIsNone(database['OPTIONS']['prepare_threshold'])
        self.assertIsNone(storage['OPTIONS']['default_acl'])
        self.assertFalse(storage['OPTIONS']['file_overwrite'])
        self.assertTrue(storage['OPTIONS']['querystring_auth'])
        self.assertEqual(storage['OPTIONS']['client_config'].s3['addressing_style'], 'path')

    def test_missing_fields_fail_without_exposing_values(self):
        for name in self.env:
            env = {k: v for k, v in self.env.items() if k != name}
            with self.assertRaises(ImproperlyConfigured) as raised:
                remote_persistence(env)
            self.assertNotIn('synthetic:pass', str(raised.exception))

    def test_insecure_or_credentialed_endpoint_rejected(self):
        for endpoint in ('http://storage.example.com', 'https://user:secret@storage.example.com',
                         'https://storage.example.com?token=secret'):
            with self.assertRaises(ImproperlyConfigured):
                remote_persistence({**self.env, 'PETVISION_S3_ENDPOINT': endpoint})

    def test_ca_enables_hostname_verification(self):
        database, _ = remote_persistence({**self.env, 'PETVISION_DB_SSL_ROOT_CERT': '/etc/ssl/supabase.crt'})
        self.assertEqual(database['OPTIONS']['sslmode'], 'verify-full')

    def test_direct_photo_urls_are_not_available(self):
        storage = PrivatePhotoStorage(access_key='synthetic', secret_key='synthetic')
        with self.assertRaises(ValueError):
            storage.url('private-photo.jpg')


class RenderOriginTests(SimpleTestCase):
    def test_assigned_hostname_is_used_without_a_manual_url(self):
        env = {'RENDER': 'true', 'RENDER_EXTERNAL_HOSTNAME': 'petvision-test.onrender.com'}
        apply_render_origin_defaults(env)
        self.assertEqual(env['PETVISION_PUBLIC_BASE_URL'], 'https://petvision-test.onrender.com')
        self.assertEqual(env['PETVISION_ALLOWED_HOSTS'], 'petvision-test.onrender.com,localhost,127.0.0.1')

    def test_explicit_custom_domain_is_preserved(self):
        env = {'RENDER': 'true', 'RENDER_EXTERNAL_HOSTNAME': 'petvision-test.onrender.com',
            'PETVISION_PUBLIC_BASE_URL': 'https://pets.example.com', 'PETVISION_ALLOWED_HOSTS': 'pets.example.com'}
        apply_render_origin_defaults(env)
        self.assertEqual(env['PETVISION_PUBLIC_BASE_URL'], 'https://pets.example.com')
        self.assertEqual(env['PETVISION_ALLOWED_HOSTS'], 'pets.example.com')

    def test_untrusted_host_and_non_render_environment(self):
        with self.assertRaises(ImproperlyConfigured):
            apply_render_origin_defaults({'RENDER': 'true', 'RENDER_EXTERNAL_HOSTNAME': 'evil.example.com'})
        env = {'RENDER_EXTERNAL_HOSTNAME': 'petvision-test.onrender.com'}
        apply_render_origin_defaults(env)
        self.assertNotIn('PETVISION_PUBLIC_BASE_URL', env)
