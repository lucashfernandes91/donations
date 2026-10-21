import django.core.validators
from django.db import migrations, models


def create_receipt_number_sequence(apps, schema_editor):
    ReceiptNumberSequence = apps.get_model('donations', 'ReceiptNumberSequence')
    ReceiptNumberSequence.objects.get_or_create(pk=1, defaults={'next_number': 1})


class Migration(migrations.Migration):
    dependencies = [
        ('donations', '0006_remove_category_audit_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='donation',
            name='contribution_receipt_number',
            field=models.PositiveBigIntegerField(
                blank=True,
                editable=False,
                null=True,
                unique=True,
                verbose_name='número do recibo de contribuição',
            ),
        ),
        migrations.AddField(
            model_name='donation',
            name='donation_receipt_number',
            field=models.PositiveBigIntegerField(
                blank=True,
                editable=False,
                null=True,
                unique=True,
                verbose_name='número do recibo de doação',
            ),
        ),
        migrations.CreateModel(
            name='ReceiptNumberSequence',
            fields=[
                (
                    'id',
                    models.PositiveSmallIntegerField(
                        default=1,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    'next_number',
                    models.PositiveBigIntegerField(
                        default=1,
                        help_text=(
                            'Número que será atribuído ao próximo recibo. '
                            'Doação e contribuição consomem um número cada.'
                        ),
                        validators=[django.core.validators.MinValueValidator(1)],
                        verbose_name='próximo número do recibo',
                    ),
                ),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='atualizado em')),
            ],
            options={
                'verbose_name': 'controle da numeração dos recibos',
                'verbose_name_plural': 'controle da numeração dos recibos',
            },
        ),
        migrations.RunPython(create_receipt_number_sequence, migrations.RunPython.noop),
    ]
