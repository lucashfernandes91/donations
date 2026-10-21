from django.db import migrations


def remove_category_audit_data(apps, schema_editor):
    AuditEntry = apps.get_model('audit', 'AuditEntry')
    AuditEntry.objects.filter(entity='donations.donationcategory').delete()

    for entry in AuditEntry.objects.filter(entity='donations.donation').iterator():
        before = dict(entry.before or {})
        after = dict(entry.after or {})
        changed = 'categoria' in before or 'categoria' in after
        before.pop('categoria', None)
        after.pop('categoria', None)
        if changed:
            AuditEntry.objects.filter(pk=entry.pk).update(before=before, after=after)


class Migration(migrations.Migration):

    dependencies = [
        ('audit', '0002_alter_auditentry_action'),
        ('donations', '0005_remove_donation_category_delete_donationcategory'),
    ]

    operations = [
        migrations.RunPython(remove_category_audit_data, migrations.RunPython.noop),
    ]
