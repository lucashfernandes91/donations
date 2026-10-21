from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from apps.audit.models import AuditEntry
from apps.donations.models import Donation
from apps.donations.templatetags.table_sort import format_document, format_phone
from .models import Donor


class DonorModelTests(TestCase):
    def test_formats_cpf_and_cnpj_for_display(self):
        self.assertEqual(format_document('52998224725'), '529.982.247-25')
        self.assertEqual(format_document('04252011000110'), '04.252.011/0001-10')
        self.assertEqual(format_phone('51980250635'), '(51) 98025-0635')

    def test_cpf_is_optional(self):
        donor = Donor(name='Maria')

        donor.full_clean()

    def test_valid_cpf_is_normalized_when_saved(self):
        donor = Donor.objects.create(name='Maria', cpf='529.982.247-25')

        self.assertEqual(donor.cpf, '52998224725')

    def test_valid_cnpj_is_normalized_when_saved(self):
        donor = Donor.objects.create(name='Empresa', cpf='04252011000110')

        self.assertEqual(donor.cpf, '04252011000110')

    def test_invalid_cpf_is_rejected(self):
        donor = Donor(name='Maria', cpf='111.111.111-11')

        with self.assertRaises(ValidationError):
            donor.save()

    def test_invalid_cnpj_is_rejected(self):
        donor = Donor(name='Empresa', cpf='00.000.000/0000-00')

        with self.assertRaises(ValidationError):
            donor.save()


class DonorViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='operador', password='senha-segura'
        )
        self.donor = Donor.objects.create(name='Maria', cpf='52998224725')
        self.client.force_login(self.user)

    def assert_message(self, response, message):
        self.assertEqual([str(item) for item in get_messages(response.wsgi_request)], [message])

    def test_can_create_a_donor(self):
        response = self.client.post(
            reverse('donors:create'),
            {'name': 'João', 'phone': '51999999999', 'is_active': 'on'},
        )

        donor = Donor.objects.get(name='João')
        self.assertRedirects(response, reverse('donors:detail', args=[donor.pk]))
        self.assert_message(response, 'Doador cadastrado com sucesso.')

    def test_donor_form_accepts_a_cnpj(self):
        response = self.client.post(
            reverse('donors:create'),
            {'name': 'Empresa', 'cpf': '04.252.011/0001-10', 'is_active': 'on'},
        )

        donor = Donor.objects.get(name='Empresa')
        self.assertRedirects(response, reverse('donors:detail', args=[donor.pk]))
        self.assertEqual(donor.cpf, '04252011000110')

    def test_searches_by_name_only(self):
        other_donor = Donor.objects.create(name='Ana', cpf='11144477735')

        by_name = self.client.get(reverse('donors:list'), {'q': 'Maria'})
        by_cpf = self.client.get(reverse('donors:list'), {'q': '529.982.247-25'})

        self.assertContains(by_name, 'Maria')
        self.assertNotContains(by_name, 'Ana')
        self.assertContains(by_name, 'class="section-heading directory-heading"')
        self.assertContains(by_name, 'class="table-search-form"')
        self.assertContains(by_name, 'placeholder="Buscar por nome"')
        self.assertContains(by_name, 'data-donor-filter-picker')
        self.assertContains(by_name, 'data-donor-filter-input')
        self.assertContains(by_name, reverse('donors:search'))
        self.assertNotContains(by_name, 'Buscar por nome ou CPF')
        self.assertContains(by_name, 'class="sort-link is-active"')
        self.assertContains(by_name, 'sort=-name')
        self.assertContains(by_name, 'CPF/CNPJ')
        self.assertContains(by_name, '529.982.247-25')
        self.assertContains(
            by_name,
            f'<tr data-row-url="{reverse("donors:detail", args=[self.donor.pk])}" tabindex="0" aria-label="Ver doador Maria">',
        )
        self.assertNotContains(by_name, '<span class="status-badge')
        self.assertNotContains(by_name, '<span>Status</span>')
        self.assertNotContains(
            by_name,
            f'<td><a href="{reverse("donors:detail", args=[self.donor.pk])}">Maria</a></td>',
        )
        self.assertContains(by_name, '<td>-</td>')
        self.assertEqual(list(by_cpf.context['donors']), [])

    def test_donor_search_returns_name_matches_as_the_name_is_typed(self):
        matching_donor = Donor.objects.create(name='Mariana Souza', cpf='11144477735')
        Donor.objects.create(name='Carlos Lima')

        response = self.client.get(reverse('donors:search'), {'q': 'm'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()['results'],
            [
                {'id': self.donor.pk, 'name': 'Maria'},
                {'id': matching_donor.pk, 'name': 'Mariana Souza'},
            ],
        )

    def test_list_sorts_by_status(self):
        inactive = Donor.objects.create(name='Ana', is_active=False)

        response = self.client.get(reverse('donors:list'), {'sort': '-status'})

        self.assertEqual(list(response.context['donors'])[:2], [inactive, self.donor])

    def test_detail_shows_donation_history_and_total(self):
        self.user.is_staff = False
        self.user.save(update_fields=['is_staff'])
        Donation.objects.create(
            donor=self.donor,
            donation_date='2026-09-10',
            amount='35.00',
            donation_amount='20.00',
            contribution_amount='15.00',
            payment_method=Donation.PaymentMethod.PIX,
            created_by=self.user,
        )

        response = self.client.get(reverse('donors:detail', args=[self.donor.pk]))

        self.assertContains(response, '35,00')
        self.assertContains(response, 'CPF/CNPJ')
        self.assertContains(response, '529.982.247-25')
        for label in ['Data da doação', 'Doador', 'Valor da doação', 'Valor da contribuição']:
            self.assertContains(response, label)
        self.assertContains(response, '<td class="amount-breakdown-column">R$ 20,00</td>')
        self.assertContains(response, '<td class="amount-breakdown-column">R$ 15,00</td>')
        self.assertNotContains(response, '<th scope="col">Comprovante</th>')
        self.assertNotContains(response, '>Ações</th>')

    def test_donor_can_be_deleted_when_it_has_no_donations(self):
        donor = Donor.objects.create(name='Sem doações')
        self.assertEqual(self.client.get(reverse('donors:delete', args=[donor.pk])).status_code, 405)

        response = self.client.post(reverse('donors:delete', args=[donor.pk]))

        self.assertRedirects(response, reverse('donors:list'))
        self.assertFalse(Donor.objects.filter(pk=donor.pk).exists())
        self.assertTrue(AuditEntry.objects.filter(action='delete', object_id=donor.pk).exists())
        self.assert_message(response, 'Doador excluído com sucesso.')

    def test_donor_detail_shows_the_inline_delete_confirmation(self):
        response = self.client.get(reverse('donors:detail', args=[self.donor.pk]))

        self.assertContains(response, f'data-delete-dialog-open="donor-delete-dialog-{self.donor.pk}"')
        self.assertContains(response, f'id="donor-delete-dialog-{self.donor.pk}"')
        self.assertContains(response, reverse('donors:delete', args=[self.donor.pk]))

    def test_donor_with_donations_cannot_be_deleted(self):
        Donation.objects.create(
            donor=self.donor,
            donation_date='2026-09-10',
            amount='35.00',
            payment_method=Donation.PaymentMethod.PIX,
            created_by=self.user,
        )

        response = self.client.post(reverse('donors:delete', args=[self.donor.pk]))

        self.assertRedirects(response, reverse('donors:detail', args=[self.donor.pk]))
        self.assertTrue(Donor.objects.filter(pk=self.donor.pk).exists())
        self.assert_message(response, 'Doador não pode ser excluído porque possui doações vinculadas.')

    def test_responsibles_are_listed_separately_from_donors(self):
        responsible = Donor.objects.create(
            name='Responsável Maria', cpf='52998224725', phone='51980250635', is_responsible=True,
        )
        Donor.objects.create(name='Somente Doador')

        response = self.client.get(reverse('donors:responsible-list'), {'q': 'Maria'})

        self.assertContains(response, 'Responsáveis encontrados')
        self.assertContains(response, responsible.name)
        self.assertNotContains(response, 'Somente Doador')
        self.assertContains(response, reverse('donors:responsible-search'))
        self.assertContains(response, 'CPF/CNPJ')
        self.assertContains(response, '529.982.247-25')
        self.assertContains(response, '(51) 98025-0635')

    def test_responsible_can_be_created_and_has_a_dedicated_detail_page(self):
        response = self.client.post(
            reverse('donors:responsible-create'),
            {'name': 'Joana Responsável', 'phone': '51999999999', 'is_active': 'on'},
        )

        responsible = Donor.objects.get(name='Joana Responsável')
        self.assertTrue(responsible.is_responsible)
        self.assertRedirects(response, reverse('donors:responsible-detail', args=[responsible.pk]))
        self.assert_message(response, 'Responsável cadastrado com sucesso.')

    def test_responsible_search_returns_only_active_responsibles(self):
        responsible = Donor.objects.create(name='Maria Responsável', is_responsible=True)
        Donor.objects.create(name='Maria Doadora')
        Donor.objects.create(name='Maria Inativa', is_responsible=True, is_active=False)

        response = self.client.get(reverse('donors:responsible-search'), {'q': 'Maria'})

        self.assertEqual(response.json()['results'], [{'id': responsible.pk, 'name': responsible.name}])

    def test_responsible_detail_shows_the_linked_donations(self):
        self.user.is_staff = False
        self.user.save(update_fields=['is_staff'])
        responsible = Donor.objects.create(
            name='Joana Responsável', cpf='04252011000110', phone='51980250635', is_responsible=True,
        )
        donation = Donation.objects.create(
            donor=self.donor,
            responsible=responsible,
            donation_date='2026-09-10',
            amount='35.00',
            donation_amount='20.00',
            contribution_amount='15.00',
            payment_method=Donation.PaymentMethod.PIX,
            created_by=self.user,
        )

        response = self.client.get(reverse('donors:responsible-detail', args=[responsible.pk]))

        self.assertContains(response, donation.receipt_number)
        self.assertContains(response, 'CPF/CNPJ')
        self.assertContains(response, '04.252.011/0001-10')
        self.assertContains(response, '(51) 98025-0635')
        for label in ['Data da doação', 'Doador', 'Valor da doação', 'Valor da contribuição']:
            self.assertContains(response, label)
        self.assertContains(response, '<td class="amount-breakdown-column">R$ 20,00</td>')
        self.assertContains(response, '<td class="amount-breakdown-column">R$ 15,00</td>')
        self.assertNotContains(response, '<th scope="col">Comprovante</th>')
        self.assertNotContains(response, '>Ações</th>')

    def test_responsible_can_be_deleted_when_it_has_no_donations(self):
        responsible = Donor.objects.create(name='Sem vínculos', is_responsible=True)

        self.assertEqual(self.client.get(reverse('donors:responsible-delete', args=[responsible.pk])).status_code, 405)

        response = self.client.post(reverse('donors:responsible-delete', args=[responsible.pk]))

        self.assertRedirects(response, reverse('donors:responsible-list'))
        self.assertFalse(Donor.objects.filter(pk=responsible.pk).exists())
        self.assert_message(response, 'Responsável excluído com sucesso.')

    def test_responsible_detail_shows_the_inline_delete_confirmation(self):
        responsible = Donor.objects.create(name='Joana Responsável', is_responsible=True)

        response = self.client.get(reverse('donors:responsible-detail', args=[responsible.pk]))

        self.assertContains(response, f'data-delete-dialog-open="responsible-delete-dialog-{responsible.pk}"')
        self.assertContains(response, f'id="responsible-delete-dialog-{responsible.pk}"')
        self.assertContains(response, reverse('donors:responsible-delete', args=[responsible.pk]))


class DonorBackNavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username='navegacao', password='senha-segura'
        )
        cls.user.user_permissions.set(
            Permission.objects.filter(
                content_type__app_label__in=['donors', 'donations']
            )
        )
        cls.donor = Donor.objects.create(name='Doador')
        cls.responsible = Donor.objects.create(name='Responsável', is_responsible=True)

    def setUp(self):
        self.client.force_login(self.user)

    def test_donor_detail_returns_to_donor_list(self):
        response = self.client.get(reverse('donors:detail', args=[self.donor.pk]))

        self.assertContains(response, f'href="{reverse("donors:list")}">Voltar</a>')

    def test_responsible_detail_returns_to_responsible_list(self):
        response = self.client.get(
            reverse('donors:responsible-detail', args=[self.responsible.pk])
        )

        self.assertContains(
            response,
            f'href="{reverse("donors:responsible-list")}">Voltar</a>',
        )
