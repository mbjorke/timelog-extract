"""Runtime collector adapters with bound environment constants."""

from __future__ import annotations

from typing import Any, Optional

from collectors import calendar as calendar_collector, lovable_desktop as lovable_desktop_collector
from core.noise_profiles import DEFAULT_LOVABLE_NOISE_PROFILE, DEFAULT_NOISE_PROFILE


class RuntimeCollectors:
    def __init__(
        self,
        *,
        cli_args=None,
        home,
        local_tz,
        chrome_epoch_delta_us,
        uncategorized,
        cursor_checkpoints_dir,
        codex_ide_session_index,
        worklog_source,
        cursor_checkpoints_source,
        classify_project_fn,
        make_event_fn,
        ai_logs_collector,
        chrome_collector,
        cursor_collector,
        antigravity_collector,
        windsurf_collector,
        mail_collector,
        timelog_collector,
        github_collector,
        toggl_collector,
        zed_collector,
        conductor_collector,
        github_token: Optional[str] = None,
    ):
        self.home = home
        self.local_tz = local_tz
        self.chrome_epoch_delta_us = chrome_epoch_delta_us
        self.uncategorized = uncategorized
        self.cursor_checkpoints_dir = cursor_checkpoints_dir
        self.codex_ide_session_index = codex_ide_session_index
        self.worklog_source = worklog_source
        self.cursor_checkpoints_source = cursor_checkpoints_source
        self.classify_project = classify_project_fn
        self.make_event = make_event_fn
        self.ai_logs = ai_logs_collector
        self.chrome = chrome_collector
        self.cursor = cursor_collector
        self.antigravity = antigravity_collector
        self.windsurf = windsurf_collector
        self.mail = mail_collector
        self.timelog = timelog_collector
        self.github = github_collector
        self.toggl = toggl_collector
        self.zed = zed_collector
        self.conductor = conductor_collector
        self.cli_args = cli_args
        self.github_token = github_token

    def collect_claude_code(self, profiles, dt_from, dt_to):
        return self.ai_logs.collect_claude_code(
            profiles, dt_from, dt_to, self.home, self.classify_project, self.make_event
        )

    def collect_claude_desktop(self, profiles, dt_from, dt_to):
        return self.ai_logs.collect_claude_desktop(
            profiles, dt_from, dt_to, self.home, self.classify_project, self.make_event
        )

    def collect_claude_desktop_code(self, profiles, dt_from, dt_to):
        from collectors.claude_desktop_events import collect_claude_desktop_code

        return collect_claude_desktop_code(
            profiles, dt_from, dt_to, self.home, self.classify_project, self.make_event
        )

    def _web_visit_collapse_minutes(self) -> int:
        collapse = 12
        if self.cli_args is not None:
            value = getattr(self.cli_args, "chrome_collapse_minutes", None)
            if value is not None:
                collapse = int(value)
        return self.chrome.web_visit_collapse_minutes(collapse)

    def collect_claude_ai_urls(self, profiles, dt_from, dt_to):
        return self.chrome.collect_claude_ai_urls(
            profiles,
            dt_from,
            dt_to,
            self.home,
            self.chrome_epoch_delta_us,
            self.uncategorized,
            self.make_event,
            collapse_minutes=self._web_visit_collapse_minutes(),
        )

    def collect_gemini_web_urls(self, profiles, dt_from, dt_to):
        return self.chrome.collect_gemini_web_urls(
            profiles,
            dt_from,
            dt_to,
            self.home,
            self.chrome_epoch_delta_us,
            self.uncategorized,
            self.make_event,
            collapse_minutes=self._web_visit_collapse_minutes(),
        )

    def collect_chrome(self, profiles, dt_from, dt_to, collapse_minutes=0):
        include_all = (
            bool(getattr(self.cli_args, "chrome_raw", False))
            if self.cli_args is not None
            else False
        )
        contains_url = (
            str(getattr(self.cli_args, "chrome_contains_url", "") or "").strip()
            if self.cli_args is not None
            else ""
        )
        return self.chrome.collect_chrome(
            profiles,
            dt_from,
            dt_to,
            collapse_minutes,
            self.home,
            self.chrome_epoch_delta_us,
            self.classify_project,
            self.make_event,
            include_all=include_all,
            contains_url=contains_url or None,
        )

    def collect_lovable_desktop(self, profiles, dt_from, dt_to):
        collapse = 12
        lovable_noise_profile = DEFAULT_LOVABLE_NOISE_PROFILE
        if self.cli_args is not None:
            value = getattr(self.cli_args, "chrome_collapse_minutes", None)
            if value is not None:
                collapse = int(value)
            lovable_noise_profile = str(
                getattr(
                    self.cli_args,
                    "lovable_noise_profile",
                    DEFAULT_LOVABLE_NOISE_PROFILE,
                )
                or DEFAULT_LOVABLE_NOISE_PROFILE
            ).lower()
        return lovable_desktop_collector.collect_lovable_desktop(
            profiles,
            dt_from,
            dt_to,
            collapse,
            self.home,
            self.chrome_epoch_delta_us,
            self.classify_project,
            self.make_event,
            lovable_noise_profile=lovable_noise_profile,
        )

    def collect_apple_mail(self, profiles, dt_from, dt_to, default_email=None):
        return self.mail.collect_apple_mail(
            profiles,
            dt_from,
            dt_to,
            self.home,
            default_email,
            self.classify_project,
            self.make_event,
            self.uncategorized,
        )

    def collect_gemini_cli(self, profiles, dt_from, dt_to):
        return self.ai_logs.collect_gemini_cli(
            profiles, dt_from, dt_to, self.home, self.classify_project, self.make_event
        )

    def collect_copilot_cli(self, profiles, dt_from, dt_to):
        from collectors.copilot_cli import collect_copilot_cli

        return collect_copilot_cli(
            profiles, dt_from, dt_to, self.home, self.classify_project, self.make_event
        )

    def collect_zed(self, profiles, dt_from, dt_to):
        from collectors.zed import collect_zed

        return collect_zed(
            profiles, dt_from, dt_to, self.home, self.classify_project, self.make_event
        )

    def collect_conductor(self, profiles, dt_from, dt_to):
        from collectors.conductor import collect_conductor

        return collect_conductor(
            profiles, dt_from, dt_to, self.home, self.classify_project, self.make_event
        )

    def _noise_profile(self) -> str:
        """Resolve the configured noise profile, defaulting when unset."""
        if self.cli_args is None:
            return DEFAULT_NOISE_PROFILE
        return str(
            getattr(self.cli_args, "noise_profile", DEFAULT_NOISE_PROFILE) or DEFAULT_NOISE_PROFILE
        ).lower()

    def collect_cursor(self, profiles, dt_from, dt_to):
        return self.cursor.collect_cursor(
            profiles,
            dt_from,
            dt_to,
            self.home,
            self.local_tz,
            self.classify_project,
            self.make_event,
            noise_profile=self._noise_profile(),
        )

    def collect_antigravity(self, profiles, dt_from, dt_to):
        return self.antigravity.collect_antigravity(
            profiles,
            dt_from,
            dt_to,
            self.home,
            self.local_tz,
            self.classify_project,
            self.make_event,
            noise_profile=self._noise_profile(),
        )

    def collect_windsurf(self, profiles, dt_from, dt_to):
        return self.windsurf.collect_windsurf(
            profiles,
            dt_from,
            dt_to,
            self.home,
            self.local_tz,
            self.classify_project,
            self.make_event,
            noise_profile=self._noise_profile(),
        )

    def collect_cursor_checkpoints(self, profiles, dt_from, dt_to):
        return self.cursor.collect_cursor_checkpoints(
            profiles,
            dt_from,
            dt_to,
            self.cursor_checkpoints_dir,
            self.home,
            self.classify_project,
            self.make_event,
            self.cursor_checkpoints_source,
        )

    def collect_codex_ide(self, profiles, dt_from, dt_to):
        return self.ai_logs.collect_codex_ide(
            profiles,
            dt_from,
            dt_to,
            self.codex_ide_session_index,
            self.classify_project,
            self.make_event,
        )

    def collect_worklog(self, worklog_path, dt_from, dt_to, profiles):
        worklog_format = (
            getattr(self.cli_args, "worklog_format", "auto")
            if self.cli_args is not None
            else "auto"
        )
        paths: list[str]
        if worklog_path is None:
            paths = []
        elif isinstance(worklog_path, (list, tuple, set)):
            paths = [str(p).strip() for p in worklog_path if p is not None and str(p).strip()]
        else:
            one = str(worklog_path).strip()
            paths = [one] if one else []

        merged: list[dict[str, Any]] = []
        seen: set[tuple[Any, ...]] = set()
        for one_path in paths:
            if not one_path:
                continue
            if hasattr(self.timelog, "collect_worklog"):
                rows = self.timelog.collect_worklog(
                    one_path,
                    dt_from,
                    dt_to,
                    profiles,
                    self.local_tz,
                    self.classify_project,
                    self.make_event,
                    self.worklog_source,
                    worklog_format=worklog_format,
                )
            else:
                rows = self.timelog.collect_timelog(
                    one_path,
                    dt_from,
                    dt_to,
                    profiles,
                    self.local_tz,
                    self.classify_project,
                    self.make_event,
                    self.worklog_source,
                )
            for event in rows:
                key = (
                    str(event.get("source", "")),
                    event.get("timestamp"),
                    str(event.get("detail", "")),
                    str(event.get("project", "")),
                )
                if key in seen:
                    continue
                seen.add(key)
                merged.append(event)
        return merged

    def collect_github(self, profiles, dt_from, dt_to):
        """Collect public GitHub activity for configured usernames."""
        from collectors.github import (
            merge_github_public_events,
            resolve_github_api_base,
            resolve_github_usernames,
        )

        users = resolve_github_usernames(self.cli_args) if self.cli_args is not None else []
        if not users:
            return []
        api_base = resolve_github_api_base()
        batches = [
            self.github.collect_public_events(
                profiles,
                dt_from,
                dt_to,
                username=u,
                token=self.github_token,
                classify_project=self.classify_project,
                make_event=self.make_event,
                api_base=api_base,
            )
            for u in users
        ]
        return merge_github_public_events(batches)

    def collect_toggl(self, profiles, dt_from, dt_to):
        return self.toggl.collect_workspace_events(
            profiles,
            dt_from,
            dt_to,
            classify_project=self.classify_project,
            make_event=self.make_event,
        )

    def calendar_roles(self) -> dict:
        raw = getattr(self.cli_args, "calendar_names", None) if self.cli_args is not None else None
        return calendar_collector.parse_calendar_roles(raw)

    def collect_calendar(self, profiles, dt_from, dt_to):
        return calendar_collector.collect_calendar(
            profiles,
            dt_from,
            dt_to,
            self.home,
            self.classify_project,
            self.make_event,
            calendar_roles=self.calendar_roles(),
        )
