from pathlib import Path
from contextlib import closing
import sqlite3
from uuid import uuid4


def backup_sqlite(source: Path, directory: Path) -> Path:
    source = source.resolve(strict=True)
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = directory / f'donations-{uuid4().hex}.sqlite3'
    with target.open('xb'):
        target.chmod(0o600)
    try:
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as origin:
            with closing(sqlite3.connect(target)) as destination:
                origin.backup(destination)
                if destination.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise ValueError('A cópia não passou na verificação de integridade.')
                if destination.execute('PRAGMA foreign_key_check').fetchall():
                    raise ValueError('A cópia contém referências inválidas.')
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return target
