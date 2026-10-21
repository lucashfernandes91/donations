from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.audit.models import AuditEntry
from apps.donors.models import Donor

from .models import Donation


class DonationEntryFormTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='operador', password='senha-segura'
        )
        self.donor = Donor.objects.create(name='Maria Silva', cpf='52998224725')
        self.responsible = Donor.objects.create(name='Responsável Padrão', is_responsible=True)
        self.client.force_login(self.user)

    def payload(self, **overrides):
        data = {
            'donor': '',
            'new_donor_name': self.donor.name,
            'responsible': '',
            'new_responsible_name': self.responsible.name,
            'donation_date': '2026-09-11',
            'donation_amount': '10.25',
            'contribution_amount': '5.70',
            'payment_method': Donation.PaymentMethod.PIX,
            'notes': 'Entrada pelo formulário.',
        }
        data.update(overrides)
        return data

    def test_existing_donor_can_be_resolved_by_typed_name(self):
        response = self.client.post(reverse('donations:create'), self.payload())

        donation = Donation.objects.get()
        self.assertRedirects(response, reverse('donations:detail', args=[donation.pk]))
        self.assertEqual(donation.donor, self.donor)
        self.assertEqual(donation.donation_amount, Decimal('10.25'))
        self.assertEqual(donation.contribution_amount, Decimal('5.70'))
        self.assertEqual(donation.amount, Decimal('15.95'))
        self.assertEqual(AuditEntry.objects.filter(entity='donors.donor').count(), 0)

        response = self.client.get(reverse('donations:detail', args=[donation.pk]))
        self.assertContains(response, '<dt>Valor da doação</dt>')
        self.assertContains(response, '<dt>Valor da contribuição</dt>')
        self.assertNotContains(response, '<dt>Valor</dt>')

    def test_new_donation_form_offers_only_pix_and_bank_transfer(self):
        response = self.client.get(reverse('donations:create'))

        self.assertEqual(
            list(response.context['form'].fields['payment_method'].choices),
            [
                ('', 'Selecione uma opção'),
                ('pix', 'PIX'),
                ('bank_transfer', 'Transferência bancária'),
            ],
        )

    def test_donation_amount_can_be_filled_without_contribution_amount(self):
        response = self.client.post(
            reverse('donations:create'),
            self.payload(donation_amount='25.00', contribution_amount=''),
        )

        donation = Donation.objects.get()
        self.assertRedirects(response, reverse('donations:detail', args=[donation.pk]))
        self.assertEqual(donation.donation_amount, Decimal('25.00'))
        self.assertEqual(donation.contribution_amount, Decimal('0.00'))
        self.assertEqual(donation.amount, Decimal('25.00'))

        response = self.client.get(reverse('donations:detail', args=[donation.pk]))
        self.assertContains(response, '<dt>Valor da doação</dt>')
        self.assertNotContains(response, '<dt>Valor da contribuição</dt>')

    def test_contribution_amount_can_be_filled_without_donation_amount(self):
        response = self.client.post(
            reverse('donations:create'),
            self.payload(donation_amount='', contribution_amount='15.00'),
        )

        donation = Donation.objects.get()
        self.assertRedirects(response, reverse('donations:detail', args=[donation.pk]))
        self.assertEqual(donation.donation_amount, Decimal('0.00'))
        self.assertEqual(donation.contribution_amount, Decimal('15.00'))
        self.assertEqual(donation.amount, Decimal('15.00'))

        response = self.client.get(reverse('donations:detail', args=[donation.pk]))
        self.assertNotContains(response, '<dt>Valor da doação</dt>')
        self.assertContains(response, '<dt>Valor da contribuição</dt>')

    def test_contribution_requires_a_responsible(self):
        response = self.client.post(
            reverse('donations:create'),
            self.payload(new_responsible_name='', contribution_amount='15.00'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Busque ou informe o nome do responsável.')
        self.assertEqual(Donation.objects.count(), 0)

    def test_new_donor_is_created_inline_and_audited(self):
        response = self.client.post(
            reverse('donations:create'), self.payload(new_donor_name='Novo Doador')
        )

        donation = Donation.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(donation.donor.name, 'Novo Doador')
        self.assertEqual(AuditEntry.objects.filter(entity='donors.donor', action='create').count(), 1)
        self.assertEqual(AuditEntry.objects.filter(entity='donations.donation', action='create').count(), 1)

    def test_responsible_can_be_resolved_by_typed_name(self):
        responsible = Donor.objects.create(name='Joana Santos')

        response = self.client.post(
            reverse('donations:create'),
            self.payload(new_responsible_name=responsible.name),
        )

        donation = Donation.objects.get()
        self.assertRedirects(response, reverse('donations:detail', args=[donation.pk]))
        self.assertEqual(donation.responsible, responsible)
        self.assertContains(
            self.client.get(reverse('donations:detail', args=[donation.pk])),
            '<dt>Responsável</dt>',
        )

    def test_new_responsible_is_created_inline_and_audited(self):
        response = self.client.post(
            reverse('donations:create'),
            self.payload(new_responsible_name='Novo Responsável'),
        )

        donation = Donation.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(donation.responsible.name, 'Novo Responsável')
        self.assertEqual(AuditEntry.objects.filter(entity='donors.donor', action='create').count(), 1)

    def test_selected_donor_takes_precedence_over_typed_text(self):
        other_donor = Donor.objects.create(name='Outro Doador')

        self.client.post(
            reverse('donations:create'),
            self.payload(donor=other_donor.pk, new_donor_name='Nome alterado no campo'),
        )

        self.assertEqual(Donation.objects.get().donor, other_donor)
        self.assertFalse(Donor.objects.filter(name='Nome alterado no campo').exists())

    def test_donor_search_returns_matches_as_the_name_is_typed(self):
        matching_donor = Donor.objects.create(name='Mariana Souza', cpf='11144477735')
        Donor.objects.create(name='Carlos Lima')

        response = self.client.get(reverse('donations:donor-search'), {'q': 'm'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()['results'],
            [
                {'id': self.donor.pk, 'name': 'Maria Silva'},
                {'id': matching_donor.pk, 'name': 'Mariana Souza'},
            ],
        )

    def test_create_form_exposes_the_live_donor_search_endpoint(self):
        response = self.client.get(reverse('donations:create'))

        self.assertContains(response, reverse('donations:donor-search'))
        self.assertContains(response, reverse('donors:responsible-search'))
        self.assertContains(response, 'name="new_responsible_name"')
        self.assertContains(response, 'data-person-label="responsável"')
        self.assertContains(response, 'class="amount-grid"')
        self.assertContains(response, 'class="form-field"', count=5)

    def test_create_form_leaves_amounts_empty_and_shows_a_format_example(self):
        response = self.client.get(reverse('donations:create'))
        form = response.context['form']

        self.assertIsNone(form['donation_amount'].value())
        self.assertIsNone(form['contribution_amount'].value())
        self.assertContains(response, 'placeholder="Ex.: 100,00"', count=2)

    def test_create_form_uses_portuguese_empty_labels_for_selects(self):
        response = self.client.get(reverse('donations:create'))

        self.assertContains(response, 'Selecione uma opção', count=1)

    def test_amount_field_errors_stay_inside_their_grid_columns(self):
        response = self.client.post(
            reverse('donations:create'),
            self.payload(donation_amount='', contribution_amount=''),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<div class="amount-grid">')
        self.assertContains(response, 'Informe um valor de doação ou contribuição maior que zero.')
        self.assertNotContains(response, '<p>\n          <label for="id_donation_amount"')

    def test_amount_fields_accept_brazilian_decimal_format(self):
        form = self.client.get(reverse('donations:create')).context['form']

        self.assertEqual(form.fields['donation_amount'].clean('100,00'), Decimal('100.00'))
        self.assertEqual(form.fields['contribution_amount'].clean('1.234,56'), Decimal('1234.56'))

    def test_donor_suggestions_hidden_attribute_overrides_the_grid_layout(self):
        stylesheet = (Path(__file__).resolve().parents[2] / 'static' / 'css' / 'base.css')
        self.assertIn('.donor-suggestions[hidden] { display:none; }', stylesheet.read_text(encoding='utf-8'))

    def test_both_amounts_cannot_be_zero(self):
        response = self.client.post(
            reverse('donations:create'),
            self.payload(donation_amount='0.00', contribution_amount='0.00'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Informe um valor de doação ou contribuição maior que zero.')
        self.assertEqual(Donation.objects.count(), 0)
