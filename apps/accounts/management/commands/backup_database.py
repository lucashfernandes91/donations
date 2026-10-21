from pathlib import Path
import sqlite3

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.backups import backup_sqlite


class Command(BaseCommand):
    help = 'Cria uma cópia consistente e verificada do SQLite, sem substituir backups anteriores.'

    def add_arguments(self, parser):
        parser.add_argument('--directory', type=Path, default=settings.BASE_DIR / 'backups')

    def handle(self, *args, **options):
        database = settings.DATABASES['default']
        if database['ENGINE'] != 'django.db.backends.sqlite3' or str(database['NAME']).startswith(('file:', ':memory:')):
            raise CommandError('Este comando requer um banco SQLite em arquivo.')
        directory = options['directory'].resolve()
        public_paths = [settings.BASE_DIR / 'static', settings.BASE_DIR / 'media']
        public_paths += [Path(path) for path in [getattr(settings, 'STATIC_ROOT', None), getattr(settings, 'MEDIA_ROOT', None)] if path]
        if any(directory.is_relative_to(path.resolve()) for path in public_paths):
            raise CommandError('O backup não pode ficar em uma pasta de arquivos públicos.')
        try:
            target = backup_sqlite(Path(database['NAME']), directory)
        except (OSError, ValueError, sqlite3.Error) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f'Backup verificado: {target}'))
