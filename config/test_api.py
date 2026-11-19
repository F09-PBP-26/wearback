from django.conf import settings
from django.contrib.auth import get_user_model
from django.middleware.csrf import get_token
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import get_resolver, path
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.test import APIClient


SMOKE_URL = '/api/v1/_smoke/'


@api_view(['GET', 'POST'])
def smoke_view(request):
    get_token(request)
    return Response({'user_id': request.user.pk})


urlpatterns = [path('api/v1/_smoke/', smoke_view)]


class APIURLTests(SimpleTestCase):
    def test_version_one_urlconf_is_mounted(self):
        prefix, resolver = get_resolver('config.urls').namespace_dict['api_v1']
        self.assertEqual(prefix, 'api/v1/')
        self.assertEqual(resolver.urlconf_name.__name__, 'config.api_urls')


@override_settings(ROOT_URLCONF=__name__)
class APIAuthenticationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username='api-member', email='api-member@example.com',
        )

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)

    def test_anonymous_requests_are_denied_by_default(self):
        response = self.client.get(SMOKE_URL, HTTP_ACCEPT='application/json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('detail', response.json())

    def test_signed_in_session_can_read_json(self):
        self.client.force_login(self.user)

        response = self.client.get(SMOKE_URL, HTTP_ACCEPT='application/json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'user_id': self.user.pk})

    def test_session_authenticated_post_requires_csrf_header(self):
        self.client.force_login(self.user)
        self.client.get(SMOKE_URL)
        csrf_token = self.client.cookies[settings.CSRF_COOKIE_NAME].value

        denied = self.client.post(SMOKE_URL, {}, format='json')
        allowed = self.client.post(
            SMOKE_URL, {}, format='json', HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('CSRF', denied.json()['detail'])
        self.assertEqual(allowed.status_code, status.HTTP_200_OK)
