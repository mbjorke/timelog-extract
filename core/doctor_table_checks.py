"""File and SQLite DB check helpers for gittan doctor (extracted from cli_doctor_sources_projects)."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path

from rich.table import Table

from core.sqlite_backup import sqlite_db_check_detail

# Doctor probes only fixed Chrome/Screen Time tables; identifiers are not parameterized in SQLite.
_DOCTOR_SQL_TABLES = frozenset({"urls", "ZOBJECT"})


@dataclass(frozen=True)
class DoctorCheckStyle:
    """Rich icon/style tokens for doctor file and SQLite check rows."""

    ok_icon: str
    warn_icon: str
    fail_icon: str
    style_muted: str


def doctor_check_file(table: Table, path: Path, label: str, style: DoctorCheckStyle) -> bool:
    """Append a file accessibility row to the doctor table; return True when readable."""
    if not path.exists():
        table.add_row(label, style.fail_icon, f"[{style.style_muted}]Not found: {path}[/{style.style_muted}]")
        return False
    if not os.access(path, os.R_OK):
        table.add_row(
            label,
            style.warn_icon,
            f"[{style.style_muted}]No read permission: {path}[/{style.style_muted}]",
        )
        return False
    table.add_row(label, style.ok_icon, f"[{style.style_muted}]Accessible[/{style.style_muted}]")
    return True


def _sqlite_live_locked(path: Path) -> bool:
    """Return True when the live SQLite file rejects reads with a lock error."""
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=0) as conn:
            conn.execute("SELECT 1").fetchone()
        return False
    except sqlite3.OperationalError as exc:
        return "database is locked" in str(exc).lower()
    except (OSError, PermissionError, sqlite3.Error):
        return False


def _sqlite_copy_query(path: Path, *, table_name: str | None) -> None:
    """Copy a SQLite DB to a temp file and run the probe query; raise on failure."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        shutil.copy2(path, tmp_path)
        with sqlite3.connect(tmp_path) as conn:
            if table_name:
                conn.execute(f"SELECT count(*) FROM {table_name} LIMIT 1").fetchone()
            else:
                conn.execute("SELECT count(*) FROM sqlite_master LIMIT 1").fetchone()
    finally:
        if os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def sqlite_db_probe_ok(path: Path, *, table_name: str | None = None) -> bool:
    """Return True when a doctor SQLite probe would succeed (no UI row)."""
    if table_name is not None and table_name not in _DOCTOR_SQL_TABLES:
        raise ValueError(f"unsupported doctor table name: {table_name!r}")
    if not path.exists():
        return False
    if _sqlite_live_locked(path):
        return False
    try:
        _sqlite_copy_query(path, table_name=table_name)
        return True
    except (OSError, PermissionError, sqlite3.Error):
        return False


def _doctor_sqlite_probe_row(
    table: Table,
    path: Path,
    label: str,
    style: DoctorCheckStyle,
    *,
    table_name: str | None,
    ok_detail_base: str,
) -> bool:
    if not path.exists():
        table.add_row(label, style.fail_icon, f"[{style.style_muted}]DB not found[/{style.style_muted}]")
        return False
    if _sqlite_live_locked(path):
        table.add_row(
            label,
            style.warn_icon,
            f"[{style.style_muted}]DB locked (try closing app)[/{style.style_muted}]",
        )
        return False

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_path = tmp.name
        shutil.copy2(path, tmp_path)
        with sqlite3.connect(tmp_path) as conn:
            if table_name:
                conn.execute(f"SELECT count(*) FROM {table_name} LIMIT 1").fetchone()
            else:
                conn.execute("SELECT count(*) FROM sqlite_master LIMIT 1").fetchone()
        detail = sqlite_db_check_detail(path, base=ok_detail_base)
        table.add_row(label, style.ok_icon, f"[{style.style_muted}]{detail}[/{style.style_muted}]")
        return True
    except sqlite3.Error as e:
        table.add_row(label, style.fail_icon, f"[{style.style_muted}]Query failed: {e}[/{style.style_muted}]")
        return False
    except PermissionError:
        table.add_row(
            label,
            style.fail_icon,
            f"[{style.style_muted}]Full Disk Access required[/{style.style_muted}]",
        )
        return False
    except OSError as e:
        table.add_row(label, style.fail_icon, f"[{style.style_muted}]Probe failed: {e}[/{style.style_muted}]")
        return False
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def doctor_probe_sqlite(table: Table, path: Path, label: str, style: DoctorCheckStyle) -> bool:
    """Probe a SQLite DB without requiring a known table name."""
    return _doctor_sqlite_probe_row(
        table,
        path,
        label,
        style,
        table_name=None,
        ok_detail_base="DB OK",
    )


def doctor_check_db(table: Table, path: Path, label: str, table_name: str, style: DoctorCheckStyle) -> bool:
    """Probe a SQLite DB via temp copy and append a status row; return True on success."""
    if table_name not in _DOCTOR_SQL_TABLES:
        raise ValueError(f"unsupported doctor table name: {table_name!r}")
    return _doctor_sqlite_probe_row(
        table,
        path,
        label,
        style,
        table_name=table_name,
        ok_detail_base="DB query successful",
    )
