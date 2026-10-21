from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.donors.models import Donor

from .forms import DonationForm
from .models import Donation
from .receipts import generate_receipt_pdf, receipt_data


class ReceiptTypeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='recibos', password='senha-segura'
        )
        self.donor = Donor.objects.create(name='Doador Teste')
        self.responsible = Donor.objects.create(name='Responsável Teste', is_responsible=True)
        self.donation = Donation.objects.create(
            donor=self.donor,
            responsible=self.responsible,
            donation_date='2026-10-07',
            amount=Decimal('150.00'),
            donation_amount=Decimal('100.00'),
            contribution_amount=Decimal('50.00'),
            payment_method=Donation.PaymentMethod.PIX,
            created_by=self.user,
        )
        self.client.force_login(self.user)

    def test_receipts_use_independent_recipient_amount_and_number(self):
        donation = receipt_data(self.donation, 'donation')
        contribution = receipt_data(self.donation, 'contribution')

        self.assertEqual(donation['recipient'], self.donor.name)
        self.assertEqual(donation['amount'], Decimal('100.00'))
        self.assertEqual(donation['number'], str(self.donation.donation_receipt_number))
        self.assertEqual(contribution['recipient'], self.responsible.name)
        self.assertEqual(contribution['amount'], Decimal('50.00'))
        self.assertEqual(
            contribution['number'],
            str(self.donation.contribution_receipt_number),
        )
        self.assertNotEqual(donation['number'], contribution['number'])
        self.assertTrue(generate_receipt_pdf(self.donation, 'donation').startswith(b'%PDF'))
        self.assertTrue(generate_receipt_pdf(self.donation, 'contribution').startswith(b'%PDF'))

    @patch('apps.donations.views.generate_receipt_pdf', return_value=b'%PDF-1.7')
    def test_each_receipt_has_an_independent_endpoint(self, generate_pdf):
        for receipt_type in ('donation', 'contribution'):
            response = self.client.get(
                reverse('donations:receipt', args=[self.donation.pk, receipt_type])
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn('inline;', response['Content-Disposition'])

        self.assertEqual(
            [call.args[1] for call in generate_pdf.call_args_list],
            ['donation', 'contribution'],
        )

    def test_detail_shows_both_print_buttons(self):
        response = self.client.get(reverse('donations:detail', args=[self.donation.pk]))

        self.assertContains(response, 'aria-label="Imprimir recibo da doação"')
        self.assertContains(response, 'aria-label="Imprimir recibo da contribuição"')
        self.assertContains(
            response, reverse('donations:receipt', args=[self.donation.pk, 'donation'])
        )
        self.assertContains(
            response, reverse('donations:receipt', args=[self.donation.pk, 'contribution'])
        )
        self.assertNotContains(response, 'Baixar doação')
        self.assertNotContains(response, 'Baixar contribuição')

    def test_contribution_requires_a_responsible(self):
        form = DonationForm(
            data={
                'new_donor_name': self.donor.name,
                'new_responsible_name': '',
                'donation_date': '2026-10-07',
                'donation_amount': '10.00',
                'contribution_amount': '5.00',
                'payment_method': Donation.PaymentMethod.PIX,
                'notes': '',
            },
            allow_new_donor=True,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('new_responsible_name', form.errors)

    def test_legacy_contribution_without_responsible_uses_donor_on_receipt(self):
        legacy = Donation.objects.create(
            donor=self.donor,
            donation_date='2026-10-07',
            amount=Decimal('25.00'),
            donation_amount=Decimal('0.00'),
            contribution_amount=Decimal('25.00'),
            payment_method=Donation.PaymentMethod.PIX,
            created_by=self.user,
        )

        detail = self.client.get(reverse('donations:detail', args=[legacy.pk]))
        receipt = self.client.get(
            reverse('donations:receipt', args=[legacy.pk, 'contribution'])
        )

        self.assertEqual(receipt_data(legacy, 'contribution')['recipient'], self.donor.name)
        self.assertContains(detail, 'aria-label="Imprimir recibo da contribuição"')
        self.assertEqual(receipt.status_code, 200)
