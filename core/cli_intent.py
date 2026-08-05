"""Typer command: intent — answer which project a chat session belongs to."""

from __future__ import annotations

from typing import Annotated, List, Optional

import typer

from core.cli_app import app


class _ControlChoice:
    """Sentinel type for control choices in interactive questionary selection."""

    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return self.name


SKIP_SESSION = _ControlChoice("Skip this session")
CANCEL_MAPPING = _ControlChoice("Cancel")


@app.command("intent")
def intent(
    date_from: Annotated[Optional[str], typer.Option("--from", help="Start date (YYYY-MM-DD). Defaults to today.")] = None,
    date_to: Annotated[Optional[str], typer.Option("--to", help="End date (YYYY-MM-DD). Defaults to today.")] = None,
    set_binding: Annotated[Optional[List[str]], typer.Option("--set", help="Bind non-interactively: SESSION=PROJECT (repeatable).")] = None,
    note: Annotated[str, typer.Option("--note", help="Optional note stored with a --set binding.")] = "",
    list_only: Annotated[bool, typer.Option("--list", help="Show current bindings and exit.")] = False,
    projects_config: Annotated[Optional[str], typer.Option("--projects-config", help="Path to timelog_projects.json.")] = None,
) -> None:
    """Ask which project each unattributed chat session belongs to.

    A chat has no repo and no working directory, so nothing observable says whose
    work it was. Rather than adding a `match_term` — a rule that then matches
    every future event containing that text — this binds the answer to the
    session itself: one decision, one conversation, no spill.

    With no options this walks today's unattributed sessions and asks. The log is
    append-only, so re-answering a session is a new record, not an edit.
    """
    from datetime import datetime, timezone
    from pathlib import Path
    from types import SimpleNamespace

    from rich.console import Console
    from rich.markup import escape

    from core.analytics import get_date_range
    from core.config import load_profiles, resolve_projects_config_path
    from core.intent_store import intent_path, record_intent, resolve_intents, unbound_sessions
    from core.local_time import local_stamp
    from outputs.terminal_theme import (
        CLR_VALUE_ORANGE,
        FAIL_ICON,
        STYLE_LABEL,
        STYLE_MUTED,
    )

    console = Console()
    home = Path.home()
    local_tz = datetime.now().astimezone().tzinfo or timezone.utc

    if list_only:
        bindings = resolve_intents(home=home)
        if not bindings:
            console.print(f"[{CLR_VALUE_ORANGE}]No active session bindings found.[/{CLR_VALUE_ORANGE}]")
            console.print(
                f"[{STYLE_MUTED}]Next: Run `gittan intent` with no options to map "
                f"unattributed sessions interactively.[/{STYLE_MUTED}]"
            )
            return
        console.print(f"[bold {STYLE_LABEL}]Session bindings[/bold {STYLE_LABEL}] — {len(bindings)}")
        for (_kind, key), record in sorted(bindings.items(), key=lambda item: item[1]["captured_at"], reverse=True):
            console.print(
                f"  [{CLR_VALUE_ORANGE}]{escape(str(record['project']))}[/{CLR_VALUE_ORANGE}] ← {escape(str(key))} "
                f"[{STYLE_MUTED}]({escape(str(record['captured_at'][:10]))}, via {escape(str(record.get('via', 'cli')))})[/{STYLE_MUTED}]"
            )
        return

    config_path = str(projects_config) if projects_config else str(resolve_projects_config_path())
    try:
        profiles, _cfg, _workspace = load_profiles(
            config_path, SimpleNamespace(project="", keywords="", email="")
        )
    except ValueError:
        # Empty / broken config falls through to a nameless CLI fallback and
        # raises — treat that as "no projects", not as an open gate.
        profiles = []
    known = [str(profile.get("name") or "") for profile in profiles if profile.get("name")]

    if set_binding:
        # Validate the whole batch before appending anything. A binding is
        # authoritative (outranks a match_term), so a partial write on a later
        # typo would leave hours reassigned while the error still claims
        # "Nothing was recorded."
        pending: list[tuple[str, str]] = []
        for pair in set_binding:
            if "=" not in pair:
                console.print(f"{FAIL_ICON} [{CLR_VALUE_ORANGE}]Error: --set needs SESSION=PROJECT, got {pair!r}[/{CLR_VALUE_ORANGE}]")
                console.print(f"[{STYLE_MUTED}]Next: Run `gittan intent` with no options to pick from a list.[/{STYLE_MUTED}]")
                raise typer.Exit(code=1)
            session, project = pair.split("=", 1)
            project = project.strip()
            # `docs/specs/intent-capture.md`: invalid project name is rejected
            # and nothing is appended. An empty profile list must not open the
            # gate — that would make every name look valid and move hours into
            # a phantom bucket off Uncategorized.
            if not known:
                console.print(
                    f"{FAIL_ICON} [{CLR_VALUE_ORANGE}]Error: no configured projects to bind "
                    f"to.[/{CLR_VALUE_ORANGE}]"
                )
                console.print(
                    f"[{STYLE_MUTED}]Next: Add a named project to your config first. "
                    f"Nothing was recorded.[/{STYLE_MUTED}]"
                )
                raise typer.Exit(code=1)
            if project not in known:
                console.print(
                    f"{FAIL_ICON} [{CLR_VALUE_ORANGE}]Error: {escape(project)!r} is not a "
                    f"configured project.[/{CLR_VALUE_ORANGE}]"
                )
                console.print(f"[{STYLE_MUTED}]Known: {escape(', '.join(known))}[/{STYLE_MUTED}]")
                console.print(
                    f"[{STYLE_MUTED}]Next: Use one of those names, or add the project to "
                    f"your config first. Nothing was recorded.[/{STYLE_MUTED}]"
                )
                raise typer.Exit(code=1)
            pending.append((session, project))
        written = 0
        for session, project in pending:
            record = record_intent(session, project, via="cli", note=note, home=home)
            console.print(
                f"Bound {escape(str(record['key']))} → "
                f"[{CLR_VALUE_ORANGE}]{escape(str(record['project']))}[/{CLR_VALUE_ORANGE}]"
            )
            written += 1
        console.print(
            f"[{STYLE_MUTED}]{written} binding(s) appended to {escape(str(intent_path(home)))}[/{STYLE_MUTED}]"
        )
        return

    from core.anchor_nudge import should_prompt
    if not should_prompt():
        console.print(
            f"{FAIL_ICON} [{CLR_VALUE_ORANGE}]Interactive mapping requires an interactive terminal.[/{CLR_VALUE_ORANGE}]"
        )
        raise typer.Exit(code=1)

    # Interactive: collect the window's events, then ask about each unbound session.
    dt_from, dt_to = get_date_range(date_from, date_to, local_tz)
    from core.session_capture import collect_device_events, device_name

    events = collect_device_events(
        profiles, dt_from, dt_to, home=home, device=device_name(None)
    )
    rows = unbound_sessions(events, home=home)
    if not rows:
        console.print(
            f"[{CLR_VALUE_ORANGE}]No unattributed sessions in this window.[/{CLR_VALUE_ORANGE}]"
        )
        console.print(
            f"[{STYLE_MUTED}]Next: run `gittan report --today --source-summary` to inspect current work.[/{STYLE_MUTED}]"
        )
        return

    import questionary

    console.print(
        f"[bold {STYLE_LABEL}]Unattributed sessions[/bold {STYLE_LABEL}] — {len(rows)} to decide"
    )
    if known:
        console.print(f"[{STYLE_MUTED}]Projects: {', '.join(known)}[/{STYLE_MUTED}]")
    console.print(f"[{STYLE_MUTED}]Select a project for each session below.[/{STYLE_MUTED}]\n")

    bound = 0
    for row in rows:
        # Shown in the operator's own wall time: the whole point of the question
        # is recognising the session, and a UTC timestamp is the wrong clock to
        # recognise it by (10:10 UTC is 13:10 in EEST).
        when = row["first_seen"]
        if hasattr(when, "astimezone"):
            span = f"{when.astimezone(local_tz):%Y-%m-%d %H:%M %Z}".strip()
        else:
            span = local_stamp(when)
        label = row["label"] or "(no title)"
        console.print(
            f"[{CLR_VALUE_ORANGE}]{escape(str(label))}[/{CLR_VALUE_ORANGE}] "
            f"[{STYLE_MUTED}]{escape(str(row['source']))} · {escape(str(span))} · "
            f"{row['events']} event(s) · {escape(str(row['session']))}[/{STYLE_MUTED}]"
        )

        choices = []
        for name in known:
            choices.append(questionary.Choice(title=name, value=name))
        choices.append(questionary.Choice(title="Skip this session", value=SKIP_SESSION))
        choices.append(questionary.Choice(title="Cancel", value=CANCEL_MAPPING))

        answer = questionary.select(
            "  Which project?",
            choices=choices,
        ).ask()

        if answer is None or answer is CANCEL_MAPPING:
            console.print(f"[{CLR_VALUE_ORANGE}]Session mapping cancelled.[/{CLR_VALUE_ORANGE}]")
            raise typer.Exit(code=130)

        if answer is SKIP_SESSION:
            console.print(f"[{STYLE_MUTED}]  skipped[/{STYLE_MUTED}]\n")
            continue

        record_intent(row["session"], answer, via="intent-prompt", home=home)
        console.print(f"  bound → [{CLR_VALUE_ORANGE}]{escape(answer)}[/{CLR_VALUE_ORANGE}]\n")
        bound += 1

    console.print(
        f"{bound} session(s) bound. "
        f"[{STYLE_MUTED}]Re-run `gittan report` to see them attributed.[/{STYLE_MUTED}]"
    )
