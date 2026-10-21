from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone


def generate_receipt_number():
    date_part = timezone.localdate().strftime('%Y%m%d')
    return f'REC-{date_part}-{uuid4().hex[:8].upper()}'


class Donation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Ativa'
        CANCELLED = 'cancelled', 'Cancelada'

    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'Dinheiro'
        PIX = 'pix', 'PIX'
        BANK_TRANSFER = 'bank_transfer', 'Transferência bancária'
        CARD = 'card', 'Cartão'
        CHECK = 'check', 'Cheque'
        OTHER = 'other', 'Outro'

    donor = models.ForeignKey(
        'donors.Donor',
        on_delete=models.PROTECT,
        related_name='donations',
        verbose_name='doador',
    )
    responsible = models.ForeignKey(
        'donors.Donor',
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name='donations_as_responsible',
        verbose_name='responsável',
    )
    receipt_number = models.CharField(
        'número do comprovante',
        default=generate_receipt_number,
        editable=False,
        max_length=30,
        unique=True,
    )
    donation_receipt_number = models.PositiveBigIntegerField(
        'número do recibo de doação',
        blank=True,
        editable=False,
        null=True,
        unique=True,
    )
    contribution_receipt_number = models.PositiveBigIntegerField(
        'número do recibo de contribuição',
        blank=True,
        editable=False,
        null=True,
        unique=True,
    )
    donation_date = models.DateField('data da doação')
    amount = models.DecimalField(
        'valor',
        decimal_places=2,
        max_digits=12,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    donation_amount = models.DecimalField(
        'doação',
        decimal_places=2,
        default=Decimal('0.00'),
        max_digits=12,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    contribution_amount = models.DecimalField(
        'contribuição',
        decimal_places=2,
        default=Decimal('0.00'),
        max_digits=12,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    payment_method = models.CharField(
        'forma de recebimento',
        choices=PaymentMethod.choices,
        max_length=20,
    )
    notes = models.TextField('observação', blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='donations_created',
        verbose_name='criada por',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='donations_updated',
        verbose_name='atualizada por',
    )
    created_at = models.DateTimeField('criada em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizada em', auto_now=True)

    status = models.CharField('status', max_length=12, choices=Status.choices, default=Status.ACTIVE)
    cancellation_reason = models.TextField('motivo do cancelamento', blank=True)
    cancelled_at = models.DateTimeField('cancelada em', null=True, blank=True)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='donations_cancelled', verbose_name='cancelada por')

    class Meta:
        ordering = ['-donation_date', '-created_at', '-pk']
        permissions = [('cancel_donation', 'Pode cancelar doações')]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name='donation_amount_must_be_positive',
            ),
            models.CheckConstraint(
                condition=(
                    Q(status='active', cancelled_at__isnull=True, cancelled_by__isnull=True, cancellation_reason='')
                    | (Q(status='cancelled', cancelled_at__isnull=False, cancelled_by__isnull=False) & ~Q(cancellation_reason=''))
                ),
                name='donation_cancellation_consistent',
            ),
        ]
        verbose_name = 'doação'
        verbose_name_plural = 'doações'

    def save(self, *args, **kwargs):
        self.full_clean()
        with transaction.atomic():
            fields = self._receipt_fields_to_allocate()
            for field, number in zip(fields, ReceiptNumberSequence.allocate(len(fields))):
                setattr(self, field, number)

            update_fields = kwargs.get('update_fields')
            if update_fields and fields:
                kwargs['update_fields'] = set(update_fields) | set(fields)
            super().save(*args, **kwargs)

    def _receipt_fields_to_allocate(self):
        zero = Decimal('0.00')
        candidates = (
            ('donation_receipt_number', 'donation_amount'),
            ('contribution_receipt_number', 'contribution_amount'),
        )
        if self._state.adding:
            return [
                receipt_field
                for receipt_field, amount_field in candidates
                if getattr(self, receipt_field) is None and (getattr(self, amount_field) or zero) > zero
            ]

        previous = type(self).objects.select_for_update().only(
            'donation_amount',
            'contribution_amount',
        ).get(pk=self.pk)
        return [
            receipt_field
            for receipt_field, amount_field in candidates
            if (
                getattr(self, receipt_field) is None
                and (getattr(previous, amount_field) or zero) <= zero
                and (getattr(self, amount_field) or zero) > zero
            )
        ]

    def clean(self):
        super().clean()
        zero = Decimal('0.00')
        if (
            self._state.adding
            and self.amount
            and self.donation_amount == zero
            and self.contribution_amount == zero
        ):
            self.donation_amount = self.amount
        total = (self.donation_amount or zero) + (self.contribution_amount or zero)
        if total <= zero:
            raise ValidationError('Informe um valor de doação ou contribuição maior que zero.')
        self.amount = total.quantize(Decimal('0.01'))

    def __str__(self):
        return f'{self.receipt_number} — {self.donor}'


class ReceiptNumberSequence(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    next_number = models.PositiveBigIntegerField(
        'próximo número do recibo',
        default=1,
        help_text=(
            'Número que será atribuído ao próximo recibo. '
            'Doação e contribuição consomem um número cada.'
        ),
        validators=[MinValueValidator(1)],
    )
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'controle da numeração dos recibos'
        verbose_name_plural = 'controle da numeração dos recibos'

    @classmethod
    def allocate(cls, quantity):
        if quantity <= 0:
            return []

        with transaction.atomic():
            sequence, _ = cls.objects.select_for_update().get_or_create(
                pk=1,
                defaults={'next_number': 1},
            )
            candidate = sequence.next_number
            allocated = []
            while len(allocated) < quantity:
                already_used = Donation.objects.filter(
                    Q(donation_receipt_number=candidate)
                    | Q(contribution_receipt_number=candidate)
                ).exists()
                if not already_used:
                    allocated.append(candidate)
                candidate += 1

            sequence.next_number = candidate
            sequence.save(update_fields=['next_number', 'updated_at'])
            return allocated

    def clean(self):
        super().clean()
        if self.pk != 1:
            raise ValidationError('Deve existir somente um controle de numeração dos recibos.')

    def __str__(self):
        return f'Próximo recibo: {self.next_number}'
