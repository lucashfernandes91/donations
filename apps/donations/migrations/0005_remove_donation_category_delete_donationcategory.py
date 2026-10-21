from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('donations', '0004_donation_responsible'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='donation',
            name='category',
        ),
        migrations.DeleteModel(
            name='DonationCategory',
        ),
    ]
