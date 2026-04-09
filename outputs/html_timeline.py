"""Single-file HTML timeline report (embedded JSON + vanilla JS)."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path
from typing import Any, Dict


def write_html_timeline(path: Path, payload: Dict[str, Any]) -> Path:
    """Write a self-contained HTML file with embedded truth payload."""
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    b64 = base64.b64encode(raw).decode("ascii")
    # Safe inside JSON.stringify context — we embed raw JSON in script
    title = html.escape(
        f"Timelog — {payload.get('range', {}).get('from', '')} → {payload.get('range', {}).get('to', '')}"
    )
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    :root {{
      font-family: system-ui, sans-serif;
      background: #0f1419;
      color: #e6edf3;
    }}
    body {{ margin: 0; padding: 1rem 1.25rem 2rem; max-width: 56rem; }}
    h1 {{ font-size: 1.15rem; font-weight: 600; margin: 0 0 0.5rem; }}
    .meta {{ color: #8b949e; font-size: 0.85rem; margin-bottom: 1.25rem; }}
    .day {{ margin-bottom: 1.75rem; }}
    .day-head {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.5rem; }}
    .day-label {{ font-weight: 600; }}
    .day-hours {{ color: #8b949e; font-size: 0.9rem; }}
    .track {{
      position: relative;
      height: 2.25rem;
      background: #161b22;
      border-radius: 6px;
      overflow: hidden;
      border: 1px solid #30363d;
    }}
    .seg {{
      position: absolute;
      top: 0;
      bottom: 0;
      border-radius: 4px;
      opacity: 0.92;
      cursor: pointer;
      box-sizing: border-box;
      border: 1px solid rgba(255,255,255,0.08);
    }}
    .seg:hover {{ filter: brightness(1.08); z-index: 2; }}
    .detail {{ margin-top: 0.75rem; padding: 0.75rem; background: #161b22; border-radius: 6px; border: 1px solid #30363d; display: none; font-size: 0.88rem; }}
    .detail.open {{ display: block; }}
    .detail pre {{ white-space: pre-wrap; word-break: break-word; margin: 0.35rem 0 0; color: #c9d1d9; }}
    .empty {{ color: #8b949e; padding: 2rem 0; }}
    a {{ color: #58a6ff; }}
  </style>
</head>
<body>
  <h1>Timelog timeline</h1>
  <p class="meta">Local-first report · schema v{html.escape(str(payload.get("version", "?")))} ·
    <span id="summary"></span>
  </p>
  <div id="root"></div>
  <script id="payload-b64" type="text/plain">{b64}</script>
  <script>
(function () {{
  const el = document.getElementById("payload-b64");
  const bin = atob(el.textContent.trim());
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const data = JSON.parse(new TextDecoder("utf-8").decode(bytes));
  const root = document.getElementById("root");
  const summary = document.getElementById("summary");
  const totals = data.totals || {{}};
  summary.textContent = (totals.hours_estimated != null ? "≈ " + totals.hours_estimated + " h estimated" : "") +
    (totals.event_count != null ? " · " + totals.event_count + " events" : "");

  const days = data.days || {{}};
  const dayKeys = Object.keys(days).sort();
  if (!dayKeys.length) {{
    root.innerHTML = '<div class="empty">No classified activity in range.</div>';
    return;
  }}

  const palette = ["#238636", "#1f6feb", "#8957e5", "#d29922", "#db61a2", "#3fb950", "#a371f7"];

  function colorForProject(projects) {{
    if (!projects || !projects.length) return palette[0];
    let h = 0;
    const s = String(projects[0]);
    for (let i = 0; i < s.length; i++) h = (h + s.charCodeAt(i) * (i + 1)) % palette.length;
    return palette[h];
  }}

  function parseIso(s) {{
    return new Date(s);
  }}

  dayKeys.forEach(function (day) {{
    const d = days[day];
    const sessions = d.sessions || [];
    const wrap = document.createElement("div");
    wrap.className = "day";
    const head = document.createElement("div");
    head.className = "day-head";
    head.innerHTML = '<div class="day-label">' + day + '</div>' +
      '<div class="day-hours">' + (d.hours_estimated != null ? "≈ " + d.hours_estimated + " h" : "") +
      " · " + sessions.length + " sessions</div>";
    wrap.appendChild(head);

    const track = document.createElement("div");
    track.className = "track";

    const dayStart = parseIso(day + "T00:00:00");
    const dayEnd = new Date(dayStart.getTime() + 24 * 60 * 60 * 1000);

    sessions.forEach(function (sess, idx) {{
      const s = parseIso(sess.start);
      const e = parseIso(sess.end);
      const clipStart = s < dayStart ? dayStart : s;
      const clipEnd = e > dayEnd ? dayEnd : e;
      if (clipEnd <= clipStart) return;
      const span = dayEnd - dayStart;
      const left = (clipStart - dayStart) / span * 100;
      const width = (clipEnd - clipStart) / span * 100;
      const seg = document.createElement("div");
      seg.className = "seg";
      seg.style.left = left.toFixed(3) + "%";
      seg.style.width = width.toFixed(3) + "%";
      seg.style.background = colorForProject(sess.projects);
      seg.title = (sess.projects && sess.projects.length ? sess.projects.join(", ") : "—") +
        " · " + (sess.hours_estimated != null ? sess.hours_estimated + "h" : "");
      seg.addEventListener("click", function () {{
        const id = "detail-" + day + "-" + idx;
        document.querySelectorAll(".detail.open").forEach(function (x) {{ x.classList.remove("open"); }});
        const box = document.getElementById(id);
        if (box) box.classList.add("open");
      }});
      track.appendChild(seg);
    }});

    wrap.appendChild(track);

    sessions.forEach(function (sess, idx) {{
      const detail = document.createElement("div");
      detail.className = "detail";
      detail.id = "detail-" + day + "-" + idx;
      const lines = (sess.events || []).map(function (ev) {{
        return (ev.local_time || ev.timestamp) + " [" + ev.source + "] [" + ev.project + "] " + ev.detail;
      }}).join("\\n");
      detail.innerHTML = "<strong>Session " + (idx + 1) + "</strong> · " +
        (sess.hours_estimated != null ? sess.hours_estimated + " h" : "") +
        "<pre>" + lines.replace(/</g, "&lt;") + "</pre>";
      wrap.appendChild(detail);
    }});

    root.appendChild(wrap);
  }});
}})();
  </script>
</body>
</html>
"""
    path.write_text(page, encoding="utf-8")
    return path
