"""The lazy-opener contract shared by the GitHub, Jira and Toggl collectors.

The optimisation moves opener construction out of import time, where it was
running ssl.create_default_context() and set_default_verify_paths() on every
CLI invocation. That is only a win if importing really builds nothing, and only
safe if first use still produces the same hardened opener and reuses it.

Fixture-only: no network, no credentials. Every case either inspects module
state or drives urlopen() with the opener patched out.
"""

from __future__ import annotations

import importlib
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request

# (module, cache attribute, builder attribute, expected service arg).
# Jira builds its opener with build_opener() directly rather than through the
# shared helper, so the builder it patches — and the call signature — differ.
_COLLECTORS = (
    ("collectors.github", "_github_opener", "build_https_opener", "GitHub"),
    ("collectors.jira", "_jira_opener", "build_opener", None),
    ("collectors.toggl", "_toggl_opener", "build_https_opener", "Toggl"),
)


class LazyOpenerContractTests(unittest.TestCase):
    """Import builds nothing; first use builds once and keeps it."""

    def _fresh(self, module_name: str):
        module = importlib.import_module(module_name)
        return importlib.reload(module)

    def test_import_does_not_construct_an_opener(self):
        for module_name, attr, builder, _service in _COLLECTORS:
            with self.subTest(module=module_name):
                module = self._fresh(module_name)
                self.assertIsNone(
                    getattr(module, attr),
                    "importing must not build an opener — that is the whole optimisation",
                )

    def test_first_use_constructs_once_and_reuses(self):
        for module_name, attr, builder, service in _COLLECTORS:
            with self.subTest(module=module_name):
                module = self._fresh(module_name)
                self.assertIsNone(getattr(module, attr))

                opener = MagicMock()
                with patch.object(module, builder, return_value=opener) as build_mock:
                    module.urlopen(Request("https://api.example.test/one"))
                    self.assertEqual(build_mock.call_count, 1)
                    if service is not None:
                        self.assertEqual(build_mock.call_args.args, (service,))

                    module.urlopen(Request("https://api.example.test/two"))
                    self.assertEqual(
                        build_mock.call_count, 1, "the opener must be cached, not rebuilt per call"
                    )
                self.assertIs(getattr(module, attr), opener)
                self.assertEqual(opener.open.call_count, 2)

    def test_request_and_timeout_are_forwarded_unchanged(self):
        for module_name, _attr, builder, _service in _COLLECTORS:
            with self.subTest(module=module_name):
                module = self._fresh(module_name)
                opener = MagicMock()
                req = Request("https://api.example.test/v2", headers={"Authorization": "Bearer x"})
                with patch.object(module, builder, return_value=opener):
                    module.urlopen(req, timeout=7)
                self.assertIs(opener.open.call_args.args[0], req)
                self.assertEqual(opener.open.call_args.kwargs.get("timeout"), 7)

    def test_lazily_built_opener_is_still_the_hardened_one(self):
        """Deferring construction must not quietly drop the redirect guard."""
        for module_name, _attr, builder, _service in _COLLECTORS:
            with self.subTest(module=module_name):
                module = self._fresh(module_name)
                try:
                    module.urlopen(Request("https://127.0.0.1:1/never"), timeout=0.01)
                except Exception:
                    pass  # the connection is expected to fail; the opener is the subject

                opener = getattr(module, _attr)
                self.assertIsNotNone(opener, "first use must have built the opener")
                handlers = [type(h).__name__ for h in opener.handlers]
                self.assertIn("HTTPSHandler", handlers)
                self.assertTrue(
                    any("RejectHttpRedirectHandler" in name for name in handlers),
                    f"redirect guard missing from {module_name}: {handlers}",
                )


class JiraOpenerHandlerTests(unittest.TestCase):
    """Jira builds its opener directly rather than via build_https_opener."""

    def test_opener_carries_both_required_handlers(self):
        import collectors.jira as jira

        jira = importlib.reload(jira)
        try:
            jira.urlopen(Request("https://127.0.0.1:1/never"), timeout=0.01)
        except Exception:
            pass
        handlers = jira._jira_opener.handlers
        self.assertTrue(any(isinstance(h, HTTPSHandler) for h in handlers))
        self.assertTrue(any(isinstance(h, HTTPRedirectHandler) for h in handlers))

    def test_redirect_handler_blocks_plain_http(self):
        from collectors.jira import _RejectHttpRedirectHandler

        with self.assertRaises(URLError) as ctx:
            _RejectHttpRedirectHandler().redirect_request(
                Request("https://jira.example.test/rest/api/3/myself"),
                None, 301, "Moved Permanently", {},
                "http://jira.example.test/rest/api/3/myself",
            )
        self.assertIn("insecure http://", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
