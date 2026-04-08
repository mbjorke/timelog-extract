"""Runtime collector adapters with bound environment constants."""

from __future__ import annotations


class RuntimeCollectors:
    def __init__(
        self,
        *,
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
