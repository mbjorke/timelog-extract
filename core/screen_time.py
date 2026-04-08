"""Screen Time / KnowledgeC collection helpers."""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta, timezone


def split_duration_by_local_day(start_ts, end_ts, local_tz):
    current = start_ts.astimezone(local_tz)
    end_local = end_ts.astimezone(local_tz)
    while current < end_local:
        next_midnight = (current + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        segment_end = min(next_midnight, end_local)
        seconds = max((segment_end - current).total_seconds(), 0)
        if seconds > 0:
            yield current.date().isoformat(), seconds
        current = segment_end


def detect_screen_time_db(candidates):
    for path in candidates:
        if path.exists():
            return path
    return None


def collect_screen_time(dt_from, dt_to, *, candidates, apple_epoch, local_tz):
    db_path = detect_screen_time_db(candidates)
    if not db_path:
        return None, "knowledgeC.db not found"

    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()

    daily_seconds = defaultdict(float)
    try:
        shutil.copy2(db_path, tmp.name)
        conn = sqlite3.connect(tmp.name)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ZSTARTDATE, ZENDDATE, COALESCE(ZVALUESTRING, '')
            FROM ZOBJECT
            WHERE ZSTREAMNAME = '/app/usage'
              AND ZSTARTDATE IS NOT NULL
              AND ZENDDATE IS NOT NULL
              AND ZENDDATE > ZSTARTDATE
            ORDER BY ZSTARTDATE
        """)
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.Error as exc:
        return None, f"could not read Screen Time database: {exc}"
    except PermissionError:
        return None, "no access to knowledgeC.db"
    except Exception as exc:
        return None, f"Screen Time read failed: {exc}"
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    for start_raw, end_raw, _bundle_id in rows:
        start_ts = datetime.fromtimestamp(float(start_raw) + apple_epoch, tz=timezone.utc)
        end_ts = datetime.fromtimestamp(float(end_raw) + apple_epoch, tz=timezone.utc)
        if end_ts < dt_from or start_ts > dt_to:
            continue
        clipped_start = max(start_ts, dt_from)
        clipped_end = min(end_ts, dt_to)
        for day, seconds in split_duration_by_local_day(clipped_start, clipped_end, local_tz):
            daily_seconds[day] += seconds

    return daily_seconds, str(db_path)
