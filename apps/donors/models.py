from django.core.validators import EmailValidator
from django.db import models

from .validators import normalize_cpf, validate_cpf


class Donor(models.Model):
    name = models.CharField('nome', max_length=255)
    cpf = models.CharField('CPF', max_length=14, blank=True, validators=[validate_cpf])
    phone = models.CharField('telefone', max_length=30, blank=True)
    email = models.EmailField('e-mail', blank=True, validators=[EmailValidator()])
    notes = models.TextField('observação', blank=True)
    is_active = models.BooleanField('ativo', default=True)
    is_responsible = models.BooleanField('responsável', default=False)
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        ordering = ['name', 'pk']
        verbose_name = 'doador'
        verbose_name_plural = 'doadores'

    def clean(self):
        super().clean()
        if self.cpf:
            validate_cpf(self.cpf)
            self.cpf = normalize_cpf(self.cpf)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
