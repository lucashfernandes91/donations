from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AuthenticationViewTests(TestCase):
    def test_login_page_is_available(self):
        response = self.client.get(reverse('accounts:login'))

        self.assertContains(response, 'Entrar')
        self.assertContains(response, 'img/lar-oscar-vargas-luzia-catarina.png')
        self.assertContains(response, 'alt="Lar Oscar Vargas e Luzia Catarina"')
        self.assertNotContains(response, 'class="auth-lock"')
        self.assertNotContains(response, 'Acesso restrito')
        self.assertNotContains(response, 'Acesse sua conta')

    def test_logout_rejects_get_requests(self):
        response = self.client.get(reverse('accounts:logout'))

        self.assertEqual(response.status_code, 405)

    def test_staff_login_redirects_to_django_admin(self):
        user = get_user_model().objects.create_user(
            username='staff', password='senha-segura', is_staff=True,
        )

        response = self.client.post(
            reverse('accounts:login'),
            {'username': user.username, 'password': 'senha-segura'},
        )

        self.assertRedirects(response, reverse('admin:index'))
