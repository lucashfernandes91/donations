from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.donors.models import Donor

from .models import Donation, ReceiptNumberSequence
from .receipts import receipt_data


class ReceiptNumberSequenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='sequencia-recibos',
            password='senha-segura',
        )
        self.donor = Donor.objects.create(name='Doador da sequência')
        self.responsible = Donor.objects.create(
            name='Responsável da sequência',
            is_responsible=True,
        )

    def create_donation(self, donation_amount='0.00', contribution_amount='0.00'):
        return Donation.objects.create(
            donor=self.donor,
            responsible=self.responsible,
            donation_date='2026-10-16',
            amount=Decimal(donation_amount) + Decimal(contribution_amount),
            donation_amount=Decimal(donation_amount),
            contribution_amount=Decimal(contribution_amount),
            payment_method=Donation.PaymentMethod.PIX,
            created_by=self.user,
        )

    def test_configured_number_assigns_two_consecutive_receipts(self):
        sequence = ReceiptNumberSequence.objects.get(pk=1)
        sequence.next_number = 100
        sequence.save()

        donation = self.create_donation('80.00', '20.00')

        self.assertEqual(donation.donation_receipt_number, 100)
        self.assertEqual(donation.contribution_receipt_number, 101)
        self.assertEqual(receipt_data(donation, 'donation')['number'], '100')
        self.assertEqual(receipt_data(donation, 'contribution')['number'], '101')
        sequence.refresh_from_db()
        self.assertEqual(sequence.next_number, 102)

    def test_each_single_receipt_consumes_one_number(self):
        donation = self.create_donation('30.00')
        contribution = self.create_donation('0.00', '15.00')

        self.assertEqual(donation.donation_receipt_number, 1)
        self.assertIsNone(donation.contribution_receipt_number)
        self.assertIsNone(contribution.donation_receipt_number)
        self.assertEqual(contribution.contribution_receipt_number, 2)
        self.assertEqual(ReceiptNumberSequence.objects.get(pk=1).next_number, 3)

    def test_adding_a_component_allocates_only_its_receipt(self):
        donation = self.create_donation('30.00')
        original_number = donation.donation_receipt_number

        donation.contribution_amount = Decimal('10.00')
        donation.save()

        self.assertEqual(donation.donation_receipt_number, original_number)
        self.assertEqual(donation.contribution_receipt_number, 2)
        self.assertEqual(ReceiptNumberSequence.objects.get(pk=1).next_number, 3)

    def test_reconfigured_used_number_is_skipped(self):
        first = self.create_donation('30.00')
        sequence = ReceiptNumberSequence.objects.get(pk=1)
        sequence.next_number = first.donation_receipt_number
        sequence.save()

        second = self.create_donation('20.00')

        self.assertEqual(second.donation_receipt_number, 2)
        sequence.refresh_from_db()
        self.assertEqual(sequence.next_number, 3)

    def test_admin_can_change_the_next_number(self):
        self.client.force_login(self.user)
        url = reverse(
            'admin:donations_receiptnumbersequence_change',
            args=[1],
        )

        response = self.client.post(url, {'next_number': 500}, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ReceiptNumberSequence.objects.get(pk=1).next_number, 500)
        self.assertContains(response, 'Próximo número do recibo')
