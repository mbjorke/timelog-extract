"""Regression: collector/config diagnostics must not corrupt --json stdout (#298).

Warnings printed to stdout land *before* the JSON on every machine-readable
path (`report --format json`, `review --json`, `review --gaps --json`), so a
consumer doing `json.load` / `| jq` fails. The maintainer's #234 manual test
surfaced this (Apple Mail's "No versioned Mail directory" warning on stdout).
These tests pin the diagnostics to stderr so stdout stays pure JSON.
"""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


class DiagnosticsGoToStderrTests(unittest.TestCase):
    def _capture(self, fn):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            fn()
        return out.getvalue(), err.getvalue()

    def test_mail_missing_dir_warning_on_stderr_not_stdout(self):
        from collectors.mail import collect_apple_mail

        def run():
            # A HOME with no ~/Library/Mail → detect_mail_root returns None →
            # the "No versioned Mail directory" warning path.
            collect_apple_mail(
                profiles=[],
                dt_from=None,
                dt_to=None,
                home=Path("/nonexistent-home-for-test"),
                default_email=None,
                classify_project=lambda *a, **k: "x",
                make_event=lambda *a, **k: {},
                uncategorized="Uncategorized",
            )

        out, err = self._capture(run)
        self.assertEqual(out, "", "collector must not print diagnostics to stdout")
        self.assertIn("Mail", err, "warning should still be visible on stderr")

    def test_diagnostic_prints_route_to_stderr(self):
        # Every `[Warning]` print in the warning-emitting collectors/runtime must
        # carry file=sys.stderr, so no diagnostic can leak onto JSON stdout.
        import inspect
        import re as _re

        import collectors.chrome as chrome
        import collectors.mail as mail
        import core.report_runtime as report_runtime

        for mod in (chrome, mail, report_runtime):
            for line in inspect.getsource(mod).splitlines():
                if _re.search(r"print\(.*\[Warning\]", line):
                    self.assertIn(
                        "file=sys.stderr",
                        line,
                        f"{mod.__name__}: warning print must go to stderr: {line.strip()}",
                    )


if __name__ == "__main__":
    unittest.main()
