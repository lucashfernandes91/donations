from datetime import date
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.core.paginator import Paginator
from django.utils import timezone

from apps.donations.models import Donation

LATEST_DONATIONS_PER_PAGE = 15

LATEST_DONATION_ORDERING = {
    'donation_date': ('donation_date', 'created_at', 'pk'),
    '-donation_date': ('-donation_date', '-created_at', '-pk'),
    'donor': ('donor__name', 'donation_date', 'pk'),
    '-donor': ('-donor__name', 'donation_date', 'pk'),
    'amount': ('amount', 'donation_date', 'pk'),
    '-amount': ('-amount', 'donation_date', 'pk'),
    'created_at': ('created_at', 'pk'),
    '-created_at': ('-created_at', '-pk'),
}


def month_start(reference, offset=0):
    year, month = divmod(reference.year * 12 + reference.month - 1 + offset, 12)
    return date(year, month + 1, 1)


def dashboard_context(params=None):
    today = timezone.localdate()
    current_month = month_start(today)
    next_month = month_start(today, 1)
    months = [month_start(today, offset) for offset in range(-11, 1)]
    active_donations = Donation.objects.filter(status=Donation.Status.ACTIVE)
    summary = active_donations.filter(donation_date__range=(current_month, today)).aggregate(
        month_total=Sum('amount', default=Decimal('0.00')),
        month_count=Count('pk'),
        today_total=Sum('amount', filter=Q(donation_date=today), default=Decimal('0.00')),
        today_count=Count('pk', filter=Q(donation_date=today)),
    )
    summary['month_average'] = (
        summary['month_total'] / summary['month_count']
        if summary['month_count'] else Decimal('0.00')
    )
    monthly_data = {
        item['month']: item
        for item in (
        active_donations.filter(donation_date__gte=months[0], donation_date__lt=next_month)
        .order_by()
        .annotate(month=TruncMonth('donation_date'))
        .values('month')
        .annotate(total=Sum('amount'), count=Count('pk'))
        )
    }
    chart = [
        {
            'month': month,
            'total': monthly_data.get(month, {}).get('total', Decimal('0.00')),
            'count': monthly_data.get(month, {}).get('count', 0),
        }
        for month in months
    ]
    maximum = max(item['total'] for item in chart)
    for item in chart:
        item['percentage'] = item['total'] * 100 / maximum if maximum else Decimal('0')
    monthly_summary = {
        'count': sum(item['count'] for item in chart),
        'total': sum((item['total'] for item in chart), Decimal('0.00')),
    }

    ordering = (params or {}).get('sort', '-created_at')
    if ordering not in LATEST_DONATION_ORDERING:
        ordering = '-created_at'

    latest_queryset = Donation.objects.select_related('donor', 'responsible').order_by(
        *LATEST_DONATION_ORDERING[ordering]
    )
    paginator = Paginator(latest_queryset, LATEST_DONATIONS_PER_PAGE)
    page_obj = paginator.get_page((params or {}).get('page'))

    return {
        'today': today,
        'month_start': current_month,
        'summary': summary,
        'monthly_chart': chart,
        'monthly_summary': monthly_summary,
        'ordering': ordering,
        'latest_donations': page_obj.object_list,
        'page_obj': page_obj,
        'paginator': paginator,
        'is_paginated': paginator.num_pages > 1,
    }
