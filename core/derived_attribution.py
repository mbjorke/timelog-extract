"""Identity for repositories no profile claims, derived and never persisted.

Classification answers one question — which declared profile does this text
match — and returns ``Uncategorized`` when none does. That answer throws away
something the event was already carrying: collectors resolve the git remote to
``owner/repo`` and store it as a ``repo`` anchor, worktree-invariant, before
classification ever runs. So the identity was known and the report said it was
not.

The cost is a first run in which most of the day is grey. That is the setup
gate this exists to remove: a report should be useful before any configuration,
and configuration should be what you do when you want to **bill**.

Two rules keep this from becoming a second, sloppier config:

**Declared always wins.** Only events that classification left at
``Uncategorized`` are touched. A profile that matches keeps its answer, so
existing mappings behave exactly as they did.

**Git remotes only.** A directory leaf, a branch name and a session title are
not durable identities — the leaf collides across machines, and #529 showed how
easily a junk path reaches the user. Only ``owner/repo`` from a remote is
accepted here.

Nothing is written. Attribution is derived per run and lives in memory;
``timelog_projects.json`` gains no new writer, per #406.

Spec: ``docs/task-prompts/zero-config-project-attribution-task.md`` (GH-527).
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from core.events import event_anchors

#: Marks an event whose project came from a remote rather than a profile.
DERIVED_KEY = "project_derived"


def derived_slug(event: Dict[str, Any] | None) -> str:
    """The ``owner/repo`` this event anchors to, or ``""``.

    Shape is the check: exactly one slash, with both halves present. A bare
    leaf reaching this function is a signal that is not allowed to create
    identity, so it is rejected rather than repaired.
    """
    anchors = event_anchors(event)
    slug = str(anchors.get("repo") or "").strip().lower()
    if slug.count("/") != 1:
        return ""
    owner, _, repo = slug.partition("/")
    if not owner.strip() or not repo.strip():
        return ""
    return slug


def apply_derived_attribution(
    events: Sequence[Dict[str, Any]],
    *,
    uncategorized: str,
) -> List[Dict[str, Any]]:
    """Attribute unclaimed events to their remote slug, marking each as derived.

    Returns new event dicts, leaving the input untouched, so a caller that also
    keeps the raw events can still see what classification alone produced.
    """
    fallback = str(uncategorized or "").strip()
    out: List[Dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            out.append(event)
            continue
        if str(event.get("project") or "").strip() != fallback:
            out.append(event)
            continue
        slug = derived_slug(event)
        if not slug:
            out.append(event)
            continue
        attributed = dict(event)
        attributed["project"] = slug
        attributed[DERIVED_KEY] = True
        out.append(attributed)
    return out


def derived_projects(events: Sequence[Dict[str, Any]]) -> set[str]:
    """Project names in ``events`` that were derived rather than declared.

    Read by the output layer, which must never present a derived row as a
    declared one, and by the payload, where ``billable_hours`` is null for these
    rows because nobody has declared what they are worth.
    """
    return {
        str(event.get("project") or "")
        for event in events
        if isinstance(event, dict) and event.get(DERIVED_KEY) is True
    }
