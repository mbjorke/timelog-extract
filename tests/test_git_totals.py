"""Tests for core.git_totals: compute_git_project_totals."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

LOCAL_TZ = timezone.utc


def _make_event(source, ts, detail, project):
    return {"source": source, "timestamp": ts, "local_ts": ts, "detail": detail, "project": project}


class TestComputeGitProjectTotals(unittest.TestCase):

    def test_no_profiles_with_git_repo_returns_empty(self):
        from core.git_totals import compute_git_project_totals

        profiles = [{"name": "MyProject", "match_terms": ["myproject"]}]  # no git_repo
        result = compute_git_project_totals(
            profiles=profiles,
            local_tz=LOCAL_TZ,
            make_event_fn=_make_event,
            ai_sources=set(),
        )
        self.assertEqual(result, {})

    def test_nonexistent_repo_returns_empty(self):
        from core.git_totals import compute_git_project_totals

        profiles = [{"name": "MyProject", "git_repo": "/nonexistent/path/repo"}]
        result = compute_git_project_totals(
            profiles=profiles,
            local_tz=LOCAL_TZ,
            make_event_fn=_make_event,
            ai_sources=set(),
        )
        self.assertEqual(result, {})

    def test_git_repo_as_list_is_supported(self):
        """Multiple repos in git_repo list should each be iterated."""
        from core.git_totals import compute_git_project_totals

        profiles = [
            {"name": "MyProject", "git_repo": ["/nope/a", "/nope/b"]}
        ]
        # Both paths nonexistent → empty result, but no crash
        result = compute_git_project_totals(
            profiles=profiles,
            local_tz=LOCAL_TZ,
            make_event_fn=_make_event,
            ai_sources=set(),
        )
        self.assertEqual(result, {})

    def test_commit_events_produce_hours(self):
        """When collect_git_commit_timestamps returns events, hours are computed."""
        from core.git_totals import compute_git_project_totals

        # Two commits 5 minutes apart → one session → passive floor (15 min = 0.25h)
        ts1 = datetime(2024, 3, 1, 10, 0, tzinfo=LOCAL_TZ)
        ts2 = datetime(2024, 3, 1, 10, 5, tzinfo=LOCAL_TZ)

        fake_events = [
            _make_event("Git commits", ts1, "git commit (myrepo)", "MyProject"),
            _make_event("Git commits", ts2, "git commit (myrepo)", "MyProject"),
        ]

        profiles = [{"name": "MyProject", "git_repo": "/some/repo"}]

        with patch("core.git_totals.collect_git_commit_timestamps", return_value=fake_events):
            result = compute_git_project_totals(
                profiles=profiles,
                local_tz=LOCAL_TZ,
                make_event_fn=_make_event,
                ai_sources=set(),
                min_session_minutes=5,
                min_session_passive_minutes=15,
            )

        self.assertIn("MyProject", result)
        # Passive floor: at least 0.25h (15 min)
        self.assertGreaterEqual(result["MyProject"], 0.25)


if __name__ == "__main__":
    unittest.main()
