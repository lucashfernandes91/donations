from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView

from .models import AuditEntry


class AuditListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = 'audit.view_auditentry'
    template_name = 'audit/list.html'
    context_object_name = 'entries'
    paginate_by = 25

    def get_queryset(self):
        queryset = AuditEntry.objects.select_related('actor')
        entity = self.request.GET.get('entity')
        object_id = self.request.GET.get('object_id', '')
        if entity:
            queryset = queryset.filter(entity=entity)
        if object_id:
            if not object_id.isdecimal() or len(object_id) > 18:
                return queryset.none()
            queryset = queryset.filter(object_id=int(object_id))
        return queryset
