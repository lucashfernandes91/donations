from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView
from apps.audit.mixins import AuditedSaveMixin, snapshot
from apps.audit.models import AuditEntry
from apps.donations.sorting import apply_ordering, resolve_ordering

from .forms import DonorForm
from .models import Donor


class DonorListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = 'donors.view_donor'
    context_object_name = 'donors'
    default_ordering = 'name'
    ordering_options = {
        'name': ('name', 'pk'),
        '-name': ('-name', '-pk'),
        'cpf': ('cpf', 'name', 'pk'),
        '-cpf': ('-cpf', 'name', 'pk'),
        'phone': ('phone', 'name', 'pk'),
        '-phone': ('-phone', 'name', 'pk'),
        'status': ('-is_active', 'name', 'pk'),
        '-status': ('is_active', 'name', 'pk'),
    }
    paginate_by = 15
    template_name = 'donors/list.html'

    def get_queryset(self):
        queryset = Donor.objects.all()
        query = self.request.GET.get('q', '').strip()

        if query:
            queryset = queryset.filter(name__icontains=query)

        ordering = resolve_ordering(self.request, self.ordering_options, self.default_ordering)
        return apply_ordering(queryset, ordering, self.ordering_options)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('q', '').strip()
        context['ordering'] = resolve_ordering(self.request, self.ordering_options, self.default_ordering)
        return context


class DonorSearchView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'donors.view_donor'

    def get(self, request):
        query = request.GET.get('q', '').strip()
        if not query:
            return JsonResponse({'results': []})

        donors = Donor.objects.filter(name__istartswith=query).order_by('name', 'pk')[:10]
        return JsonResponse({
            'results': [
                {'id': donor.pk, 'name': donor.name}
                for donor in donors
            ]
        })


class DonorCreateView(LoginRequiredMixin, PermissionRequiredMixin, AuditedSaveMixin, CreateView):
    permission_required = 'donors.add_donor'
    form_class = DonorForm
    template_name = 'donors/form.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Doador cadastrado com sucesso.')
        return response

    def get_success_url(self):
        return reverse('donors:detail', kwargs={'pk': self.object.pk})


class DonorDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = ('donors.view_donor', 'donations.view_donation')
    context_object_name = 'donor'
    queryset = Donor.objects.prefetch_related('donations')
    template_name = 'donors/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        donations = self.object.donations.all()
        context['donations'] = donations
        context['total_donated'] = donations.filter(status='active').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        return context


class DonorUpdateView(LoginRequiredMixin, PermissionRequiredMixin, AuditedSaveMixin, UpdateView):
    permission_required = 'donors.change_donor'
    form_class = DonorForm
    model = Donor
    template_name = 'donors/form.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Doador atualizado com sucesso.')
        return response

    def get_success_url(self):
        return reverse('donors:detail', kwargs={'pk': self.object.pk})


class ResponsibleContextMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['responsible_section'] = True
        return context


class ResponsibleListView(ResponsibleContextMixin, DonorListView):
    context_object_name = 'responsibles'
    template_name = 'responsibles/list.html'

    def get_queryset(self):
        queryset = Donor.objects.filter(
            Q(is_responsible=True) | Q(donations_as_responsible__isnull=False)
        ).distinct()
        query = self.request.GET.get('q', '').strip()

        if query:
            queryset = queryset.filter(name__icontains=query)

        ordering = resolve_ordering(self.request, self.ordering_options, self.default_ordering)
        return apply_ordering(queryset, ordering, self.ordering_options)


class ResponsibleSearchView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'donors.view_donor'

    def get(self, request):
        query = request.GET.get('q', '').strip()
        if not query:
            return JsonResponse({'results': []})

        responsibles = Donor.objects.filter(
            Q(is_responsible=True) | Q(donations_as_responsible__isnull=False),
            is_active=True,
            name__istartswith=query,
        ).distinct().order_by('name', 'pk')[:10]
        return JsonResponse({
            'results': [
                {'id': responsible.pk, 'name': responsible.name}
                for responsible in responsibles
            ]
        })


class ResponsibleCreateView(ResponsibleContextMixin, LoginRequiredMixin, PermissionRequiredMixin, AuditedSaveMixin, CreateView):
    permission_required = 'donors.add_donor'
    form_class = DonorForm
    template_name = 'responsibles/form.html'

    def form_valid(self, form):
        form.instance.is_responsible = True
        response = super().form_valid(form)
        messages.success(self.request, 'Responsável cadastrado com sucesso.')
        return response

    def get_success_url(self):
        return reverse('donors:responsible-detail', kwargs={'pk': self.object.pk})


class ResponsibleDetailView(ResponsibleContextMixin, LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    permission_required = ('donors.view_donor', 'donations.view_donation')
    context_object_name = 'responsible'
    template_name = 'responsibles/detail.html'

    def get_queryset(self):
        return Donor.objects.filter(
            Q(is_responsible=True) | Q(donations_as_responsible__isnull=False)
        ).prefetch_related('donations_as_responsible__donor').distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        donations = self.object.donations_as_responsible.select_related('donor')
        context['donations'] = donations
        context['total_responsible'] = donations.filter(status='active').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        return context


class ResponsibleUpdateView(ResponsibleContextMixin, LoginRequiredMixin, PermissionRequiredMixin, AuditedSaveMixin, UpdateView):
    permission_required = 'donors.change_donor'
    form_class = DonorForm
    template_name = 'responsibles/form.html'

    def get_queryset(self):
        return Donor.objects.filter(
            Q(is_responsible=True) | Q(donations_as_responsible__isnull=False)
        ).distinct()

    def form_valid(self, form):
        form.instance.is_responsible = True
        response = super().form_valid(form)
        messages.success(self.request, 'Responsável atualizado com sucesso.')
        return response

    def get_success_url(self):
        return reverse('donors:responsible-detail', kwargs={'pk': self.object.pk})


class PersonDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    http_method_names = ['post']
    permission_required = 'donors.delete_donor'
    context_object_name = 'donor'
    person_name = 'Doador'

    def get_queryset(self):
        return Donor.objects.all()

    def get_object(self):
        return get_object_or_404(self.get_queryset(), pk=self.kwargs['pk'])

    def detail_url(self, person):
        return reverse('donors:detail', kwargs={'pk': person.pk})

    def list_url(self):
        return reverse('donors:list')

    def post(self, request, *args, **kwargs):
        with transaction.atomic():
            person = get_object_or_404(self.get_queryset().select_for_update(), pk=kwargs['pk'])
            before = snapshot(person)
            person_name = str(person)
            person_id = person.pk
            try:
                person.delete()
            except ProtectedError:
                messages.error(request, f'{self.person_name} não pode ser excluído porque possui doações vinculadas.')
                return redirect(self.detail_url(person))
            AuditEntry.objects.create(
                actor=request.user,
                entity=person._meta.label_lower,
                object_id=person_id,
                object_label=person_name[:300],
                action='delete',
                before=before,
                after={},
            )
        messages.success(request, f'{self.person_name} excluído com sucesso.')
        return redirect(self.list_url())


class DonorDeleteView(PersonDeleteView):
    pass


class ResponsibleDeleteView(ResponsibleContextMixin, PersonDeleteView):
    context_object_name = 'responsible'
    person_name = 'Responsável'

    def get_queryset(self):
        return Donor.objects.filter(
            Q(is_responsible=True) | Q(donations_as_responsible__isnull=False)
        ).distinct()

    def detail_url(self, person):
        return reverse('donors:responsible-detail', kwargs={'pk': person.pk})

    def list_url(self):
        return reverse('donors:responsible-list')
