"""Runtime collector adapters with bound environment constants."""

from __future__ import annotations

from typing import Any, Optional


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
        mail_collector,
        timelog_collector,
        github_collector,
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
        self.mail = mail_collector
        self.timelog = timelog_collector
        self.github = github_collector
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

    def collect_claude_ai_urls(self, profiles, dt_from, dt_to):
        return self.chrome.collect_claude_ai_urls(
            profiles,
            dt_from,
            dt_to,
            self.home,
            self.chrome_epoch_delta_us,
            self.uncategorized,
            self.make_event,
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
        )

    def collect_chrome(self, profiles, dt_from, dt_to, collapse_minutes=0):
        return self.chrome.collect_chrome(
            profiles,
            dt_from,
            dt_to,
            collapse_minutes,
            self.home,
            self.chrome_epoch_delta_us,
            self.classify_project,
            self.make_event,
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

    def collect_cursor(self, profiles, dt_from, dt_to):
        return self.cursor.collect_cursor(
            profiles, dt_from, dt_to, self.home, self.local_tz, self.classify_project, self.make_event
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
        worklog_format = getattr(self.cli_args, "worklog_format", "auto") if self.cli_args is not None else "auto"
        if hasattr(self.timelog, "collect_worklog"):
            return self.timelog.collect_worklog(
                worklog_path,
                dt_from,
                dt_to,
                profiles,
                self.local_tz,
                self.classify_project,
                self.make_event,
                self.worklog_source,
                worklog_format=worklog_format,
            )
        return self.timelog.collect_timelog(
            worklog_path,
            dt_from,
            dt_to,
            profiles,
            self.local_tz,
            self.classify_project,
            self.make_event,
            self.worklog_source,
        )

    def collect_github(self, profiles, dt_from, dt_to):
        from collectors.github import resolve_github_username

        user = resolve_github_username(self.cli_args) if self.cli_args is not None else ""
        if not user:
            return []
        return self.github.collect_public_events(
            profiles,
            dt_from,
            dt_to,
            username=user,
            token=self.github_token,
            classify_project=self.classify_project,
            make_event=self.make_event,
        )
