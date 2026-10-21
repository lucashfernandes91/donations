from datetime import date, datetime, timezone as datetime_timezone
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.donations.models import Donation
from apps.donors.models import Donor

from .services import dashboard_context


class DashboardViewTests(TestCase):
    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse('dashboard:index'))

        self.assertRedirects(response, f"{reverse('accounts:login')}?next=/")

    def test_authenticated_user_can_access_dashboard(self):
        user = get_user_model().objects.create_user(
            username='operador', password='senha-segura'
        )
        user.user_permissions.add(Permission.objects.get(codename='view_donation'))
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard:index'))

        self.assertContains(response, 'Início')
        self.assertContains(response, 'class="app-body dashboard-page"')
        self.assertContains(response, 'data-mixed-chart')
        self.assertContains(response, 'data-monthly-chart-toggle')
        self.assertContains(response, 'aria-controls="monthly-chart-panel"')
        self.assertContains(response, 'aria-expanded="true"')
        self.assertContains(response, 'monthly-chart-data')
        self.assertContains(response, 'Doações nos últimos 12 meses')
        self.assertContains(response, 'Arrecadação nos últimos 12 meses')
        self.assertNotContains(response, 'Total de hoje')
        self.assertNotContains(response, 'Ticket médio do mês')
        self.assertContains(response, 'dashboard.js')

    def test_staff_user_is_redirected_to_django_admin(self):
        user = get_user_model().objects.create_user(
            username='membro-equipe',
            password='senha-segura',
            is_staff=True,
        )
        user.user_permissions.add(Permission.objects.get(codename='view_donation'))
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard:index'))

        self.assertRedirects(response, reverse('admin:index'))

    def test_users_and_profiles_link_is_hidden_from_non_staff_user(self):
        user = get_user_model().objects.create_user(
            username='usuario-comum',
            password='senha-segura',
        )
        user.user_permissions.add(Permission.objects.get(codename='view_donation'))
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard:index'))

        self.assertNotContains(response, 'Usuários e perfis')


class DashboardDataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='dashboard-review')
        cls.user.user_permissions.set(
            Permission.objects.filter(content_type__app_label__in=['donations', 'donors', 'audit'])
        )
        cls.donor = Donor.objects.create(name='Doador de teste')

    def setUp(self):
        self.client.force_login(self.user)

    def donate(self, donation_date, amount):
        return Donation.objects.create(
            donor=self.donor, created_by=self.user, donation_date=donation_date,
            amount=Decimal(amount), payment_method=Donation.PaymentMethod.PIX,
        )

    @patch('apps.dashboard.services.timezone.localdate', return_value=date(2026, 1, 10))
    def test_empty_dashboard_has_zero_totals_and_twelve_months(self, localdate):
        response = self.client.get(reverse('dashboard:index'))
        self.assertContains(response, 'Nenhuma doação registrada ainda.')
        self.assertEqual(response.context['summary'], {
            'month_total': Decimal('0.00'), 'month_count': 0,
            'today_total': Decimal('0.00'), 'today_count': 0,
            'month_average': Decimal('0.00'),
        })
        self.assertEqual(len(response.context['monthly_chart']), 12)
        self.assertEqual(response.context['monthly_summary'], {'count': 0, 'total': Decimal('0.00')})
        self.assertTrue(all(item['percentage'] == 0 for item in response.context['monthly_chart']))
        self.assertTrue(all(item['count'] == 0 for item in response.context['monthly_chart']))

    @patch('apps.dashboard.services.timezone.localdate', return_value=date(2026, 1, 10))
    def test_amounts_use_donation_date_and_exclude_future_dates(self, localdate):
        self.donate(date(2026, 1, 1), '10.10')
        self.donate(date(2026, 1, 10), '20.20')
        self.donate(date(2026, 1, 10), '0.03')
        self.donate(date(2025, 12, 31), '500.00')
        self.donate(date(2026, 1, 11), '900.00')
        self.donate(date(2026, 2, 1), '1000.00')
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.context['summary'], {
            'month_total': Decimal('30.33'), 'month_count': 3,
            'today_total': Decimal('20.23'), 'today_count': 2,
            'month_average': Decimal('10.11'),
        })
        self.assertContains(response, 'start_date=2026-01-01&amp;end_date=2026-01-10')

    @patch('apps.dashboard.services.timezone.localdate', return_value=date(2026, 1, 10))
    def test_chart_crosses_year_boundary_and_fills_missing_months(self, localdate):
        self.donate(date(2025, 1, 31), '9999.00')
        self.donate(date(2025, 8, 1), '100.00')
        self.donate(date(2025, 12, 31), '200.00')
        self.donate(date(2026, 1, 10), '50.00')
        context = dashboard_context()
        self.assertEqual([item['month'] for item in context['monthly_chart']], [
            date(2025, 2, 1), date(2025, 3, 1), date(2025, 4, 1),
            date(2025, 5, 1), date(2025, 6, 1), date(2025, 7, 1),
            date(2025, 8, 1), date(2025, 9, 1), date(2025, 10, 1),
            date(2025, 11, 1), date(2025, 12, 1), date(2026, 1, 1),
        ])
        self.assertEqual([item['total'] for item in context['monthly_chart']], [
            Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0'),
            Decimal('100'), Decimal('0'), Decimal('0'), Decimal('0'), Decimal('200'), Decimal('50'),
        ])
        self.assertEqual([item['count'] for item in context['monthly_chart']], [0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 1])
        self.assertEqual([item['percentage'] for item in context['monthly_chart']], [0, 0, 0, 0, 0, 0, 50, 0, 0, 0, 100, 25])
        self.assertEqual(context['monthly_summary'], {'count': 3, 'total': Decimal('350.00')})

    def test_chart_includes_current_month_and_advances_one_month_at_a_time(self):
        self.donate(date(2026, 1, 31), '75.00')

        with patch('apps.dashboard.services.timezone.localdate', return_value=date(2026, 1, 10)):
            january_context = dashboard_context()

        self.assertEqual(january_context['monthly_chart'][0]['month'], date(2025, 2, 1))
        self.assertEqual(january_context['monthly_chart'][-1], {
            'month': date(2026, 1, 1),
            'total': Decimal('75.00'),
            'count': 1,
            'percentage': Decimal('100'),
        })

        with patch('apps.dashboard.services.timezone.localdate', return_value=date(2026, 2, 1)):
            february_context = dashboard_context()

        self.assertEqual(february_context['monthly_chart'][0]['month'], date(2025, 3, 1))
        self.assertEqual(february_context['monthly_chart'][-1]['month'], date(2026, 2, 1))
        self.assertEqual(february_context['monthly_chart'][-2]['month'], date(2026, 1, 1))
        self.assertEqual(february_context['monthly_chart'][-2]['total'], Decimal('75.00'))

    def test_latest_donations_paginate_after_fifteen_and_link_to_details(self):
        donations = [self.donate(date(2026, 1, day), '10.00') for day in range(17, 0, -1)]
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(list(response.context['latest_donations']), list(reversed(donations))[:15])
        self.assertEqual(len(response.context['latest_donations']), 15)
        self.assertContains(response, 'Os 15 lançamentos mais recentes')
        self.assertContains(response, 'Página 1 de 2 · 17 registros')
        self.assertContains(response, 'Próxima')
        self.assertContains(response, reverse('donations:detail', args=[donations[-1].pk]))
        self.assertContains(
            response,
            f'<tr data-donation-modal-open="donation-modal-{donations[-1].pk}" '
            f'tabindex="0" aria-label="Ver doação {donations[-1].receipt_number}">',
        )
        self.assertContains(response, f'id="donation-modal-{donations[-1].pk}"')
        self.assertContains(response, 'class="donation-table donation-breakdown-table"')
        self.assertContains(response, '<th scope="col" class="actions-column">Ações</th>')
        self.assertContains(response, '<th scope="col" class="amount-breakdown-column">Valor da doação</th>')
        self.assertContains(response, '<th scope="col" class="amount-breakdown-column">Valor da contribuição</th>')
        self.assertNotContains(response, '<span>Valor</span>')
        self.assertNotContains(response, '<th scope="col">Registrada em</th>')
        self.assertNotContains(response, '<th scope="col">Detalhes</th>')
        self.assertContains(response, 'aria-label="Ver doação')
        self.assertContains(response, 'aria-label="Imprimir comprovante')
        self.assertContains(response, 'data-donation-row-action')
        self.assertNotContains(response, '<th scope="col">Status</th>')
        self.assertNotContains(response, '<dt>Status</dt>')
        self.assertNotContains(response, '<dt>Cadastrada por</dt>')
        self.assertNotContains(response, '<dt>Criada em</dt>')
        self.assertNotContains(response, '<dt>Atualizada em</dt>')
        self.assertContains(response, 'Imprimir doação')
        self.assertNotContains(response, 'Imprimir</a>')
        self.assertContains(response, reverse('donations:receipt', args=[donations[-1].pk, 'donation']))
        self.assertContains(response, reverse('donations:receipt-download', args=[donations[-1].pk, 'donation']))
        self.assertContains(response, reverse('donations:update', args=[donations[-1].pk]))
        self.assertContains(response, reverse('donations:cancel', args=[donations[-1].pk]))
        self.assertContains(response, f"{reverse('audit:list')}?entity=donations.donation&amp;object_id={donations[-1].pk}")

    def test_latest_table_separates_donation_and_contribution_values(self):
        donation = Donation.objects.create(
            donor=self.donor,
            created_by=self.user,
            donation_date=date(2026, 1, 2),
            amount=Decimal('75.00'),
            donation_amount=Decimal('75.00'),
            contribution_amount=Decimal('0.00'),
            payment_method=Donation.PaymentMethod.PIX,
        )
        contribution = Donation.objects.create(
            donor=self.donor,
            created_by=self.user,
            donation_date=date(2026, 1, 1),
            amount=Decimal('25.00'),
            donation_amount=Decimal('0.00'),
            contribution_amount=Decimal('25.00'),
            payment_method=Donation.PaymentMethod.PIX,
        )

        response = self.client.get(reverse('dashboard:index'))

        self.assertContains(response, f'<td class="amount-breakdown-column">R$ 75,00</td>')
        self.assertContains(response, f'<td class="amount-breakdown-column">R$ 25,00</td>')
        self.assertContains(response, '<td class="amount-breakdown-column">-</td>', count=2)
        self.assertContains(response, f'<tr data-donation-modal-open="donation-modal-{donation.pk}"')
        self.assertContains(response, f'<tr data-donation-modal-open="donation-modal-{contribution.pk}"')
        self.assertContains(
            response,
            f'aria-label="Imprimir comprovante de contribuição {contribution.receipt_number}"',
        )
        self.assertContains(
            response,
            reverse('donations:receipt', args=[contribution.pk, 'contribution']),
        )

    def test_latest_table_groups_receipts_when_donation_has_both_amounts(self):
        responsible = Donor.objects.create(name='Responsável', is_responsible=True)
        donation = Donation.objects.create(
            donor=self.donor,
            responsible=responsible,
            created_by=self.user,
            donation_date=date(2026, 1, 3),
            amount=Decimal('150.00'),
            donation_amount=Decimal('100.00'),
            contribution_amount=Decimal('50.00'),
            payment_method=Donation.PaymentMethod.PIX,
        )

        response = self.client.get(reverse('dashboard:index'))

        self.assertContains(response, 'class="receipt-menu"')
        self.assertContains(response, 'class="receipt-menu-options"')
        self.assertContains(
            response,
            f'Escolher comprovante para imprimir {donation.receipt_number}',
        )
        self.assertContains(response, 'data-receipt-menu-close')
        self.assertContains(response, 'Fechar opções de impressão')
        self.assertContains(response, 'Imprimir recibo da doação')
        self.assertContains(response, 'Imprimir recibo da contribuição')
        self.assertContains(response, 'data-modal-action-column="donation"')
        self.assertContains(response, 'data-modal-action-column="contribution"')
        self.assertContains(response, 'data-modal-action-column="management"')
        modal_html = response.content.decode()
        self.assertLess(
            modal_html.index('data-modal-action-column="donation"'),
            modal_html.index('data-modal-action-column="contribution"'),
        )
        self.assertLess(
            modal_html.index('data-modal-action-column="contribution"'),
            modal_html.index('data-modal-action-column="management"'),
        )
        self.assertLess(modal_html.index('Imprimir doação'), modal_html.index('Baixar doação'))
        self.assertLess(
            modal_html.index('Imprimir contribuição'),
            modal_html.index('Baixar contribuição'),
        )
        self.assertLess(modal_html.index('Histórico de alterações'), modal_html.index('Editar doação'))
        self.assertContains(
            response,
            reverse('donations:receipt', args=[donation.pk, 'donation']),
        )
        self.assertContains(
            response,
            reverse('donations:receipt', args=[donation.pk, 'contribution']),
        )

    def test_latest_table_sorts_by_amount_when_requested(self):
        low = self.donate(date(2026, 1, 1), '5.00')
        high = self.donate(date(2026, 1, 2), '50.00')

        response = self.client.get(reverse('dashboard:index'), {'sort': '-amount'})

        self.assertEqual(list(response.context['latest_donations'])[:2], [high, low])

    @patch('django.utils.timezone.now', return_value=datetime(2026, 2, 1, 1, 0, tzinfo=datetime_timezone.utc))
    def test_today_uses_sao_paulo_date_near_midnight(self, now):
        self.donate(date(2026, 1, 31), '25.00')
        self.donate(date(2026, 2, 1), '100.00')
        context = dashboard_context()
        self.assertEqual(context['today'], date(2026, 1, 31))
        self.assertEqual(context['summary']['today_total'], Decimal('25.00'))
