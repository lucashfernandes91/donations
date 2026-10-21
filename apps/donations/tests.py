from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from apps.donors.models import Donor

from .models import Donation
from .receipts import amount_to_words, generate_receipt_pdf, receipt_data


class DonationModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='operador', password='senha-segura'
        )
        self.donor = Donor.objects.create(name='Maria')

    def test_generates_a_unique_receipt_number(self):
        first = self.create_donation()
        second = self.create_donation()

        self.assertTrue(first.receipt_number.startswith('REC-'))
        self.assertNotEqual(first.receipt_number, second.receipt_number)

    def test_amount_must_be_greater_than_zero(self):
        donation = Donation(
            donor=self.donor,
            donation_date=date.today(),
            amount=Decimal('0.00'),
            payment_method=Donation.PaymentMethod.PIX,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            donation.save()

    def create_donation(self, **overrides):
        values = {
            'donor': self.donor,
            'donation_date': date.today(),
            'amount': Decimal('25.00'),
            'payment_method': Donation.PaymentMethod.PIX,
            'created_by': self.user,
        }
        values.update(overrides)
        return Donation.objects.create(**values)


class DonationViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='operador', password='senha-segura'
        )
        self.donor = Donor.objects.create(name='Maria')
        self.client.force_login(self.user)

    def test_can_create_a_donation_and_record_the_user(self):
        response = self.client.post(
            reverse('donations:create'),
            {
                'donor': self.donor.pk,
                'donation_date': '2026-09-10',
                'donation_amount': '50.00',
                'contribution_amount': '0.00',
                'payment_method': Donation.PaymentMethod.PIX,
            },
        )

        donation = Donation.objects.get()
        self.assertEqual(donation.created_by, self.user)
        self.assertRedirects(response, reverse('donations:detail', args=[donation.pk]))

    def test_edit_records_the_user_who_updated_the_donation(self):
        donation = Donation.objects.create(
            donor=self.donor,
            donation_date='2026-09-10',
            amount='50.00',
            payment_method=Donation.PaymentMethod.PIX,
            created_by=self.user,
        )
        editor = get_user_model().objects.create_superuser(
            username='editor', password='senha-segura'
        )
        self.client.force_login(editor)

        response = self.client.post(
            reverse('donations:update', args=[donation.pk]),
            {
                'donor': self.donor.pk,
                'donation_date': '2026-09-10',
                'donation_amount': '75.00',
                'contribution_amount': '0.00',
                'payment_method': Donation.PaymentMethod.PIX,
            },
        )

        donation.refresh_from_db()
        self.assertEqual(donation.updated_by, editor)
        self.assertEqual(donation.amount, Decimal('75.00'))
        self.assertRedirects(response, reverse('donations:detail', args=[donation.pk]))

    def test_detail_page_hides_status_and_keeps_remaining_information(self):
        donation = Donation.objects.create(
            donor=self.donor,
            donation_date='2026-09-10',
            amount='50.00',
            payment_method=Donation.PaymentMethod.PIX,
            notes='Referência do modal.',
            created_by=self.user,
        )

        response = self.client.get(reverse('donations:detail', args=[donation.pk]))

        self.assertNotContains(response, '<dt>Status</dt>')
        self.assertContains(response, '<dt>Valor da doação</dt>')
        self.assertNotContains(response, '<dt>Valor</dt>')
        for label in ['Doador', 'Forma de recebimento']:
            self.assertContains(response, label)
        self.assertNotContains(response, '<dt>Cadastrada por</dt>')
        self.assertNotContains(response, '<dt>Criada em</dt>')
        self.assertNotContains(response, '<dt>Atualizada em</dt>')
        self.assertContains(response, 'Referência do modal.')

    @patch('apps.donations.views.generate_receipt_pdf', return_value=b'%PDF-1.7')
    def test_receipt_is_served_inline(self, receipt_pdf):
        donation = Donation.objects.create(
            donor=self.donor,
            donation_date='2026-09-10',
            amount='50.00',
            payment_method=Donation.PaymentMethod.PIX,
            created_by=self.user,
        )

        response = self.client.get(reverse('donations:receipt', args=[donation.pk, 'donation']))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('inline;', response['Content-Disposition'])
        receipt_pdf.assert_called_once_with(donation, 'donation')

    @patch('apps.donations.views.generate_receipt_pdf', return_value=b'%PDF-1.7')
    def test_receipt_can_be_downloaded(self, receipt_pdf):
        donation = Donation.objects.create(
            donor=self.donor,
            donation_date='2026-09-10',
            amount='50.00',
            payment_method=Donation.PaymentMethod.PIX,
            created_by=self.user,
        )

        response = self.client.get(reverse('donations:receipt-download', args=[donation.pk, 'donation']))

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        receipt_pdf.assert_called_once_with(donation, 'donation')

    def test_receipt_fields_use_donation_data(self):
        donation = Donation.objects.create(
            donor=self.donor,
            donation_date='2026-09-13',
            amount='150.75',
            donation_amount='150.75',
            contribution_amount='0.00',
            payment_method=Donation.PaymentMethod.PIX,
            created_by=self.user,
        )

        self.assertEqual(
            amount_to_words(donation.amount),
            'cento e cinquenta reais e setenta e cinco centavos',
        )
        self.assertEqual(receipt_data(donation, 'donation')['reference'], 'doação')
        self.assertTrue(generate_receipt_pdf(donation, 'donation').startswith(b'%PDF'))

    def test_receipt_reference_identifies_contribution(self):
        responsible = Donor.objects.create(name='Responsável')
        donation = Donation.objects.create(
            donor=self.donor,
            responsible=responsible,
            donation_date='2026-09-13',
            amount='25.00',
            donation_amount='0.00',
            contribution_amount='25.00',
            payment_method=Donation.PaymentMethod.PIX,
            created_by=self.user,
        )

        self.assertEqual(receipt_data(donation, 'contribution')['reference'], 'contribuição')


class DonationDetailPageActionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username='detalhes-doacao', password='senha-segura'
        )
        cls.user.user_permissions.set(
            Permission.objects.filter(
                content_type__app_label__in=['donations', 'donors']
            )
        )
        cls.donor = Donor.objects.create(name='Doador')
        cls.responsible = Donor.objects.create(name='Responsável', is_responsible=True)

    def setUp(self):
        self.client.force_login(self.user)

    def test_detail_places_receipt_print_icons_beside_each_existing_amount(self):
        donation = Donation.objects.create(
            donor=self.donor,
            responsible=self.responsible,
            created_by=self.user,
            donation_date='2026-10-19',
            amount='150.00',
            donation_amount='100.00',
            contribution_amount='50.00',
            payment_method=Donation.PaymentMethod.PIX,
        )

        response = self.client.get(reverse('donations:detail', args=[donation.pk]))

        self.assertContains(response, 'aria-label="Imprimir recibo da doação"')
        self.assertContains(response, 'aria-label="Imprimir recibo da contribuição"')
        self.assertContains(
            response,
            reverse('donations:receipt', args=[donation.pk, 'donation']),
        )
        self.assertContains(
            response,
            reverse('donations:receipt', args=[donation.pk, 'contribution']),
        )
        self.assertNotContains(
            response,
            reverse('donations:receipt-download', args=[donation.pk, 'donation']),
        )
        self.assertNotContains(
            response,
            reverse('donations:receipt-download', args=[donation.pk, 'contribution']),
        )

    def test_detail_title_uses_the_numbers_printed_on_each_receipt(self):
        cases = (
            ('100.00', '0.00'),
            ('0.00', '50.00'),
            ('100.00', '50.00'),
        )

        for donation_amount, contribution_amount in cases:
            with self.subTest(
                donation_amount=donation_amount,
                contribution_amount=contribution_amount,
            ):
                donation = Donation.objects.create(
                    donor=self.donor,
                    responsible=self.responsible,
                    created_by=self.user,
                    donation_date='2026-10-19',
                    amount='150.00',
                    donation_amount=donation_amount,
                    contribution_amount=contribution_amount,
                    payment_method=Donation.PaymentMethod.PIX,
                )
                titles = []
                if donation.donation_receipt_number is not None:
                    titles.append(f'Doação nº {donation.donation_receipt_number}')
                if donation.contribution_receipt_number is not None:
                    titles.append(f'Contribuição nº {donation.contribution_receipt_number}')
                expected_title = ' / '.join(titles)

                response = self.client.get(reverse('donations:detail', args=[donation.pk]))

                self.assertContains(response, f'<h1>{expected_title}</h1>', html=True)
                self.assertContains(
                    response,
                    f'<title>{expected_title} | Gestão de Doações</title>',
                    html=True,
                )
                self.assertNotContains(response, f'<h1>Doação {donation.receipt_number}</h1>')

    def test_detail_keeps_only_management_and_back_buttons_in_the_header(self):
        donation = Donation.objects.create(
            donor=self.donor,
            created_by=self.user,
            donation_date='2026-10-19',
            amount='100.00',
            donation_amount='100.00',
            contribution_amount='0.00',
            payment_method=Donation.PaymentMethod.PIX,
        )

        response = self.client.get(reverse('donations:detail', args=[donation.pk]))
        html = response.content.decode()

        self.assertContains(response, 'aria-label="Imprimir recibo da doação"')
        self.assertNotContains(response, 'aria-label="Imprimir recibo da contribuição"')
        self.assertContains(response, 'Editar doação')
        self.assertContains(response, 'Excluir doação')
        self.assertContains(response, f'href="{reverse("donations:list")}">Voltar</a>')
        self.assertContains(response, reverse('donations:cancel', args=[donation.pk]))
        self.assertNotContains(response, 'Baixar doação')
        self.assertNotContains(response, 'Baixar contribuição')
        self.assertLess(html.index('Editar doação'), html.index('Excluir doação'))
        self.assertLess(html.index('Excluir doação'), html.index('>Voltar</a>'))

    def test_editor_can_see_and_open_the_protected_delete_flow(self):
        editor = get_user_model().objects.create_user(
            username='editor-doacao', password='senha-segura'
        )
        editor.user_permissions.set(
            Permission.objects.filter(
                content_type__app_label='donations',
                codename__in=['view_donation', 'change_donation'],
            )
        )
        donation = Donation.objects.create(
            donor=self.donor,
            created_by=editor,
            donation_date='2026-10-19',
            amount='100.00',
            donation_amount='100.00',
            contribution_amount='0.00',
            payment_method=Donation.PaymentMethod.PIX,
        )
        self.client.force_login(editor)

        detail = self.client.get(reverse('donations:detail', args=[donation.pk]))
        delete_flow = self.client.get(reverse('donations:cancel', args=[donation.pk]))

        self.assertContains(detail, 'Excluir doação')
        self.assertEqual(delete_flow.status_code, 200)


class DonationListReportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='operador', password='senha-segura'
        )
        self.user.user_permissions.set(
            Permission.objects.filter(content_type__app_label__in=['donations', 'donors'])
        )
        self.donor = Donor.objects.create(name='Maria')
        self.client.force_login(self.user)
        self.pix_donation = Donation.objects.create(
            donor=self.donor,
            donation_date='2026-09-05',
            amount='100.00',
            payment_method=Donation.PaymentMethod.PIX,
            created_by=self.user,
        )
        self.cash_donation = Donation.objects.create(
            donor=self.donor,
            donation_date='2026-08-25',
            amount='50.00',
            payment_method=Donation.PaymentMethod.CASH,
            created_by=self.user,
        )

    def test_list_filters_and_summarizes_donations(self):
        response = self.client.get(
            reverse('donations:list'),
            {'start_date': '2026-09-01', 'end_date': '2026-09-30', 'payment_method': 'pix'},
        )

        self.assertEqual(list(response.context['donations']), [self.pix_donation])
        self.assertEqual(response.context['summary']['total'], Decimal('100.00'))
        self.assertEqual(response.context['summary']['quantity'], 1)
        self.assertEqual(response.context['summary']['average'], Decimal('100.00'))
        self.assertEqual(response.context['summary']['largest'], Decimal('100.00'))
        self.assertEqual(response.context['summary_period_label'], 'de 01/09/2026 a 30/09/2026')
        self.assertEqual(response.context['distribution'][0]['label'], 'PIX')
        self.assertNotContains(response, 'Período selecionado')
        self.assertContains(response, 'de 01/09/2026 a 30/09/2026')
        self.assertContains(response, 'data-collapsible-toggle')
        self.assertContains(response, 'aria-controls="donation-filter-panel"')
        self.assertContains(response, 'aria-expanded="true"')
        self.assertContains(response, f'href="{reverse("dashboard:index")}">Voltar</a>')
        self.assertContains(response, '<label for="id_q">Doador</label>')
        self.assertContains(response, 'data-donor-filter-picker')
        self.assertContains(response, 'data-donor-filter-input')
        self.assertContains(response, reverse('donations:donor-search'))
        self.assertNotContains(response, 'Buscar por comprovante, doador ou CPF')
        self.assertContains(response, 'class="donation-table donation-breakdown-table"')
        self.assertContains(response, 'class="sort-link is-active is-descending"')
        self.assertContains(response, 'sort=donation_date')
        self.assertNotContains(response, 'for="id_payment_method"')
        self.assertNotContains(response, 'for="id_status"')
        self.assertContains(response, 'class="filter-actions filter-actions-right"')
        self.assertContains(response, 'class="button-link button-secondary"')
        self.assertContains(
            response,
            f'data-row-url="{reverse("donations:detail", args=[self.pix_donation.pk])}"',
        )
        self.assertContains(response, '<th scope="col" class="amount-breakdown-column">Valor da doação</th>')
        self.assertContains(response, '<th scope="col" class="amount-breakdown-column">Valor da contribuição</th>')
        self.assertContains(response, '<th scope="col" class="actions-column">Ações</th>')
        self.assertContains(response, '<td class="amount-breakdown-column">R$ 100,00</td>')
        self.assertContains(response, '<td class="amount-breakdown-column">-</td>')
        self.assertNotContains(response, '<span>Valor</span>')
        self.assertNotContains(response, '<span>Registrada em</span>')
        self.assertNotContains(response, '<th scope="col">Detalhes</th>')
        self.assertNotContains(response, '<th scope="col">Status</th>')
        self.assertContains(response, 'aria-label="Ver doação')
        self.assertContains(response, 'aria-label="Imprimir comprovante')

    def test_list_groups_receipts_when_donation_has_both_amounts(self):
        responsible = Donor.objects.create(name='Responsável', is_responsible=True)
        donation = Donation.objects.create(
            donor=self.donor,
            responsible=responsible,
            donation_date='2026-09-06',
            amount='150.00',
            donation_amount='100.00',
            contribution_amount='50.00',
            payment_method=Donation.PaymentMethod.PIX,
            created_by=self.user,
        )

        response = self.client.get(reverse('donations:list'))

        self.assertContains(response, 'class="receipt-menu"')
        self.assertContains(response, 'class="receipt-menu-options"')
        self.assertContains(response, f'Escolher comprovante para imprimir {donation.receipt_number}')
        self.assertContains(response, 'data-receipt-menu-close')
        self.assertContains(response, 'Fechar opções de impressão')
        self.assertContains(response, 'Imprimir recibo da doação')
        self.assertContains(response, 'Imprimir recibo da contribuição')
        self.assertContains(response, reverse('donations:receipt', args=[donation.pk, 'donation']))
        self.assertContains(response, reverse('donations:receipt', args=[donation.pk, 'contribution']))

    def test_list_prints_legacy_contribution_without_responsible(self):
        donation = Donation.objects.create(
            donor=self.donor,
            donation_date='2026-09-07',
            amount='30.00',
            donation_amount='0.00',
            contribution_amount='30.00',
            payment_method=Donation.PaymentMethod.PIX,
            created_by=self.user,
        )

        response = self.client.get(reverse('donations:list'))

        self.assertContains(
            response,
            f'aria-label="Imprimir comprovante de contribuição {donation.receipt_number}"',
        )
        self.assertContains(
            response,
            reverse('donations:receipt', args=[donation.pk, 'contribution']),
        )

    def test_list_searches_only_by_donor_name(self):
        other_donor = Donor.objects.create(name='Ana Souza', cpf='11144477735')
        receipt_match = Donation.objects.create(
            donor=other_donor,
            receipt_number='REC-MARIA-TESTE',
            donation_date='2026-09-06',
            amount='25.00',
            payment_method=Donation.PaymentMethod.PIX,
            created_by=self.user,
        )

        by_donor = self.client.get(reverse('donations:list'), {'q': 'Maria'})
        self.assertIn(self.pix_donation, by_donor.context['donations'])
        self.assertIn(self.cash_donation, by_donor.context['donations'])
        self.assertNotIn(receipt_match, by_donor.context['donations'])

        by_cpf = self.client.get(reverse('donations:list'), {'q': other_donor.cpf})
        self.assertEqual(list(by_cpf.context['donations']), [])

    def test_list_sorts_donations_by_amount(self):
        response = self.client.get(reverse('donations:list'), {'sort': 'amount'})

        self.assertEqual(list(response.context['donations'])[:2], [self.cash_donation, self.pix_donation])

    def test_list_uses_the_full_history_when_no_period_is_selected(self):
        response = self.client.get(reverse('donations:list'))

        self.assertEqual(response.context['summary_period_label'], 'todo o histórico')
        self.assertNotContains(response, 'Período selecionado')
        self.assertContains(response, 'todo o histórico')

    def test_list_rejects_an_inverted_date_range(self):
        response = self.client.get(
            reverse('donations:list'),
            {'start_date': '2026-09-30', 'end_date': '2026-09-01'},
        )

        self.assertContains(response, 'A data final deve ser igual ou posterior à inicial.')
        self.assertNotContains(response, 'Período selecionado')
        self.assertContains(response, 'período inválido')
        self.assertEqual(list(response.context['donations']), [])

    def test_list_paginates_without_changing_the_summary(self):
        Donation.objects.bulk_create(
            [
                Donation(
                    donor=self.donor,
                    donation_date='2026-09-06',
                    amount='10.00',
                    payment_method=Donation.PaymentMethod.PIX,
                    created_by=self.user,
                )
                for _ in range(29)
            ]
        )

        response = self.client.get(reverse('donations:list'), {'page': 3})

        self.assertEqual(response.context['summary']['quantity'], 31)
        self.assertEqual(response.context['page_obj'].number, 3)
        self.assertEqual(len(response.context['donations']), 1)

    def test_old_consultation_route_does_not_exist(self):
        response = self.client.get('/doacoes/consultas/')

        self.assertEqual(response.status_code, 404)
