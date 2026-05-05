"""Sanity checks for embedded global post-commit hook script."""

from __future__ import annotations

import unittest

from core.global_timelog_hook_script import HOOK_BODY


class GlobalTimelogHookScriptTests(unittest.TestCase):
    def test_uses_portable_shebang_and_grep(self):
        self.assertIn("#!/usr/bin/env zsh", HOOK_BODY)
        self.assertNotIn("#!/bin/zsh", HOOK_BODY)
        self.assertIn("grep -Fxq", HOOK_BODY)
        self.assertNotIn(" rg ", HOOK_BODY)
        self.assertNotIn("rg -Fx", HOOK_BODY)

    def test_supports_absolute_and_tilde_paths(self):
        self.assertIn('if [[ "$TIMELOG_NAME" == /* ]]; then', HOOK_BODY)
        self.assertIn('elif [[ "$TIMELOG_NAME" == ~/* ]]; then', HOOK_BODY)

    def test_prefers_project_scoped_worklog_when_present(self):
        self.assertIn('PROJECT_WORKLOG="$HOME/.gittan/worklogs/${REPO_ID}.md"', HOOK_BODY)
        self.assertIn('"$CONFIGURED_CANDIDATE" == "TIMELOG.md"', HOOK_BODY)


if __name__ == "__main__":
    unittest.main()
