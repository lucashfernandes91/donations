from django import forms

from .models import Donor
from .validators import normalize_document, validate_cpf


class DonorForm(forms.ModelForm):
    cpf = forms.CharField(
        label='CPF ou CNPJ',
        max_length=18,
        required=False,
        validators=[validate_cpf],
        widget=forms.TextInput(attrs={
            'data-document-input': '',
            'inputmode': 'numeric',
            'autocomplete': 'off',
            'maxlength': 18,
            'minlength': 14,
            'placeholder': 'CPF ou CNPJ',
            'pattern': r'(?:\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})',
        }),
    )

    def clean_cpf(self):
        return normalize_document(self.cleaned_data['cpf'])

    class Meta:
        model = Donor
        fields = ['name', 'cpf', 'phone', 'email', 'notes', 'is_active']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 4}),
        }
