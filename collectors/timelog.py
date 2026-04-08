from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def collect_timelog(worklog_path, dt_from, dt_to, profiles, local_tz, classify_project, make_event, source_name):
    results = []
    wl = Path(worklog_path)
    if not wl.exists():
        return results

    ts_pattern = re.compile(r"(?m)^\s*(?:##\s*)?(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?\s*$")
    try:
        text = wl.read_text(encoding="utf-8")
        slot_by_date = defaultdict(int)
        for match in ts_pattern.finditer(text):
            date_s = match.group(1)
            time_s = match.group(2)
            try:
                if time_s:
                    ts = datetime.strptime(
                        f"{date_s} {time_s}", "%Y-%m-%d %H:%M"
                    ).replace(tzinfo=local_tz)
                else:
                    n = slot_by_date[date_s]
                    slot_by_date[date_s] += 1
                    minute_of_day = 12 * 60 + n
                    if minute_of_day >= 24 * 60:
                        minute_of_day = 24 * 60 - 1
                    hh, mm = divmod(minute_of_day, 60)
                    ts = datetime.strptime(
                        f"{date_s} {hh:02d}:{mm:02d}", "%Y-%m-%d %H:%M"
                    ).replace(tzinfo=local_tz)
            except ValueError:
                continue

            if not (dt_from <= ts <= dt_to):
                continue

            start = match.end()
            snippet = text[start:start + 220].strip().split("\n")[0][:120]
            project = classify_project(snippet, profiles)
            results.append(make_event(source_name, ts, snippet or "worklog", project))
    except OSError:
        pass
    return results
