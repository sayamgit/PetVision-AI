from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch
from django.db import OperationalError

class ReleaseTests(TestCase):
    def test_health_reports_database_failure_without_detail(self):
        response=self.client.get(reverse('health'))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.content,b'ok')
        with patch('pets.health.connection.cursor',side_effect=OperationalError('private details')):
            response=self.client.get(reverse('health'))
        self.assertEqual(response.status_code,503)
        self.assertNotContains(response,'private details',status_code=503)
        self.assertEqual(self.client.post(reverse('health')).status_code,405)

    def test_animation_is_scoped_to_login_and_preserves_form(self):
        response=self.client.get(reverse('login')+'?next=/care/')
        self.assertContains(response,'data-cat-scene')
        self.assertContains(response,'name="next" value="/care/"')
        self.assertContains(response,'name="csrfmiddlewaretoken"')
        self.assertContains(response,'name="password"')
        self.assertNotContains(self.client.get(reverse('signup')),'data-cat-scene')
