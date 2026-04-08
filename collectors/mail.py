from __future__ import annotations

from datetime import timezone
from email import message_from_binary_file
from email.header import decode_header as email_decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable, List, Sequence, Tuple


def detect_mail_root(home: Path) -> Tuple[Path | None, str]:
    mail_base = home / "Library" / "Mail"
    if not mail_base.exists():
        return None, "~/Library/Mail hittades inte."
    try:
        versions = sorted(mail_base.glob("V[0-9]*"), reverse=True)
    except PermissionError:
        return None, "Åtkomst nekad till ~/Library/Mail."
    if not versions:
        return None, "Ingen versionerad Mail-katalog hittades."
    return versions[0], "ok"


def collect_apple_mail(
    profiles,
    dt_from,
    dt_to,
    home: Path,
    default_email: str | None,
    classify_project: Callable,
    make_event: Callable,
    uncategorized: str,
) -> List[dict]:
    results = []
    mail_dir, status = detect_mail_root(home)
    if mail_dir is None:
        print(f"  [Varning] {status}")
        return results

    sent_patterns: Sequence[str] = [
        "**/Sent Messages.mbox/Messages/*.emlx",
        "**/Sent.mbox/Messages/*.emlx",
        "**/Skickade meddelanden.mbox/Messages/*.emlx",
        "**/Skickade.mbox/Messages/*.emlx",
        "**/[Ss]ent*/**/*.emlx",
    ]

    emlx_files = []
    try:
        for pat in sent_patterns:
            emlx_files.extend(mail_dir.glob(pat))
    except PermissionError:
        print("  [Varning] Åtkomst nekad till Mail-mappar.")
        return results

    def _decode_header(value):
        if not value:
            return ""
        parts = []
        for raw, charset in email_decode_header(value):
            if isinstance(raw, bytes):
                parts.append(raw.decode(charset or "utf-8", errors="replace"))
            else:
                parts.append(raw)
        return "".join(parts)

    senders = {p["email"].lower() for p in profiles if p["email"]}
    if default_email:
        senders.add(default_email.lower())

    for emlx_path in emlx_files:
        try:
            with open(emlx_path, "rb") as f:
                f.readline()
                msg = message_from_binary_file(f)

            date_str = msg.get("Date", "")
            if not date_str:
                continue
            try:
                ts = parsedate_to_datetime(date_str)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            if not (dt_from <= ts <= dt_to):
                continue

            from_addr = (msg.get("From", "") or "").lower()
            if senders and not any(sender in from_addr for sender in senders):
                continue

            to_addr = (msg.get("To", "") or "").lower()
            subject_raw = msg.get("Subject", "") or ""
            subject = _decode_header(subject_raw)
            project = classify_project(f"{to_addr} {subject}", profiles)
            if project == uncategorized:
                continue

            detail = f"-> {msg.get('To', '')[:35]}  \"{subject[:45]}\""
            results.append(make_event("Apple Mail", ts, detail, project))
        except PermissionError:
            print("  [Varning] Kan inte läsa enskilt mail — kontrollera Full Disk Access.")
            break
        except Exception:
            continue

    return results
