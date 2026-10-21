from django.contrib import admin

from .models import ReceiptNumberSequence


@admin.register(ReceiptNumberSequence)
class ReceiptNumberSequenceAdmin(admin.ModelAdmin):
    fields = ('next_number', 'updated_at')
    list_display = ('next_number', 'updated_at')
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        return not ReceiptNumberSequence.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
