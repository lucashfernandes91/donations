from datetime import date
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.test import TestCase

from apps.audit.models import AuditEntry
from apps.donors.models import Donor
from .models import Donation


class SeedDemoTests(TestCase):
    @patch('apps.donations.management.commands.seed_demo.timezone.localdate', return_value=date(2026, 9, 11))
    def test_creates_exact_annual_distribution_and_does_not_duplicate(self, localdate):
        call_command('seed_demo', stdout=StringIO())
        self.assertEqual(Donation.objects.count(), 100)
        self.assertEqual(Donor.objects.count(), 25)
        self.assertEqual(AuditEntry.objects.count(), 125)
        monthly = list(Donation.objects.order_by().annotate(month=TruncMonth('donation_date')).values('month').annotate(count=Count('pk')).order_by('month'))
        self.assertEqual([row['count'] for row in monthly], [5, 7, 9, 6, 8, 11, 7, 10, 6, 9, 12, 10])
        self.assertEqual(monthly[0]['month'], date(2025, 10, 1))
        self.assertEqual(monthly[-1]['month'], date(2026, 9, 1))
        self.assertFalse(Donation.objects.filter(donation_date__gt=date(2026, 9, 11)).exists())
        self.assertEqual(Donation.objects.filter(donation_date=date(2026, 9, 11)).count(), 1)
        self.assertEqual(Donation.objects.values('payment_method').distinct().count(), 6)
        actor = get_user_model().objects.get(username='carga-demonstracao')
        self.assertFalse(actor.is_active)
        self.assertFalse(actor.has_usable_password())
        call_command('seed_demo', stdout=StringIO())
        self.assertEqual(Donation.objects.count(), 100)
        self.assertEqual(AuditEntry.objects.count(), 125)

    @patch('apps.donations.management.commands.seed_demo.timezone.localdate', return_value=date(2026, 1, 1))
    def test_handles_first_day_of_year_and_preserves_existing_records(self, localdate):
        donor = Donor.objects.create(name='Doador existente')
        call_command('seed_demo', stdout=StringIO())
        donor.refresh_from_db()
        self.assertEqual(donor.name, 'Doador existente')
        self.assertEqual(Donor.objects.count(), 26)
        self.assertFalse(Donation.objects.filter(donation_date__gt=date(2026, 1, 1)).exists())
        self.assertEqual(Donation.objects.filter(donation_date=date(2026, 1, 1)).count(), 10)
