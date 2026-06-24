#!/usr/bin/env python3
"""Safely migrate project worklogs into a central ~/.gittan/worklogs store."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DEFAULT_DEST_ROOT = Path.home() / ".gittan" / "worklogs"


@dataclass
class MigrationResult:
    project: str
    source: Path
    destination: Path
    status: str
    message: str
    backup_path: Path | None = None


def _now_stamp() -> str:
    return datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _parse_mapping(raw: str, default_source_root: Path) -> tuple[str, Path]:
    if "=" in raw:
        project, source_text = raw.split("=", 1)
        project = project.strip()
        source = Path(source_text.strip()).expanduser()
    else:
        project = raw.strip()
        source = default_source_root / project / "TIMELOG.md"
    if not project:
        raise ValueError(f"invalid mapping {raw!r}: project name is empty")
    return project, source


def _normalize_newline(text: str) -> str:
    if not text:
        return text
    return text if text.endswith("\n") else f"{text}\n"


def _source_marker(project: str, source: Path, digest: str) -> str:
    return f"<!-- migrated-from:{project}:{source}:{digest} -->"


def _backup_destination_if_needed(destination: Path, dry_run: bool) -> Path | None:
    if not destination.exists():
        return None
    backup = destination.parent / f"{destination.name}.backup.{_now_stamp()}"
    if not dry_run:
        shutil.copy2(destination, backup)
    return backup


def migrate_one(project: str, source: Path, destination: Path, dry_run: bool) -> MigrationResult:
    if not source.exists():
        return MigrationResult(project, source, destination, "missing_source", "source file is missing")
    if source.is_dir():
        return MigrationResult(project, source, destination, "invalid_source", "source path is a directory")
    try:
        source_content = source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, PermissionError) as exc:
        return MigrationResult(
            project,
            source,
            destination,
            "read_error",
            f"cannot read source: {exc}",
        )
    if not source_content.strip():
        return MigrationResult(project, source, destination, "empty_source", "source file is empty")

    normalized_source = _normalize_newline(source_content)
    digest = _sha256_text(normalized_source)
    marker = _source_marker(project, source.resolve(), digest)

    try:
        destination_text = destination.read_text(encoding="utf-8") if destination.exists() else ""
    except (OSError, UnicodeDecodeError, PermissionError) as exc:
        return MigrationResult(
            project,
            source,
            destination,
            "read_error",
            f"cannot read destination: {exc}",
        )
    if marker in destination_text:
        return MigrationResult(project, source, destination, "unchanged", "matching content already migrated")

    backup = _backup_destination_if_needed(destination, dry_run=dry_run)
    payload = (
        f"\n{marker}\n"
        f"<!-- migrated-at:{datetime.now().astimezone().isoformat()} -->\n"
        f"{normalized_source}"
    )
    if not destination_text:
        payload = f"{marker}\n<!-- migrated-at:{datetime.now().astimezone().isoformat()} -->\n{normalized_source}"
    elif not destination_text.endswith("\n"):
        payload = f"\n{payload}"

    if not dry_run:
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("a", encoding="utf-8") as fh:
                fh.write(payload)
        except OSError as exc:
            return MigrationResult(
                project,
                source,
                destination,
                "write_error",
                f"cannot write destination: {exc}",
                backup_path=backup,
            )

    return MigrationResult(
        project,
        source,
        destination,
        "migrated",
        "appended source history into destination",
        backup_path=backup,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Migrate per-project worklog files into a central destination directory safely."
    )
    parser.add_argument(
        "--mapping",
        action="append",
        default=[],
        help=(
            "Project mapping, format: project=/absolute/or/relative/source.md. "
            "If source is omitted (project only), source defaults to "
            "--default-source-root/<project>/TIMELOG.md."
        ),
    )
    parser.add_argument(
        "--default-source-root",
        default=str(Path.cwd()),
        help="Base directory used when a mapping omits explicit source path (default: current working directory).",
    )
    parser.add_argument(
        "--dest-root",
        default=str(DEFAULT_DEST_ROOT),
        help="Central destination directory for migrated worklogs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without writing destination files or backups.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.mapping:
        parser.error("at least one --mapping is required")

    default_source_root = Path(args.default_source_root).expanduser()
    dest_root = Path(args.dest_root).expanduser()
    results: list[MigrationResult] = []

    for raw in args.mapping:
        try:
            project, source = _parse_mapping(raw, default_source_root)
        except ValueError as exc:
            print(f"[error] {exc}")
            return 2
        if any(sep in project for sep in ("/", "\\")) or project in {".", ".."}:
            print(f"[error] invalid project name {project!r}: path separators are not allowed")
            return 2
        destination = dest_root / f"{project}.md"
        try:
            destination.resolve().relative_to(dest_root.resolve())
        except ValueError:
            print(f"[error] invalid project name {project!r}: resolves outside destination root")
            return 2
        result = migrate_one(project, source, destination, dry_run=args.dry_run)
        results.append(result)

    print("Project worklog migration results")
    print("=" * 33)
    for item in results:
        backup_note = f" backup={item.backup_path}" if item.backup_path else ""
        print(
            f"- {item.project}: {item.status} | source={item.source} | "
            f"destination={item.destination}{backup_note}"
        )
        print(f"  {item.message}")

    failures = [r for r in results if r.status in {"missing_source", "invalid_source", "read_error", "write_error"}]
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
