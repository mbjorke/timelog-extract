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

    def test_rejects_pathy_timelog_name(self):
        self.assertIn('case "$CANDIDATE"', HOOK_BODY)
        self.assertIn("*/", HOOK_BODY)
        self.assertIn("*..*", HOOK_BODY)


if __name__ == "__main__":
    unittest.main()
