const ALLOWED_COMMANDS = new Set([
  "help",
  "clear",
  "gittan doctor",
  "gittan report --today --source-summary",
  "gittan report --today --format json",
]);

const TRUTH_PAYLOAD = {
  schema: "timelog_extract.truth_payload",
  version: 1,
  demo: true,
  totals: {
    event_count: 31,
    hours_estimated: 2.1,
  },
  truth_model: {
    observed_time_hours: 2.1,
    classified_candidate_hours: 1.8,
    approved_invoice_hours: 0.0,
    approval_state: "human_review_required",
  },
  projects: [
    {
      name: "Gittan",
      candidate_hours: 1.2,
      decision_class: "work",
      confidence: "high",
      evidence: ["cursor log", "github.com", "worklog note"],
    },
    {
      name: "Client A",
      candidate_hours: 0.6,
      decision_class: "maybe",
      confidence: "needs_review",
      evidence: ["browser domain", "GitHub PR review"],
    },
  ],
};

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

function textResponse(body, status = 200) {
  return new Response(body, {
    status,
    headers: {
      ...corsHeaders(),
      "Content-Type": "text/plain; charset=utf-8",
    },
  });
}

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: {
      ...corsHeaders(),
      "Content-Type": "application/json; charset=utf-8",
    },
  });
}

function normalizeCommand(line) {
  return String(line || "")
    .trim()
    .replace(/\s+/g, " ")
    .toLowerCase();
}

function demoOutput(line) {
  const command = normalizeCommand(line);

  if (!ALLOWED_COMMANDS.has(command)) {
    return {
      ok: false,
      body: {
        error: "Command not allowed in demo sandbox. Try: help",
      },
    };
  }

  if (command === "help") {
    return {
      ok: true,
      body: `Demo sandbox — allowlisted commands:
  gittan doctor
  gittan report --today --source-summary
  gittan report --today --format json
  help
  clear
`,
    };
  }

  if (command === "clear") {
    return {
      ok: true,
      body: "[demo] Screen cleared.\n",
    };
  }

  if (command === "gittan doctor") {
    return {
      ok: true,
      body: `Gittan doctor — demo environment
Local-first checks for a safe demo path.

Project config         OK — demo projects loaded
Local worklog          OK — TIMELOG.md fixture
Cursor / IDE logs      OK — local demo events
Browser history        OK — local Chrome fixture
GitHub activity        OK — public activity fixture
Approval workflow      MANUAL — classified time is not invoice truth

Next: run \`gittan report --today --source-summary\`
`,
    };
  }

  if (command === "gittan report --today --source-summary") {
    return {
      ok: true,
      body: `Gittan report — today (demo fixture)
Source summary

Cursor / IDE           12 events
Chrome                 9 events
GitHub activity        4 events
AI agent logs          3 events
TIMELOG.md             3 events
Total: 31

Observed time:             2.1h
Classified candidates:    1.8h
Approved invoice time:    0.0h (human review required)

Gittan organizes evidence; it does not approve invoice truth.
Optional: run \`gittan report --today --format json\`
`,
    };
  }

  return {
    ok: true,
    body: `${JSON.stringify(TRUTH_PAYLOAD, null, 2)}\n`,
  };
}

async function parseJsonBody(request) {
  try {
    return await request.json();
  } catch (_error) {
    return null;
  }
}

function createSession() {
  const random = crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
  return jsonResponse({ session_id: random }, 201);
}

async function execCommand(request) {
  const payload = await parseJsonBody(request);
  if (!payload || typeof payload !== "object") {
    return jsonResponse({ error: "invalid JSON body" }, 400);
  }

  const result = demoOutput(payload.line);
  if (!result.ok) {
    return jsonResponse(result.body, 400);
  }
  return textResponse(result.body);
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const pathname = url.pathname.replace(/\/+$/, "") || "/";

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }

    if (request.method === "GET" && pathname === "/demo/health") {
      return jsonResponse({ status: "ok" });
    }

    if (request.method === "POST" && pathname === "/demo/sessions") {
      return createSession();
    }

    if (request.method === "POST" && /^\/demo\/sessions\/[^/]+\/exec$/.test(pathname)) {
      return execCommand(request);
    }

    return jsonResponse({ error: "not found" }, 404);
  },
};
