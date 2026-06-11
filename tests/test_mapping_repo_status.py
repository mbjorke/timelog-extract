"""Tests for mapping repo status helpers."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from core.mapping_repo_status import SlugGitBinding, enrich_bindings_with_remote_activity


class MappingRepoStatusTests(unittest.TestCase):
    def test_enrich_uses_remote_event_epoch_when_no_local_clone(self):
        ts = datetime(2026, 6, 10, tzinfo=timezone.utc)
        events = [
            {
                "source": "GitHub",
                "timestamp": ts,
                "detail": "push to ax-finans/financing-portal-dev-31e799cf (2 commits, ref main)",
                "project": "Uncategorized",
            },
        ]
        enriched = enrich_bindings_with_remote_activity(
            {},
            events,
            activity={"ax-finans/financing-portal-dev-31e799cf": 4},
            dt_from=datetime(2026, 6, 1, tzinfo=timezone.utc),
            dt_to=datetime(2026, 6, 30, tzinfo=timezone.utc),
        )
        binding = enriched["ax-finans/financing-portal-dev-31e799cf"]
        self.assertEqual(binding.local_path, "(not found on disk)")
        self.assertEqual(binding.in_window_epoch, int(ts.timestamp()))
        self.assertEqual(binding.remote_hits, 4)
        self.assertEqual(binding.git_cmd_hits, 0)

    def test_enrich_merges_remote_epoch_with_local_binding(self):
        local_epoch = 1_700_000_000
        remote_epoch = 1_800_000_000
        bindings = {
            "mbjorke/demo": SlugGitBinding(
                slug="mbjorke/demo",
                remote_url="https://github.com/mbjorke/demo",
                local_path="~/demo",
                last_commit_epoch=local_epoch,
                git_cmd_hits=1,
            ),
        }
        enriched = enrich_bindings_with_remote_activity(
            bindings,
            [],
            gh_pushed_epochs={"mbjorke/demo": remote_epoch},
            dt_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
            dt_to=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(enriched["mbjorke/demo"].in_window_epoch, remote_epoch)


if __name__ == "__main__":
    unittest.main()
