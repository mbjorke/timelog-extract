"""Tests for core.timelog_totals — all-time TIMELOG.md hours per project."""

import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile


def _tz():
    return datetime.now().astimezone().tzinfo or timezone.utc


def _make_event(source, ts, detail, project, anchors=None):
    return {"source": source, "timestamp": ts, "local_ts": ts, "detail": detail, "project": project}


def _classify(text, profiles, fallback="Uncategorized"):
    for p in profiles:
        for term in p.get("match_terms", []):
            if term.lower() in text.lower():
                return p["name"]
    return fallback


class TestComputeTimelogProjectTotals(unittest.TestCase):
    def _run(self, md_content, profiles):
        from core.timelog_totals import compute_timelog_project_totals
        from core.sources import AI_SOURCES

        with NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(md_content)
            tmppath = Path(f.name)

        try:
            return compute_timelog_project_totals(
                worklog_path=tmppath,
                profiles=profiles,
                local_tz=_tz(),
                classify_project_fn=lambda text, profs: _classify(text, profs),
                make_event_fn=_make_event,
                source_name="TIMELOG.md",
                ai_sources=AI_SOURCES,
                gap_minutes=15,
                min_session_minutes=5,
                min_session_passive_minutes=5,
            )
        finally:
            tmppath.unlink(missing_ok=True)

    def test_empty_worklog_returns_empty_dict(self):
        result = self._run("", [{"name": "Project Alpha", "match_terms": ["alpha"]}])
        self.assertEqual(result, {})

    def test_single_project_across_two_months_is_summed(self):
        md = """
## 2026-01-10 10:00
- alpha work

## 2026-03-15 14:00
- more alpha work
"""
        profiles = [{"name": "Project Alpha", "match_terms": ["alpha"]}]
        result = self._run(md, profiles)
        self.assertIn("Project Alpha", result)
        self.assertGreater(result["Project Alpha"], 0)

    def test_no_history_project_absent_from_result(self):
        md = """
## 2026-01-10 10:00
- alpha work
"""
        profiles = [
            {"name": "Project Alpha", "match_terms": ["alpha"]},
            {"name": "Project Beta", "match_terms": ["beta"]},
        ]
        result = self._run(md, profiles)
        self.assertIn("Project Alpha", result)
        self.assertNotIn("Project Beta", result)

    def test_no_date_filter_includes_old_entries(self):
        md = """
## 2015-06-01 09:00
- alpha ancient work

## 2026-06-01 09:00
- alpha recent work
"""
        profiles = [{"name": "Project Alpha", "match_terms": ["alpha"]}]
        result = self._run(md, profiles)
        self.assertIn("Project Alpha", result)
        self.assertGreater(result["Project Alpha"], 0)


if __name__ == "__main__":
    unittest.main()
