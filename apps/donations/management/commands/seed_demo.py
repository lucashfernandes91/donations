from calendar import monthrange
from decimal import Decimal
from random import Random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.audit.mixins import snapshot
from apps.audit.models import AuditEntry
from apps.dashboard.services import month_start
from apps.donations.models import Donation
from apps.donors.models import Donor


PREFIX = 'DEMO-ANUAL-'
MONTH_COUNTS = [5, 7, 9, 6, 8, 11, 7, 10, 6, 9, 12, 10]


class Command(BaseCommand):
    help = 'Cria um lote identificado de 100 doações fictícias em 12 meses, sem duplicar uma carga anterior.'

    @transaction.atomic
    def handle(self, *args, **options):
        existing = Donation.objects.filter(receipt_number__startswith=PREFIX).count()
        if existing == 100:
            self.stdout.write('O lote de 100 doações de demonstração já existe. Nenhuma alteração realizada.')
            return
        if existing:
            raise CommandError('Já existe um lote parcial de demonstração. Revise-o antes de continuar.')

        actor, created = get_user_model().objects.get_or_create(
            username='carga-demonstracao',
            defaults={'is_active': False, 'first_name': 'Carga de demonstração'},
        )
        if not created:
            raise CommandError('O usuário reservado carga-demonstracao já existe. Nenhum dado foi alterado.')
        actor.set_unusable_password()
        actor.save(update_fields=['password'])

        def record(instance):
            AuditEntry.objects.create(
                actor=actor, entity=instance._meta.label_lower, object_id=instance.pk,
                object_label=str(instance)[:300], action='create', before={}, after=snapshot(instance),
            )
            return instance

        names = [
            'Ana Silva', 'Bruno Costa', 'Carla Santos', 'Daniel Oliveira', 'Elisa Souza',
            'Felipe Lima', 'Gabriela Rocha', 'Henrique Alves', 'Isabela Martins', 'João Pereira',
            'Larissa Almeida', 'Marcos Ribeiro', 'Natália Ferreira', 'Otávio Gomes', 'Patrícia Araujo',
            'Rafael Carvalho', 'Sofia Teixeira', 'Tiago Moreira', 'Valéria Mendes', 'William Barbosa',
            'Adriana Cardoso', 'Beatriz Nunes', 'César Machado', 'Débora Batista', 'Eduardo Vieira',
        ]
        donors = [record(Donor.objects.create(
            name=f'{name} (Demonstração)', email=f'doador{index:02d}@example.invalid',
            notes='Dados fictícios para relatórios. Lote DEMO-ANUAL. Sem CPF ou telefone reais.',
        )) for index, name in enumerate(names, start=1)]
        today = timezone.localdate()
        random = Random(20260911)
        methods = ['pix', 'cash', 'pix', 'bank_transfer', 'card', 'pix', 'cash', 'check', 'other', 'pix']
        base_amounts = [20, 30, 50, 75, 100, 150, 200, 250, 350, 500, 750, 1000]
        number = 0
        for offset, count in zip(range(-11, 1), MONTH_COUNTS):
            first = month_start(today, offset)
            last_day = today.day if offset == 0 else monthrange(first.year, first.month)[1]
            total = Decimal('0.00')
            for item in range(count):
                number += 1
                day = 1 + item * (last_day - 1) // (count - 1)
                amount = (Decimal(random.choice(base_amounts)) + Decimal(random.choice([0, 0, 0, 50, 90])) / 100).quantize(Decimal('0.01'))
                donation = Donation.objects.create(
                    donor=donors[(number - 1) % len(donors)],
                    receipt_number=f'{PREFIX}{number:03d}', donation_date=first.replace(day=day),
                    amount=amount, payment_method=methods[(number - 1) % len(methods)],
                    created_by=actor, notes='DOAÇÃO FICTÍCIA — lote DEMO-ANUAL para testes de relatórios.',
                )
                record(donation)
                total += amount
            self.stdout.write(f'{first:%m/%Y}: {count} doações; R$ {total:.2f}')
        self.stdout.write(self.style.SUCCESS('Criadas 100 doações, 25 doadores e 125 registros de auditoria.'))
