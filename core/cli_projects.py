"""Typer commands: interactive projects management and projects lint."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import questionary
import typer

from core.cli_app import app
from core.cli_options import split_comma_separated_list
from core.projects_lint import lint_projects_config


def _match_terms_prompt_message(default_terms: list[str]) -> str:
    if default_terms:
        return "Match Terms (comma separated; press Enter to keep current/suggested terms):"
    return "Match Terms (comma separated):"


@app.command()
def projects(
    config: Annotated[str, typer.Option(help="Path to projects config file")] = "timelog_projects.json",
):
    """Manage project profiles interactively."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    config_path = Path(config)

    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                data = {"projects": data}
        except Exception as e:
            console.print(f"[red]Error reading config: {e}[/red]")
            raise typer.Exit(code=1) from e
    else:
        data = {"projects": [], "worklog": "TIMELOG.md"}

    def save():
        try:
            config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            console.print(f"[red]Error writing config:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        console.print(f"[green]Saved to {config_path}[/green]")

    while True:
        action = questionary.select(
            "Project Management",
            choices=[
                "List Projects",
                "Add New Project",
                "Edit Project",
                "Remove Project",
                "Set Worklog Path",
                "Save & Exit",
                "Cancel",
            ],
        ).ask()

        if action == "Cancel" or not action:
            break

        if action == "Save & Exit":
            save()
            break

        if action == "List Projects":
            table = Table(title="Project Profiles")
            table.add_column("Name (ID)", style="cyan")
            table.add_column("Customer", style="magenta")
            table.add_column("Match Terms", style="dim")

            for p in data.get("projects", []):
                table.add_row(
                    p.get("name", "N/A"),
                    p.get("customer", p.get("name", "N/A")),
                    ", ".join(p.get("match_terms", [])),
                )
            console.print(table)

        if action == "Set Worklog Path":
            current_wl = data.get("worklog", "TIMELOG.md")
            new_wl = questionary.text("Worklog path:", default=current_wl).ask()
            if new_wl:
                data["worklog"] = new_wl

        if action == "Add New Project" or action == "Edit Project":
            project = {}
            is_edit = action == "Edit Project"

            if is_edit:
                names = [p["name"] for p in data.get("projects", [])]
                if not names:
                    console.print("[yellow]No projects to edit.[/yellow]")
                    continue
                target_name = questionary.select("Select project to edit:", choices=names).ask()
                if not target_name:
                    continue
                project = next((p for p in data["projects"] if p["name"] == target_name), {})
                if not project:
                    console.print("[yellow]Selected project was not found.[/yellow]")
                    continue

            name = project.get("name", "")
            if not is_edit:
                name = questionary.text("Project Name (unique ID):").ask()
                if not name:
                    continue

            customer = questionary.text("Customer (display name):", default=project.get("customer", name)).ask()
            if customer is None:
                continue

            default_terms = project.get("match_terms", [])
            match_terms = questionary.text(
                _match_terms_prompt_message(default_terms),
                default=", ".join(default_terms),
            ).ask()
            if match_terms is None:
                continue

            tracked_urls = questionary.text(
                "Tracked AI URLs (comma separated):",
                default=", ".join(project.get("tracked_urls", [])),
            ).ask()
            if tracked_urls is None:
                continue

            email = questionary.text("Email filter (sender/receiver):", default=project.get("email", "")).ask()
            if email is None:
                continue

            title = questionary.text("Invoice Title:", default=project.get("invoice_title", "")).ask()
            if title is None:
                continue

            desc = questionary.text("Invoice Description:", default=project.get("invoice_description", "")).ask()
            if desc is None:
                continue

            new_project = {
                "name": name,
                "customer": customer,
                "match_terms": split_comma_separated_list(match_terms),
                "tracked_urls": split_comma_separated_list(tracked_urls),
                "email": email,
                "invoice_title": title,
                "invoice_description": desc,
                "enabled": True,
            }

            if is_edit:
                idx = next(i for i, p in enumerate(data["projects"]) if p["name"] == target_name)
                data["projects"][idx] = new_project
            else:
                if "projects" not in data:
                    data["projects"] = []
                data["projects"].append(new_project)

            console.print("[green]Project updated in memory. Remember to 'Save & Exit'.[/green]")

        if action == "Remove Project":
            names = [p["name"] for p in data.get("projects", [])]
            if not names:
                console.print("[yellow]No projects to remove.[/yellow]")
                continue
            target_name = questionary.select("Select project to remove:", choices=names).ask()
            if not target_name:
                continue
            should_remove = questionary.confirm(f"Are you sure you want to remove '{target_name}'?").ask()
            if should_remove is True:
                data["projects"] = [p for p in data["projects"] if p["name"] != target_name]
                console.print("[red]Project removed from memory.[/red]")


@app.command("projects-lint")
def projects_lint(
    config: Annotated[str, typer.Option(help="Path to projects config file")] = "timelog_projects.json",
    strict: Annotated[bool, typer.Option(help="Exit non-zero when warnings exist")] = False,
):
    """Lint project config for overlapping terms and high-risk generic terms."""
    from rich.console import Console

    console = Console()
    config_path = Path(config).expanduser()
    try:
        warnings = lint_projects_config(config_path)
    except Exception as exc:
        console.print(f"[red]Error reading config:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if not warnings:
        console.print("[green]projects-lint: PASS[/green] no overlap/high-risk warnings.")
        return

    console.print(f"[yellow]projects-lint: WARN[/yellow] {len(warnings)} warning(s)")
    for idx, warning in enumerate(warnings, start=1):
        console.print(f"{idx}. [{warning.code}] {warning.message}")

    if strict:
        raise typer.Exit(code=2)

