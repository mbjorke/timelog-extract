from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

from collectors.mail import collect_apple_mail, mail_event_parts


def _write_emlx(path: Path, headers: str, body: str = "") -> None:
    payload = (headers + "\r\n\r\n" + body).encode("utf-8")
    path.write_bytes(f"{len(payload)}\n".encode("ascii") + payload)


def _make_event(source, ts, detail, project, anchors=None):
    event = {"source": source, "timestamp": ts, "detail": detail, "project": project}
    if anchors:
        event["anchors"] = anchors
    return event


class MailEventPartsTests(unittest.TestCase):
    def test_subject_and_recipient_split(self):
        self.assertEqual(
            mail_event_parts("Re: invoice Q2", "customer-a@customer-a.test"),
            ("Re: invoice Q2", "customer-a@customer-a.test"),
        )

    def test_empty_subject_uses_placeholder(self):
        self.assertEqual(
            mail_event_parts("", "customer-a@customer-a.test"),
            ("(no subject)", "customer-a@customer-a.test"),
        )


class MailCollectorTests(unittest.TestCase):
    def _collect(self, home: Path, profiles, **kwargs):
        dt_from = datetime(2026, 4, 10, 0, 0, tzinfo=timezone.utc)
        dt_to = datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc)
        return collect_apple_mail(
            profiles,
            dt_from,
            dt_to,
            home,
            kwargs.get("default_email"),
            kwargs.get("classify", lambda _hay, _profiles: "project-alpha"),
            _make_event,
            "Uncategorized",
        )

    def test_sent_message_splits_subject_and_recipient(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            mail_dir = home / "Library" / "Mail" / "V10" / "Skickade.mbox" / "Messages"
            mail_dir.mkdir(parents=True)
            ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
            _write_emlx(
                mail_dir / "1.emlx",
                "\r\n".join(
                    [
                        "From: sender@project-alpha.test",
                        "To: customer-a@customer-a.test",
                        "Subject: Re: invoice Q2",
                        f"Date: {format_datetime(ts)}",
                    ]
                ),
            )
            profiles = [{"name": "project-alpha", "email": "other@project-alpha.test", "match_terms": ["invoice"]}]
            out = self._collect(home, profiles)
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["anchors"]["label"], "Re: invoice Q2")
            self.assertEqual(out[0]["detail"], "customer-a@customer-a.test")

    def test_uncategorized_mail_is_kept_for_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            mail_dir = home / "Library" / "Mail" / "V10" / "Skickade.mbox" / "Messages"
            mail_dir.mkdir(parents=True)
            ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
            _write_emlx(
                mail_dir / "1.emlx",
                "\r\n".join(
                    [
                        "From: sender@project-alpha.test",
                        "To: unknown@example.test",
                        "Subject: Quick hello",
                        f"Date: {format_datetime(ts)}",
                    ]
                ),
            )
            profiles = [{"name": "project-alpha", "match_terms": ["invoice"]}]
            out = self._collect(
                home,
                profiles,
                classify=lambda _hay, _profiles: "Uncategorized",
            )
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["project"], "Uncategorized")
            self.assertEqual(out[0]["anchors"]["label"], "Quick hello")

    def test_email_flag_filters_by_from_address(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            mail_dir = home / "Library" / "Mail" / "V10" / "Skickade.mbox" / "Messages"
            mail_dir.mkdir(parents=True)
            ts = datetime(2026, 4, 10, 14, 0, tzinfo=timezone.utc)
            _write_emlx(
                mail_dir / "1.emlx",
                "\r\n".join(
                    [
                        "From: work@project-alpha.test",
                        "To: customer-a@customer-a.test",
                        "Subject: Work mail",
                        f"Date: {format_datetime(ts)}",
                    ]
                ),
            )
            _write_emlx(
                mail_dir / "2.emlx",
                "\r\n".join(
                    [
                        "From: personal@example.test",
                        "To: friend@example.test",
                        "Subject: Personal mail",
                        f"Date: {format_datetime(ts)}",
                    ]
                ),
            )
            profiles = [{"name": "project-alpha", "match_terms": ["customer-a"]}]
            out = self._collect(home, profiles, default_email="work@project-alpha.test")
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["anchors"]["label"], "Work mail")


if __name__ == "__main__":
    unittest.main()
