from __future__ import annotations

from datetime import timezone
from email import message_from_binary_file
from email.header import decode_header as email_decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable, List, Sequence, Tuple

from collectors.ai_logs import _anchors


def mail_event_parts(subject: str, to_display: str) -> tuple[str | None, str]:
    """Split sent-mail rows into session-style label (subject) and detail (recipient)."""
    subj = (subject or "").strip()
    recipient = (to_display or "").strip()[:80]
    if subj:
        return subj[:80], recipient
    if recipient:
        return "(no subject)", recipient
    return None, ""


def detect_mail_root(home: Path) -> Tuple[Path | None, str]:
    mail_base = home / "Library" / "Mail"
    if not mail_base.exists():
        return None, "~/Library/Mail not found."
    try:
        versions = sorted(mail_base.glob("V[0-9]*"), reverse=True)
    except PermissionError:
        return None, "Access denied to ~/Library/Mail."
    if not versions:
        return None, "No versioned Mail directory found."
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
        print(f"  [Warning] {status}")
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
        seen_paths: set[Path] = set()
        for pat in sent_patterns:
            for path in mail_dir.glob(pat):
                resolved = path.resolve()
                if resolved in seen_paths:
                    continue
                seen_paths.add(resolved)
                emlx_files.append(path)
    except PermissionError:
        print("  [Warning] Access denied to Mail folders.")
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

    senders: set[str] = set()
    if default_email:
        senders.add(default_email.strip().lower())

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

            from_addr = _decode_header(msg.get("From", "") or "").lower()
            # Sent-folder reads are outbound-only; restrict by From only when --email is set.
            if senders and not any(sender in from_addr for sender in senders):
                continue

            to_addr = (msg.get("To", "") or "").lower()
            subject_raw = msg.get("Subject", "") or ""
            subject = _decode_header(subject_raw)
            project = classify_project(f"{to_addr} {subject}", profiles)

            page_label, detail = mail_event_parts(subject, msg.get("To", "") or "")
            anchors = _anchors(label=page_label) if page_label else None
            results.append(make_event("Apple Mail", ts, detail, project, anchors=anchors))
        except PermissionError:
            print("  [Warning] Cannot read individual message — check Full Disk Access.")
            break
        except Exception:
            continue

    return results
