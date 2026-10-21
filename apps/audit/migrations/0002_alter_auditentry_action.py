from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('audit', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditentry',
            name='action',
            field=models.CharField(
                choices=[
                    ('create', 'Cadastro'),
                    ('update', 'Alteração'),
                    ('cancel', 'Cancelamento'),
                    ('delete', 'Exclusão'),
                ],
                max_length=20,
            ),
        ),
    ]
