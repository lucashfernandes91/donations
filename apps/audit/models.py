from django.conf import settings
from django.db import models


class AuditQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise TypeError('Registros de auditoria não podem ser alterados.')

    def delete(self):
        raise TypeError('Registros de auditoria não podem ser excluídos.')


class AuditEntry(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    entity = models.CharField(max_length=100)
    object_id = models.PositiveBigIntegerField()
    object_label = models.CharField(max_length=300)
    action = models.CharField(max_length=20, choices=[('create', 'Cadastro'), ('update', 'Alteração'), ('cancel', 'Cancelamento'), ('delete', 'Exclusão')])
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = AuditQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at', '-pk']
        default_permissions = ('view',)
        indexes = [models.Index(fields=['entity', 'object_id'])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise TypeError('Registros de auditoria não podem ser alterados.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise TypeError('Registros de auditoria não podem ser excluídos.')

    @property
    def changes(self):
        return [
            {'field': key, 'before': self.before.get(key, '—'), 'after': self.after.get(key, '—')}
            for key in sorted(self.before.keys() | self.after.keys())
            if self.before.get(key) != self.after.get(key)
        ]
