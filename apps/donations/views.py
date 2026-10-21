from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Avg, Count, Max, Q, Sum
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseGone, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.donors.models import Donor
from apps.audit.mixins import AuditedSaveMixin, snapshot
from apps.audit.models import AuditEntry

from .forms import CancellationForm, DonationFilterForm, DonationForm
from .models import Donation
from .exports import export_xlsx
from .receipts import generate_receipt_pdf, receipt_filename
from .sorting import apply_ordering, resolve_ordering


class DonationFilterMixin:
    default_ordering = '-donation_date'
    ordering_options = {
        'donation_date': ('donation_date', 'created_at', 'pk'),
        '-donation_date': ('-donation_date', '-created_at', '-pk'),
        'donor': ('donor__name', 'donation_date', 'pk'),
        '-donor': ('-donor__name', 'donation_date', 'pk'),
        'amount': ('amount', 'donation_date', 'pk'),
        '-amount': ('-amount', 'donation_date', 'pk'),
        'created_at': ('created_at', 'pk'),
        '-created_at': ('-created_at', '-pk'),
        'status': ('status', 'donation_date', 'pk'),
        '-status': ('-status', 'donation_date', 'pk'),
    }

    def get_filter_form(self):
        if not hasattr(self, '_filter_form'):
            self._filter_form = DonationFilterForm(self.request.GET)
        return self._filter_form

    def get_filtered_queryset(self, *, active_only=False):
        queryset = Donation.objects.select_related('donor', 'created_by')
        form = self.get_filter_form()

        if not form.is_valid():
            return queryset.none()

        filters = form.cleaned_data
        query = filters['q'].strip()

        if query:
            queryset = queryset.filter(donor__name__icontains=query)
        if filters['start_date']:
            queryset = queryset.filter(donation_date__gte=filters['start_date'])
        if filters['end_date']:
            queryset = queryset.filter(donation_date__lte=filters['end_date'])
        if filters['payment_method']:
            queryset = queryset.filter(payment_method=filters['payment_method'])
        if active_only:
            queryset = queryset.filter(status=Donation.Status.ACTIVE)
            if filters['status'] and filters['status'] != Donation.Status.ACTIVE:
                queryset = queryset.none()
        elif filters['status']:
            queryset = queryset.filter(status=filters['status'])

        ordering = resolve_ordering(self.request, self.ordering_options, self.default_ordering)
        return apply_ordering(queryset, ordering, self.ordering_options)

    def get_filter_params(self):
        params = self.request.GET.copy()
        params.pop('page', None)
        return params.urlencode()

    def get_period_label(self):
        form = self.get_filter_form()

        if not form.is_valid():
            return 'período inválido'

        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')

        if start_date and end_date:
            return f'de {start_date:%d/%m/%Y} a {end_date:%d/%m/%Y}'
        if start_date:
            return f'a partir de {start_date:%d/%m/%Y}'
        if end_date:
            return f'até {end_date:%d/%m/%Y}'
        return 'todo o histórico'


class DonationListView(LoginRequiredMixin, PermissionRequiredMixin, DonationFilterMixin, ListView):
    permission_required = 'donations.view_donation'
    context_object_name = 'donations'
    paginate_by = 15
    template_name = 'donations/list.html'

    def get_queryset(self):
        return self.get_filtered_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        report_queryset = self.get_filtered_queryset(active_only=True)
        summary = report_queryset.aggregate(
            total=Sum('amount'),
            quantity=Count('id'),
            average=Avg('amount'),
            largest=Max('amount'),
        )
        payment_labels = dict(Donation.PaymentMethod.choices)
        distribution = list(
            report_queryset.values('payment_method')
            .annotate(total=Sum('amount'), quantity=Count('id'))
            .order_by('payment_method')
        )
        for item in distribution:
            item['label'] = payment_labels[item['payment_method']]

        context.update(
            filter_form=self.get_filter_form(),
            filter_params=self.get_filter_params(),
            ordering=resolve_ordering(self.request, self.ordering_options, self.default_ordering),
            summary_period_label=self.get_period_label(),
            summary={
                'total': summary['total'] or Decimal('0.00'),
                'quantity': summary['quantity'],
                'average': summary['average'] or Decimal('0.00'),
                'largest': summary['largest'] or Decimal('0.00'),
            },
            distribution=distribution,
        )
        return context


class DonationExportXlsxView(LoginRequiredMixin, PermissionRequiredMixin, DonationFilterMixin, View):
    permission_required = 'donations.view_donation'

    def get(self, request):
        if not self.get_filter_form().is_valid():
            return HttpResponseBadRequest('Filtros de consulta inválidos.')
        return export_xlsx(self.get_filtered_queryset(active_only=True))


class DonationCreateView(LoginRequiredMixin, PermissionRequiredMixin, AuditedSaveMixin, CreateView):
    permission_required = 'donations.add_donation'
    form_class = DonationForm
    template_name = 'donations/form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['allow_new_donor'] = True
        return kwargs

    def form_valid(self, form):
        new_people = []
        for person in (form.created_donor, form.created_responsible):
            if person and person not in new_people:
                new_people.append(person)

        if new_people:
            if not self.request.user.has_perm('donors.add_donor'):
                form.add_error(None, 'Seu usuário não pode cadastrar um novo doador ou responsável.')
                return self.form_invalid(form)

            for person in new_people:
                if person is form.created_responsible:
                    person.is_responsible = True
                person.save()
                AuditEntry.objects.create(
                    actor=self.request.user,
                    entity=person._meta.label_lower,
                    object_id=person.pk,
                    object_label=str(person)[:300],
                    action='create',
                    before={},
                    after=snapshot(person),
                )

        if form.created_donor:
            form.instance.donor = form.created_donor
        if form.created_responsible:
            form.instance.responsible = form.created_responsible
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, 'Doação cadastrada com sucesso.')
        return response

    def get_success_url(self):
        return reverse('donations:detail', kwargs={'pk': self.object.pk})


class DonorSearchView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'donors.view_donor'

    def get(self, request):
        query = request.GET.get('q', '').strip()
        if not query:
            return JsonResponse({'results': []})

        donors = Donor.objects.filter(is_active=True, name__istartswith=query).order_by('name', 'pk')[:10]
        return JsonResponse({
            'results': [
                {
                    'id': donor.pk,
                    'name': donor.name,
                }
                for donor in donors
            ]
        })


class DonationDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = 'donations.view_donation'
    context_object_name = 'donation'
    queryset = Donation.objects.select_related('donor', 'responsible', 'created_by', 'updated_by')
    template_name = 'donations/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        receipt_titles = []
        if self.object.donation_amount and self.object.donation_receipt_number is not None:
            receipt_titles.append(f'Doação nº {self.object.donation_receipt_number}')
        if self.object.contribution_amount and self.object.contribution_receipt_number is not None:
            receipt_titles.append(f'Contribuição nº {self.object.contribution_receipt_number}')
        context['detail_title'] = ' / '.join(receipt_titles)
        context['audit_entries'] = (
            AuditEntry.objects.select_related('actor')
            .filter(entity='donations.donation', object_id=self.object.pk)
            if self.request.user.has_perm('audit.view_auditentry') else AuditEntry.objects.none()
        )
        return context


class DonationUpdateView(LoginRequiredMixin, PermissionRequiredMixin, AuditedSaveMixin, UpdateView):
    permission_required = 'donations.change_donation'
    form_class = DonationForm
    model = Donation
    template_name = 'donations/form.html'

    def get_queryset(self):
        return super().get_queryset().filter(status=Donation.Status.ACTIVE)

    def form_valid(self, form):
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, 'Doação atualizada com sucesso.')
        return response

    def get_success_url(self):
        return reverse('donations:detail', kwargs={'pk': self.object.pk})


class DonationReceiptView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'donations.view_donation'
    as_attachment = False

    def get(self, request, pk, receipt_type):
        donation = get_object_or_404(Donation.objects.select_related('donor', 'responsible'), pk=pk)
        if donation.status == Donation.Status.CANCELLED:
            return HttpResponseGone('Doação cancelada. O comprovante não pode mais ser emitido.')
        disposition = 'attachment' if self.as_attachment else 'inline'
        try:
            pdf = generate_receipt_pdf(donation, receipt_type)
        except ValueError as error:
            raise Http404(str(error)) from error
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'{disposition}; filename="{receipt_filename(donation, receipt_type)}"'
        response['Cache-Control'] = 'no-store'
        return response


class DonationReceiptDownloadView(DonationReceiptView):
    as_attachment = True


class DonationCancelView(LoginRequiredMixin, PermissionRequiredMixin, AuditedSaveMixin, UpdateView):
    permission_required = 'donations.cancel_donation'
    model = Donation
    form_class = CancellationForm
    template_name = 'donations/cancel.html'
    audit_action = 'cancel'

    def has_permission(self):
        return (
            self.request.user.has_perm('donations.cancel_donation')
            or self.request.user.has_perm('donations.change_donation')
        )

    def get_queryset(self):
        return super().get_queryset().filter(status=Donation.Status.ACTIVE)

    def form_valid(self, form):
        form.instance.status = Donation.Status.CANCELLED
        form.instance.cancelled_by = self.request.user
        form.instance.cancelled_at = timezone.now()
        form.instance.updated_by = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, 'Doação cancelada com sucesso.')
        return response

    def get_success_url(self):
        return reverse('donations:detail', args=[self.object.pk])
