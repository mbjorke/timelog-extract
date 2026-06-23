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


@dataclass(frozen=True)
class DoctorCheckStyle:
    ok_icon: str
    warn_icon: str
    fail_icon: str
    style_muted: str


def doctor_check_file(table: Table, path: Path, label: str, style: DoctorCheckStyle) -> bool:
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


def doctor_check_db(table: Table, path: Path, label: str, table_name: str, style: DoctorCheckStyle) -> bool:
    if not path.exists():
        table.add_row(label, style.fail_icon, f"[{style.style_muted}]DB not found[/{style.style_muted}]")
        return False

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    try:
        shutil.copy2(path, tmp.name)
        conn = sqlite3.connect(tmp.name)
        c = conn.cursor()
        c.execute(f"SELECT count(*) FROM {table_name} LIMIT 1")
        c.fetchone()
        conn.close()
        detail = sqlite_db_check_detail(path)
        table.add_row(label, style.ok_icon, f"[{style.style_muted}]{detail}[/{style.style_muted}]")
        return True
    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            table.add_row(
                label,
                style.warn_icon,
                f"[{style.style_muted}]DB locked (try closing app)[/{style.style_muted}]",
            )
        else:
            table.add_row(label, style.fail_icon, f"[{style.style_muted}]Query failed: {e}[/{style.style_muted}]")
        return False
    except PermissionError:
        table.add_row(
            label,
            style.fail_icon,
            f"[{style.style_muted}]Full Disk Access required[/{style.style_muted}]",
        )
        return False
    finally:
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
