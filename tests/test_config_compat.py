"""Tests for strict config normalization and project matching."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from timelog_extract import UNCATEGORIZED, classify_project, normalize_profile
from core.config import (
    ENV_GITTAN_HOME,
    ENV_PROJECTS_CONFIG,
    PROJECTS_CONFIG_FILENAME,
    SOURCE_GITTAN_HOME,
    SOURCE_PROFILE_HOME,
    apply_rule_to_project,
    remove_rule_from_project,
    canonical_projects_config_path,
    default_projects_config_option,
    find_ignored_projects_config_paths,
    load_projects_config_payload,
    projects_config_resolution_warnings,
    resolve_projects_config_path,
    resolve_projects_config_path_and_source,
)


class ConfigCompatibilityTests(unittest.TestCase):
    """Validates current config fields produce consistent behavior."""

    def test_normalize_profile_uses_match_terms(self):
        """Uses match_terms as canonical matching field."""
        profile = normalize_profile(
            {
                "name": "Demo",
                "match_terms": ["alpha"],
            }
        )
        self.assertIn("alpha", profile["match_terms"])
        self.assertIn("demo", profile["match_terms"])
        self.assertNotIn("beta", profile["match_terms"])

    def test_normalize_profile_keeps_explicit_empty_match_terms(self):
        profile = normalize_profile(
            {
                "name": "Demo",
                "match_terms": [],
            }
        )
        self.assertEqual(profile["match_terms"], [])

    def test_normalize_profile_uses_tracked_urls(self):
        """Uses tracked_urls as canonical URL field."""
        profile = normalize_profile(
            {
                "name": "Demo",
                "tracked_urls": ["https://example.com/a"],
            }
        )
        self.assertEqual(profile["tracked_urls"], ["https://example.com/a"])

    def test_normalize_profile_preserves_optional_project_worklog(self):
        profile = normalize_profile(
            {
                "name": "Demo",
                "worklog": "clients/demo/TIMELOG.md",
            }
        )
        self.assertEqual(profile.get("worklog"), "clients/demo/TIMELOG.md")

    def test_normalize_profile_preserves_toggl_project_id_as_int(self):
        profile = normalize_profile(
            {
                "name": "Demo",
                "toggl_project_id": "219507172",
            }
        )
        self.assertEqual(profile.get("toggl_project_id"), 219507172)
        self.assertIsInstance(profile["toggl_project_id"], int)

    def test_normalize_profile_rejects_non_integer_toggl_project_id(self):
        with self.assertRaises(ValueError):
            normalize_profile({"name": "Demo", "toggl_project_id": "not-a-number"})

    def test_normalize_profile_rejects_boolean_toggl_project_id(self):
        with self.assertRaises(ValueError):
            normalize_profile({"name": "Demo", "toggl_project_id": True})

    def test_normalize_profile_omits_toggl_project_id_when_absent(self):
        profile = normalize_profile({"name": "Demo"})
        self.assertNotIn("toggl_project_id", profile)

    def test_normalize_profile_supports_canonical_project_and_aliases(self):
        profile = normalize_profile(
            {
                "name": "project-core",
                "canonical_project": "ProductSuite",
                "aliases": ["project-ui", "project-cli"],
            }
        )
        self.assertEqual(profile["canonical_project"], "ProductSuite")
        self.assertIn("project-core", profile["aliases"])
        self.assertIn("ProductSuite", profile["aliases"])
        self.assertIn("project-ui", profile["aliases"])
        self.assertEqual(profile["ticket_mode"], "optional")
        self.assertEqual(profile["project_id"], "project-core")
        self.assertEqual(profile["default_client"], profile["customer"])

    def test_normalize_profile_accepts_ticket_policy_fields(self):
        profile = normalize_profile(
            {
                "name": "project-core",
                "project_id": "prod-core",
                "ticket_mode": "none",
                "default_client": "Internal Platform",
            }
        )
        self.assertEqual(profile["project_id"], "prod-core")
        self.assertEqual(profile["ticket_mode"], "none")
        self.assertEqual(profile["default_client"], "Internal Platform")

    def test_classify_project_works_with_match_terms(self):
        """Classifies text to the project whose match term appears in input."""
        profiles = [
            normalize_profile(
                {
                    "name": "ProjectA",
                    "match_terms": ["project-a", "alpha-feature"],
                }
            ),
            normalize_profile({"name": "ProjectB", "match_terms": ["project-b"]}),
        ]
        result = classify_project("Working on alpha-feature today", profiles)
        self.assertEqual(result, "ProjectA")

    def test_classify_project_returns_uncategorized_when_no_match(self):
        """Returns the UNCATEGORIZED fallback if no profile terms match."""
        profiles = [normalize_profile({"name": "ProjectA", "match_terms": ["foo"]})]
        result = classify_project("completely unrelated text", profiles)
        self.assertEqual(result, UNCATEGORIZED)

    def test_classify_project_matches_tracked_url_fragment(self):
        """URL fragments in tracked_urls participate in scoring (Chrome-style haystacks)."""
        profiles = [
            normalize_profile(
                {
                    "name": "ClientX",
                    "match_terms": ["clientx"],
                    "tracked_urls": ["app.clientx.io"],
                }
            ),
            normalize_profile({"name": "Other", "match_terms": ["other"]}),
        ]
        result = classify_project("https://app.clientx.io/checkout Other noise", profiles)
        self.assertEqual(result, "ClientX")

    def test_remove_rule_from_project_preserves_existing_shape_without_normalization(self):
        payload = {
            "projects": [
                {
                    "name": "Demo",
                    "match_terms": ["alpha", "demo"],
                    "tracked_urls": ["https://example.test"],
                    "aliases": ["Demo", "Demo Legacy"],
                    "enabled": True,
                }
            ]
        }
        ok = remove_rule_from_project(
            payload,
            project_name="Demo",
            rule_type="match_terms",
            rule_value="demo",
        )
        self.assertTrue(ok)
        project = payload["projects"][0]
        self.assertEqual(project["match_terms"], ["alpha"])
        self.assertEqual(project["aliases"], ["Demo", "Demo Legacy"])



class TagsFieldTests(unittest.TestCase):
    """Validates the optional 'tags' field on project profiles."""

    def test_normalize_profile_tags_optional(self):
        """Missing tags field normalizes to empty list."""
        profile = normalize_profile({"name": "Demo"})
        self.assertEqual(profile["tags"], [])

    def test_normalize_profile_tags_preserved(self):
        """Tags are sorted and lowercased."""
        profile = normalize_profile({"name": "Demo", "tags": ["OPS", "tech", "Tech"]})
        self.assertEqual(profile["tags"], ["ops", "tech"])

    def test_apply_rule_preserves_tags(self):
        """apply_rule_to_project does not drop existing tags."""
        payload = {
            "projects": [
                {
                    "name": "Demo",
                    "tags": ["tech"],
                    "match_terms": ["demo"],
                    "tracked_urls": [],
                    "enabled": True,
                }
            ]
        }
        apply_rule_to_project(payload, project_name="Demo", rule_type="match_terms", rule_value="newterm")
        project = payload["projects"][0]
        self.assertEqual(project.get("tags"), ["tech"])

    def test_normalize_profile_tags_deduplicated(self):
        """Duplicate tags after lowercasing are de-duplicated."""
        profile = normalize_profile({"name": "Demo", "tags": ["Tech", "tech", "TECH", "ops", "Ops"]})
        self.assertEqual(profile["tags"], ["ops", "tech"])

    def test_normalize_profile_tags_empty_strings_excluded(self):
        """Blank/empty strings in tags are stripped and excluded."""
        profile = normalize_profile({"name": "Demo", "tags": ["  ", "", "valid"]})
        self.assertEqual(profile["tags"], ["valid"])

    def test_normalize_profile_tags_single_value_as_string(self):
        """A comma-separated string for tags is treated via as_list."""
        profile = normalize_profile({"name": "Demo", "tags": "ops,tech"})
        self.assertIn("ops", profile["tags"])
        self.assertIn("tech", profile["tags"])

    def test_normalize_profile_tags_sorted_alphabetically(self):
        """Tags are sorted alphabetically after normalizing."""
        profile = normalize_profile({"name": "Demo", "tags": ["zebra", "alpha", "middle"]})
        self.assertEqual(profile["tags"], ["alpha", "middle", "zebra"])

    def test_apply_rule_creates_project_with_empty_tags(self):
        """New project created by apply_rule_to_project has an empty tags list (no KeyError)."""
        payload = {"projects": []}
        apply_rule_to_project(payload, project_name="BrandNew", rule_type="match_terms", rule_value="stuff")
        project = payload["projects"][0]
        self.assertIn("tags", project)
        self.assertEqual(project["tags"], [])

    def test_apply_rule_new_project_uses_customer_when_given(self):
        payload = {"projects": []}
        apply_rule_to_project(
            payload,
            project_name="landsbanken-faq-helper",
            rule_type="match_terms",
            rule_value="mbjorke/landsbanken-faq-helper",
            customer="Ålandsbanken",
        )
        project = payload["projects"][0]
        self.assertEqual(project["name"], "landsbanken-faq-helper")
        self.assertEqual(project["customer"], "Ålandsbanken")
        self.assertEqual(project["default_client"], "Ålandsbanken")
        self.assertEqual(project["project_id"], "landsbanken-faq-helper")

    def test_apply_rule_new_project_sets_invoice_title_and_alias(self):
        payload = {"projects": []}
        apply_rule_to_project(
            payload,
            project_name="landsbanken-faq-helper",
            rule_type="match_terms",
            rule_value="mbjorke/landsbanken-faq-helper",
            customer="Ålandsbanken Contact Center",
            invoice_title="Ålandsbanken Chatbot",
        )
        project = payload["projects"][0]
        self.assertEqual(project["invoice_title"], "Ålandsbanken Chatbot")
        self.assertIn("Ålandsbanken Chatbot", project["aliases"])
        self.assertNotIn("ålandsbanken chatbot", project["match_terms"])

    def test_apply_rule_preserves_multiple_tags(self):
        """Multiple existing tags are all preserved after applying a rule."""
        payload = {
            "projects": [
                {
                    "name": "Multi",
                    "tags": ["ops", "tech", "backend"],
                    "match_terms": ["multi"],
                    "tracked_urls": [],
                    "enabled": True,
                }
            ]
        }
        apply_rule_to_project(payload, project_name="Multi", rule_type="tracked_urls", rule_value="app.multi.io")
        project = payload["projects"][0]
        for tag in ["ops", "tech", "backend"]:
            self.assertIn(tag, project.get("tags", []))

    def test_load_projects_config_payload_projects_with_tags(self):
        """load_projects_config_payload preserves tags when loading from file."""
        import json
        import tempfile
        from pathlib import Path

        data = {
            "projects": [
                {"name": "Proj", "tags": ["alpha", "beta"], "match_terms": ["proj"], "tracked_urls": [], "enabled": True}
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = Path(f.name)
        try:
            payload = load_projects_config_payload(path)
            self.assertEqual(payload["projects"][0]["tags"], ["alpha", "beta"])
        finally:
            path.unlink(missing_ok=True)


class ProjectsConfigPathTests(unittest.TestCase):
    def test_prefers_explicit_projects_config_env(self):
        with mock.patch.dict(
            "os.environ",
            {ENV_PROJECTS_CONFIG: "~/secure/custom.json", ENV_GITTAN_HOME: "/tmp/ignored"},
            clear=False,
        ):
            path = resolve_projects_config_path()
            _path2, source = resolve_projects_config_path_and_source()
        self.assertEqual(path, Path("~/secure/custom.json").expanduser())
        self.assertEqual(source, ENV_PROJECTS_CONFIG)

    def test_uses_gittan_home_when_set(self):
        with mock.patch.dict("os.environ", {ENV_PROJECTS_CONFIG: "", ENV_GITTAN_HOME: "/tmp/gittan-home"}, clear=False):
            path = resolve_projects_config_path()
            _path2, source = resolve_projects_config_path_and_source()
        self.assertEqual(path, Path("/tmp/gittan-home") / PROJECTS_CONFIG_FILENAME)
        self.assertEqual(source, ENV_GITTAN_HOME)

    def test_defaults_to_canonical_gittan_home_when_missing(self):
        with mock.patch.dict(
            "os.environ",
            {ENV_PROJECTS_CONFIG: "", ENV_GITTAN_HOME: "", "USER": "", "LOGNAME": ""},
            clear=False,
        ):
            with mock.patch("core.config.Path.cwd", return_value=Path("/repo/no-config")):
                with mock.patch("core.config.Path.home", return_value=Path("/Users/demo")):
                    with mock.patch("core.config.getpass.getuser", return_value="sampleuser"):
                        with mock.patch("pathlib.Path.is_file", autospec=True) as is_file:
                            is_file.return_value = False
                            path = resolve_projects_config_path()
                            cli_default = default_projects_config_option()
                            _path2, source = resolve_projects_config_path_and_source()
        self.assertEqual(path, Path("/Users/demo/.gittan") / PROJECTS_CONFIG_FILENAME)
        self.assertEqual(cli_default, str(Path("/Users/demo/.gittan") / PROJECTS_CONFIG_FILENAME))
        self.assertEqual(source, SOURCE_GITTAN_HOME)

    def test_ignores_cwd_config_when_canonical_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd_config = Path(tmp) / PROJECTS_CONFIG_FILENAME
            cwd_config.write_text('{"projects": []}', encoding="utf-8")
            with mock.patch.dict("os.environ", {ENV_PROJECTS_CONFIG: "", ENV_GITTAN_HOME: ""}, clear=False):
                with mock.patch("core.config.Path.cwd", return_value=Path(tmp)):
                    with mock.patch("core.config.Path.home", return_value=Path("/Users/demo")):
                        with mock.patch("core.config.getpass.getuser", return_value="sampleuser"):
                            with mock.patch("pathlib.Path.is_file", autospec=True) as is_file:
                                def _is_file(path_obj):
                                    return Path(path_obj) == Path("/Users/demo/.gittan") / PROJECTS_CONFIG_FILENAME

                                is_file.side_effect = _is_file
                                path = resolve_projects_config_path()
                                _path2, source = resolve_projects_config_path_and_source()
        self.assertEqual(path, Path("/Users/demo/.gittan") / PROJECTS_CONFIG_FILENAME)
        self.assertEqual(source, SOURCE_GITTAN_HOME)

    def test_prefers_gittan_home_over_profile_home(self):
        with mock.patch.dict(
            "os.environ",
            {ENV_PROJECTS_CONFIG: "", ENV_GITTAN_HOME: "", "USER": "", "LOGNAME": ""},
            clear=False,
        ):
            with mock.patch("core.config.Path.cwd", return_value=Path("/repo/no-config")):
                with mock.patch("core.config.Path.home", return_value=Path("/Users/demo")):
                    with mock.patch("core.config.getpass.getuser", return_value="sampleuser"):
                        with mock.patch("pathlib.Path.is_file", autospec=True) as is_file:
                            def _is_file(path_obj):
                                p = Path(path_obj)
                                return p in {
                                    Path("/Users/demo/.gittan") / PROJECTS_CONFIG_FILENAME,
                                    Path("/Users/demo/.gittan-sampleuser") / PROJECTS_CONFIG_FILENAME,
                                }

                            is_file.side_effect = _is_file
                            path = resolve_projects_config_path()
                            _path2, source = resolve_projects_config_path_and_source()
        self.assertEqual(path, Path("/Users/demo/.gittan") / PROJECTS_CONFIG_FILENAME)
        self.assertEqual(source, SOURCE_GITTAN_HOME)

    def test_falls_back_to_profile_home_when_canonical_missing(self):
        with mock.patch.dict(
            "os.environ",
            {ENV_PROJECTS_CONFIG: "", ENV_GITTAN_HOME: "", "USER": "", "LOGNAME": ""},
            clear=False,
        ):
            with mock.patch("core.config.Path.cwd", return_value=Path("/repo/no-config")):
                with mock.patch("core.config.Path.home", return_value=Path("/Users/demo")):
                    with mock.patch("core.config.getpass.getuser", return_value="sampleuser"):
                        with mock.patch("pathlib.Path.is_file", autospec=True) as is_file:
                            def _is_file(path_obj):
                                return Path(path_obj) == Path("/Users/demo/.gittan-sampleuser") / PROJECTS_CONFIG_FILENAME

                            is_file.side_effect = _is_file
                            path = resolve_projects_config_path()
                            _path2, source = resolve_projects_config_path_and_source()
        self.assertEqual(path, Path("/Users/demo/.gittan-sampleuser") / PROJECTS_CONFIG_FILENAME)
        self.assertEqual(source, SOURCE_PROFILE_HOME)

    def test_shadow_config_detection_flags_home_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            canonical = home / ".gittan" / PROJECTS_CONFIG_FILENAME
            shadow = home / PROJECTS_CONFIG_FILENAME
            canonical.parent.mkdir(parents=True)
            canonical.write_text('{"projects": []}', encoding="utf-8")
            shadow.write_text('{"projects": []}', encoding="utf-8")
            with mock.patch("core.config.Path.home", return_value=home):
                ignored = find_ignored_projects_config_paths(canonical, cwd=home / "workspace")
            self.assertEqual(ignored, [(shadow.resolve(), "home directory")])

    def test_resolution_warnings_mention_legacy_worklog_dir(self):
        cfg = canonical_projects_config_path()
        profiles = [
            {
                "name": "demo",
                "worklog": str(Path.home() / "worklogs" / "demo.md"),
            }
        ]
        warnings = projects_config_resolution_warnings(cfg, profiles=profiles)
        self.assertTrue(any("~/worklogs/" in line for line in warnings))

    def test_resolve_profile_worklog_paths_resolves_relative_deduped_and_absolute(self):
        from core.config import resolve_profile_worklog_paths

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cfg = base / "timelog_projects.json"
            cfg.write_text('{"projects": []}', encoding="utf-8")
            profiles = [
                {"name": "A", "worklog": "worklogs/a.md"},
                {"name": "B", "worklog": "worklogs/a.md"},
                {"name": "C", "worklog": str((base / "abs" / "c.md").resolve())},
            ]
            paths = resolve_profile_worklog_paths(profiles, config_path=cfg, script_dir=base)
            self.assertEqual(len(paths), 2)
            self.assertEqual(paths[0], (base / "worklogs" / "a.md").resolve())
            self.assertEqual(paths[1], (base / "abs" / "c.md").resolve())



if __name__ == "__main__":
    unittest.main()
