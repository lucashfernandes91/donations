from decimal import Decimal

from django import forms
from django.db.models import Q

from apps.donors.models import Donor

from .models import Donation


class BrazilianMoneyField(forms.DecimalField):
    def to_python(self, value):
        if isinstance(value, str):
            normalized = value.strip().replace(' ', '')
            if ',' in normalized:
                value = normalized.replace('.', '').replace(',', '.')
        return super().to_python(value)


class DonationForm(forms.ModelForm):
    new_donor_name = forms.CharField(
        label='Doador',
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                'autocomplete': 'off',
                'data-donor-input': '',
                'placeholder': 'Busque ou informe o nome do doador',
            }
        ),
    )
    new_responsible_name = forms.CharField(
        label='Responsável',
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                'autocomplete': 'off',
                'data-donor-input': '',
                'placeholder': 'Busque ou informe o nome do responsável',
            }
        ),
    )
    donation_amount = BrazilianMoneyField(
        label='Doação',
        decimal_places=2,
        max_digits=12,
        min_value=Decimal('0.00'),
        required=False,
        widget=forms.TextInput(
            attrs={
                'autocomplete': 'off',
                'data-money-input': '',
                'inputmode': 'decimal',
                'placeholder': 'Ex.: 100,00',
            }
        ),
    )
    contribution_amount = BrazilianMoneyField(
        label='Contribuição',
        decimal_places=2,
        max_digits=12,
        min_value=Decimal('0.00'),
        required=False,
        widget=forms.TextInput(
            attrs={
                'autocomplete': 'off',
                'data-money-input': '',
                'inputmode': 'decimal',
                'placeholder': 'Ex.: 100,00',
            }
        ),
    )

    class Meta:
        model = Donation
        fields = [
            'donor',
            'responsible',
            'donation_date',
            'donation_amount',
            'contribution_amount',
            'payment_method',
            'notes',
        ]
        widgets = {
            'donation_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        self.allow_new_donor = kwargs.pop('allow_new_donor', False)
        self.created_donor = None
        self.created_responsible = None
        super().__init__(*args, **kwargs)
        donor_filter = Q(is_active=True)
        if self.instance.pk:
            donor_filter |= Q(pk=self.instance.donor_id)
            if self.instance.responsible_id:
                donor_filter |= Q(pk=self.instance.responsible_id)

        self.fields['donor'].queryset = Donor.objects.filter(donor_filter).order_by('name', 'pk')
        self.fields['donor'].required = False
        self.fields['donor'].widget = forms.HiddenInput(attrs={'data-donor-id': ''})
        self.fields['responsible'].queryset = Donor.objects.filter(donor_filter).order_by('name', 'pk')
        self.fields['responsible'].required = False
        self.fields['responsible'].widget = forms.HiddenInput(attrs={'data-donor-id': ''})
        if self.instance.pk:
            self.fields['donor'].initial = self.instance.donor_id
            self.fields['new_donor_name'].initial = self.instance.donor.name
            self.fields['responsible'].initial = self.instance.responsible_id
            if self.instance.responsible_id:
                self.fields['new_responsible_name'].initial = self.instance.responsible.name
        else:
            self.initial['donation_amount'] = None
            self.initial['contribution_amount'] = None
        payment_method_choices = [
            (Donation.PaymentMethod.PIX.value, Donation.PaymentMethod.PIX.label),
            (Donation.PaymentMethod.BANK_TRANSFER.value, Donation.PaymentMethod.BANK_TRANSFER.label),
        ]
        current_payment_method = self.instance.payment_method
        if self.instance.pk and current_payment_method not in dict(payment_method_choices):
            payment_method_choices.append(
                (current_payment_method, dict(Donation.PaymentMethod.choices)[current_payment_method])
            )
        self.fields['payment_method'].choices = [
            ('', 'Selecione uma opção'),
            *payment_method_choices,
        ]

    def clean(self):
        cleaned_data = super().clean()
        zero = Decimal('0.00')
        donation_amount = cleaned_data.get('donation_amount') or zero
        contribution_amount = cleaned_data.get('contribution_amount') or zero
        cleaned_data['donation_amount'] = donation_amount
        cleaned_data['contribution_amount'] = contribution_amount

        if donation_amount + contribution_amount <= zero:
            self.add_error('donation_amount', 'Informe um valor de doação ou contribuição maior que zero.')
            return cleaned_data

        donor = self._resolve_person(
            selected=cleaned_data.get('donor'),
            typed_name=(cleaned_data.get('new_donor_name') or '').strip(),
            field_name='new_donor_name',
            required=True,
            person_label='doador',
            created_attribute='created_donor',
        )
        if donor and not self.created_donor:
            cleaned_data['donor'] = donor
            self.instance.donor = donor

        responsible = self._resolve_person(
            selected=cleaned_data.get('responsible'),
            typed_name=(cleaned_data.get('new_responsible_name') or '').strip(),
            field_name='new_responsible_name',
            required=contribution_amount > zero,
            person_label='responsável',
            created_attribute='created_responsible',
        )
        if responsible and not self.created_responsible:
            cleaned_data['responsible'] = responsible
            self.instance.responsible = responsible

        return cleaned_data

    def _resolve_person(
        self,
        *,
        selected,
        typed_name,
        field_name,
        required,
        person_label,
        created_attribute,
    ):
        if selected:
            return selected
        if not typed_name:
            if required:
                self.add_error(field_name, f'Busque ou informe o nome do {person_label}.')
            return None

        matches = self.fields['donor'].queryset.filter(name__iexact=typed_name)
        match_count = matches.count()
        if match_count == 1:
            return matches.get()
        if match_count > 1:
            self.add_error(
                field_name,
                f'Há mais de um doador com este nome. Escolha uma opção da lista.',
            )
            return None
        if not self.allow_new_donor:
            self.add_error(
                field_name,
                f'Em uma edição, escolha um {person_label} já cadastrado.',
            )
            return None

        person = Donor(name=typed_name)
        try:
            person.full_clean()
        except ValidationError as error:
            self.add_error(field_name, error)
            return None

        setattr(self, created_attribute, person)
        return person

    def _post_clean(self):
        super()._post_clean()
        if self.created_donor:
            self._errors.pop('donor', None)
        if self.created_responsible:
            self._errors.pop('responsible', None)


class DonationFilterForm(forms.Form):
    q = forms.CharField(
        label='Doador',
        required=False,
        widget=forms.TextInput(
            attrs={
                'autocomplete': 'off',
                'data-donor-filter-input': '',
                'placeholder': 'Digite o nome do doador',
            }
        ),
    )
    start_date = forms.DateField(
        label='Data inicial',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    end_date = forms.DateField(
        label='Data final',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    payment_method = forms.ChoiceField(
        choices=[('', 'Todas as formas'), *Donation.PaymentMethod.choices],
        label='Forma de recebimento',
        required=False,
    )
    status = forms.ChoiceField(
        choices=[('', 'Todos os status'), *Donation.Status.choices],
        label='Status',
        required=False,
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and start_date > end_date:
            self.add_error('end_date', 'A data final deve ser igual ou posterior à inicial.')

        return cleaned_data


class CancellationForm(forms.ModelForm):
    cancellation_reason = forms.CharField(label='Motivo do cancelamento', min_length=5, max_length=2000, widget=forms.Textarea(attrs={'rows': 4}))

    class Meta:
        model = Donation
        fields = ['cancellation_reason']
