import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction

from .models import AuditEntry


def snapshot(instance) -> dict:
    values = {}
    for field in instance._meta.concrete_fields:
        value = getattr(instance, field.name)
        if field.is_relation:
            value = f'{value} (#{getattr(instance, field.attname)})' if value is not None else None
        values[str(field.verbose_name)] = value
    return json.loads(json.dumps(values, cls=DjangoJSONEncoder))


class AuditedSaveMixin:
    audit_action = None

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST':
            with transaction.atomic():
                return super().dispatch(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_for_update() if self.request.method == 'POST' else queryset

    def form_valid(self, form):
        instance = form.instance
        before = snapshot(type(instance).objects.get(pk=instance.pk)) if instance.pk else {}
        response = super().form_valid(form)
        after = snapshot(self.object)
        if before != after:
            AuditEntry.objects.create(
                actor=self.request.user, entity=self.object._meta.label_lower,
                object_id=self.object.pk, object_label=str(self.object)[:300],
                action=self.audit_action or ('update' if before else 'create'),
                before=before, after=after,
            )
        return response
