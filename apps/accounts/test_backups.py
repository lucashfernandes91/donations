from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase
from django.conf import settings

from .backups import backup_sqlite


class BackupTests(SimpleTestCase):
    def test_backup_is_readable_and_does_not_replace_source_or_previous_copy(self):
        with TemporaryDirectory() as folder:
            source = Path(folder) / 'source.sqlite3'
            with closing(sqlite3.connect(source)) as database:
                database.execute('CREATE TABLE example (name TEXT)')
                database.execute('INSERT INTO example VALUES (?)', ['Maria'])
                database.commit()
            original = source.read_bytes()
            first = backup_sqlite(source, Path(folder) / 'backups')
            second = backup_sqlite(source, Path(folder) / 'backups')
            self.assertNotEqual(first, second)
            self.assertEqual(source.read_bytes(), original)
            with closing(sqlite3.connect(first)) as database:
                self.assertEqual(database.execute('SELECT name FROM example').fetchall(), [('Maria',)])
                self.assertEqual(database.execute('PRAGMA integrity_check').fetchone(), ('ok',))

    def test_invalid_source_does_not_leave_a_broken_backup(self):
        with TemporaryDirectory() as folder:
            source = Path(folder) / 'invalid.sqlite3'
            source.write_bytes(b'invalid database')
            with self.assertRaises(sqlite3.DatabaseError):
                backup_sqlite(source, Path(folder) / 'backups')
            self.assertEqual(list((Path(folder) / 'backups').iterdir()), [])

    def test_command_rejects_public_destination(self):
        with self.assertRaises(CommandError):
            call_command('backup_database', directory=settings.BASE_DIR / 'static' / 'backups')
