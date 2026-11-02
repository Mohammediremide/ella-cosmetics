import re
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from accounts.models import User

PW = 'Str0ng-pass!x'
NEW = 'An0ther-Strong#pw'


class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email='ada@example.com', password=PW, name='Ada')
        self.c = APIClient()

    def request_link(self, email='ada@example.com'):
        r = self.c.post('/api/auth/password-reset/', {'email': email}, format='json')
        self.assertEqual(r.status_code, 200)
        return r

    def parts(self):
        m = re.search(r'uid=([^&\s]+)&token=([^\s]+)', mail.outbox[-1].body)
        return m.group(1), m.group(2)

    def test_unknown_email_gets_same_answer_and_no_email(self):
        a = self.request_link('nobody@example.com').json()
        b = self.request_link().json()
        self.assertEqual(a, b)
        self.assertEqual(len(mail.outbox), 1)  # only the real account was emailed

    def test_token_never_in_response(self):
        r = self.request_link()
        uid, token = self.parts()
        self.assertNotIn(token, r.content.decode())

    def test_full_flow_and_single_use(self):
        self.request_link()
        uid, token = self.parts()
        ok = self.c.post('/api/auth/password-reset/confirm/', {'uid': uid, 'token': token, 'password': NEW}, format='json')
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(APIClient().post('/api/auth/login/', {'email': 'ada@example.com', 'password': NEW}, format='json').status_code, 200)
        self.assertEqual(APIClient().post('/api/auth/login/', {'email': 'ada@example.com', 'password': PW}, format='json').status_code, 400)
        again = self.c.post('/api/auth/password-reset/confirm/', {'uid': uid, 'token': token, 'password': 'Yet-An0ther#pw'}, format='json')
        self.assertEqual(again.status_code, 400)  # link already used

    def test_expired_token_rejected(self):
        self.request_link()
        uid, token = self.parts()
        with override_settings(PASSWORD_RESET_TIMEOUT=-1):
            r = self.c.post('/api/auth/password-reset/confirm/', {'uid': uid, 'token': token, 'password': NEW}, format='json')
        self.assertEqual(r.status_code, 400)

    def test_garbage_and_weak_password(self):
        self.assertEqual(self.c.post('/api/auth/password-reset/confirm/', {'uid': 'zz', 'token': 'bad', 'password': NEW}, format='json').status_code, 400)
        self.request_link()
        uid, token = self.parts()
        r = self.c.post('/api/auth/password-reset/confirm/', {'uid': uid, 'token': token, 'password': '123'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('password', r.json()['error']['fields'])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PW))  # unchanged

    def test_request_is_rate_limited(self):
        codes = [self.c.post('/api/auth/password-reset/', {'email': 'ada@example.com'}, format='json').status_code for _ in range(7)]
        self.assertEqual(codes[:5], [200] * 5)
        self.assertIn(429, codes[5:])

    def test_csrf_enforced(self):
        c = APIClient(enforce_csrf_checks=True)
        self.assertEqual(c.post('/api/auth/password-reset/', {'email': 'ada@example.com'}, format='json').status_code, 403)


class SessionTests(TestCase):
    def setUp(self):
        cache.clear()
        User.objects.create_user(email='ada@example.com', password=PW, name='Ada')

    def test_logout_invalidates_the_session_cookie(self):
        c = APIClient()
        c.post('/api/auth/login/', {'email': 'ada@example.com', 'password': PW}, format='json')
        old = c.cookies['sessionid'].value
        self.assertEqual(c.get('/api/auth/me/').status_code, 200)
        c.post('/api/auth/logout/')
        stolen = APIClient()
        stolen.cookies['sessionid'] = old  # replaying the pre-logout cookie must not work
        self.assertNotIn('id', stolen.get('/api/auth/me/').json())  # replayed cookie is dead

    def test_login_is_rate_limited(self):
        c = APIClient()
        codes = [c.post('/api/auth/login/', {'email': 'ada@example.com', 'password': 'wrong'}, format='json').status_code for _ in range(12)]
        self.assertIn(429, codes)

    def test_unauthenticated_error_code_for_frontend_session_expiry(self):
        r = APIClient().get('/api/cart/')
        self.assertEqual((r.status_code, r.json()['error']['code']), (403, 'not_authenticated'))

    def test_me_is_null_for_visitors_and_patch_needs_login(self):
        c = APIClient()
        r = c.get('/api/auth/me/'); self.assertEqual((r.status_code, r.json()), (200, {'authenticated': False}))
        self.assertEqual(c.patch('/api/auth/me/', {'name': 'x'}, format='json').status_code, 403)

    def test_health_endpoint(self):
        r = APIClient().get('/api/health/')
        self.assertEqual((r.status_code, r.json()), (200, {'status': 'ok'}))

    def test_password_hash_never_exposed(self):
        c = APIClient(); c.post('/api/auth/login/', {'email': 'ada@example.com', 'password': PW}, format='json')
        self.assertNotIn('pbkdf2', c.get('/api/auth/me/').content.decode())


class RegistrationTests(TestCase):
    def test_registration_requires_and_saves_phone_number(self):
        client = APIClient()
        data = {'name': 'Ada Lovelace', 'email': 'ada@example.com', 'password': PW}
        missing_phone = client.post('/api/auth/register/', data, format='json')
        self.assertEqual(missing_phone.status_code, 400)
        self.assertIn('phone', missing_phone.json()['error']['fields'])

        data['phone'] = '+234 801 234 5678'
        response = client.post('/api/auth/register/', data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['phone'], data['phone'])
        self.assertEqual(User.objects.get(email='ada@example.com').phone, data['phone'])
