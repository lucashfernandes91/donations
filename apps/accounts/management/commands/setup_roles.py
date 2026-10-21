from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Configura os perfis Administrador, Operador e Consulta sem atribuí-los a usuários.'

    @transaction.atomic
    def handle(self, *args, **options):
        read = {'view_donation', 'view_donor'}
        operate = read | {'add_donation', 'change_donation', 'add_donor', 'change_donor'}
        admin = operate | {'cancel_donation', 'view_auditentry'}
        available = Permission.objects.filter(content_type__app_label__in=['donations', 'donors', 'audit'])
        for name, codes in [('Consulta', read), ('Operador', operate), ('Administrador', admin)]:
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.set(available.filter(codename__in=codes))
        self.stdout.write(self.style.SUCCESS('Perfis configurados. Atribua os grupos pelo administrador Django.'))
