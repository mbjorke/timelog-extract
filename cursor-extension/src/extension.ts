import * as path from "path";
import * as vscode from "vscode";
import { spawn } from "child_process";

type RunOptions = {
  dateFrom?: string;
  dateTo?: string;
  today?: boolean;
};

type EngineRunRequest = {
  config_path: string;
  date_from: string | null;
  date_to: string | null;
  options: {
    today: boolean;
    worklog: string;
    include_uncategorized: boolean;
    quiet: boolean;
    source_summary?: boolean;
  };
};

type TruthPayload = {
  schema: string;
  version: string;
  totals: {
    hours_estimated: number;
    days_with_activity: number;
    event_count: number;
  };
  days: Record<string, unknown>;
};

type EngineRunWithPdfResponse = {
  payload: TruthPayload;
  pdf_path: string | null;
};

export function activate(context: vscode.ExtensionContext): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("timelogExtract.openWizard", () =>
      openWizard(context)
    ),
    vscode.commands.registerCommand("timelogExtract.runToday", () =>
      runTimelog({ today: true })
    ),
    vscode.commands.registerCommand("timelogExtract.runRange", async () => {
      const from = await vscode.window.showInputBox({
        prompt: "From date (YYYY-MM-DD)",
      });
      const to = await vscode.window.showInputBox({
        prompt: "To date (YYYY-MM-DD)",
      });
      if (!from || !to) {
        return;
      }
      await runTimelog({ dateFrom: from, dateTo: to });
    }),
    vscode.commands.registerCommand("timelogExtract.openOutputFolder", async () => {
      const root = workspaceRoot();
      if (!root) {
        return;
      }
      const uri = vscode.Uri.file(path.join(root, "output", "pdf"));
      await vscode.commands.executeCommand("revealFileInOS", uri);
    })
  );
}

export function deactivate(): void {}

function workspaceRoot(): string | undefined {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

async function runTimelog(options: RunOptions): Promise<void> {
  const root = workspaceRoot();
  if (!root) {
    vscode.window.showErrorMessage("Open a workspace folder first.");
    return;
  }

  const cfg = vscode.workspace.getConfiguration("timelogExtract");
  const pythonPath = cfg.get<string>("pythonPath", "python3");
  const projectsConfig = cfg
    .get<string>("projectsConfig", "${workspaceFolder}/timelog_projects.json")
    .replace("${workspaceFolder}", root);
  const worklogPath = cfg
    .get<string>("worklogPath", "${workspaceFolder}/TIMELOG.md")
    .replace("${workspaceFolder}", root);
  const includeUncategorized = cfg.get<boolean>("includeUncategorized", false);
  const generatePdf = cfg.get<boolean>("generatePdf", true);

  const output = vscode.window.createOutputChannel("Timelog Extract");
  output.show(true);
  output.appendLine("Running timelog engine API...");

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Timelog report in progress",
      cancellable: false,
    },
    async () => {
      try {
        const payload = await runEnginePayload(
          root,
          pythonPath,
          projectsConfig,
          worklogPath,
          options,
          includeUncategorized
        );
        output.appendLine(
          `Done. Estimated hours: ${payload?.totals?.hours_estimated ?? 0}, days: ${payload?.totals?.days_with_activity ?? 0}, events: ${payload?.totals?.event_count ?? 0}`
        );
        output.appendLine(JSON.stringify(payload, null, 2));

        if (generatePdf) {
          output.appendLine("Generating invoice PDF via engine API...");
          const pdfPath = await runEnginePdf(
            root,
            pythonPath,
            projectsConfig,
            worklogPath,
            options,
            includeUncategorized
          );
          if (pdfPath) {
            output.appendLine(`PDF created: ${pdfPath}`);
          }
        }

        void vscode.window.showInformationMessage(
          "Timelog run completed. See 'Timelog Extract' output channel."
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        output.appendLine(`Error: ${msg}`);
        void vscode.window.showErrorMessage(`Timelog run failed: ${msg}`);
      }
    }
  );
}

async function runEnginePayload(
  root: string,
  pythonPath: string,
  projectsConfig: string,
  worklogPath: string,
  options: RunOptions,
  includeUncategorized: boolean
): Promise<TruthPayload> {
  const request: EngineRunRequest = {
    config_path: projectsConfig,
    date_from: options.dateFrom ?? null,
    date_to: options.dateTo ?? null,
    options: {
      today: Boolean(options.today),
      worklog: worklogPath,
      include_uncategorized: includeUncategorized,
      quiet: true,
      source_summary: true,
    },
  };
  const code = [
    "import json,sys",
    "from core.engine_api import run_report_payload",
    "req=json.load(sys.stdin)",
    "payload=run_report_payload(req['config_path'], req.get('date_from'), req.get('date_to'), req.get('options', {}))",
    "print(json.dumps(payload, ensure_ascii=False))",
  ].join(";");
  const { stdout, stderr, exitCode } = await spawnCollect(
    pythonPath,
    ["-c", code],
    root,
    JSON.stringify(request)
  );
  if (exitCode !== 0) {
    throw new Error(stderr || `Engine API failed with exit code ${exitCode}`);
  }
  return parseTruthPayloadOrThrow(stdout);
}

async function runEnginePdf(
  root: string,
  pythonPath: string,
  projectsConfig: string,
  worklogPath: string,
  options: RunOptions,
  includeUncategorized: boolean
): Promise<string | null> {
  const request: EngineRunRequest & { generate_pdf: boolean } = {
    config_path: projectsConfig,
    date_from: options.dateFrom ?? null,
    date_to: options.dateTo ?? null,
    options: {
      today: Boolean(options.today),
      worklog: worklogPath,
      include_uncategorized: includeUncategorized,
      quiet: true,
    },
    generate_pdf: true,
  };
  const code = [
    "import json,sys",
    "from core.engine_api import run_report_with_optional_pdf",
    "req=json.load(sys.stdin)",
    "out=run_report_with_optional_pdf(req['config_path'], req.get('date_from'), req.get('date_to'), req.get('options', {}), generate_pdf=bool(req.get('generate_pdf', False)))",
    "print(json.dumps(out, ensure_ascii=False))",
  ].join(";");
  const { stdout, stderr, exitCode } = await spawnCollect(
    pythonPath,
    ["-c", code],
    root,
    JSON.stringify(request)
  );
  if (exitCode !== 0) {
    throw new Error(stderr || `PDF generation failed with exit code ${exitCode}`);
  }
  const out = parsePdfResponseOrThrow(stdout);
  return out?.pdf_path ?? null;
}

function parseTruthPayloadOrThrow(stdout: string): TruthPayload {
  let parsed: unknown;
  try {
    parsed = JSON.parse(stdout);
  } catch (err) {
    throw new Error(
      `Engine output is not valid JSON: ${err instanceof Error ? err.message : String(err)}`
    );
  }
  if (!isTruthPayload(parsed)) {
    throw new Error("Engine payload failed schema/version validation.");
  }
  return parsed;
}

function parsePdfResponseOrThrow(stdout: string): EngineRunWithPdfResponse {
  let parsed: unknown;
  try {
    parsed = JSON.parse(stdout);
  } catch (err) {
    throw new Error(
      `Engine PDF output is not valid JSON: ${err instanceof Error ? err.message : String(err)}`
    );
  }
  if (!isEngineRunWithPdfResponse(parsed)) {
    throw new Error("Engine PDF response failed payload validation.");
  }
  return parsed;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isTruthPayload(value: unknown): value is TruthPayload {
  if (!isRecord(value)) {
    return false;
  }
  if (value.schema !== "timelog_extract.truth_payload") {
    return false;
  }
  if (value.version !== "1") {
    return false;
  }
  if (!isRecord(value.totals)) {
    return false;
  }
  if (!isRecord(value.days)) {
    return false;
  }
  return (
    typeof value.totals.hours_estimated === "number" &&
    typeof value.totals.days_with_activity === "number" &&
    typeof value.totals.event_count === "number"
  );
}

function isEngineRunWithPdfResponse(value: unknown): value is EngineRunWithPdfResponse {
  if (!isRecord(value)) {
    return false;
  }
  if (!("pdf_path" in value)) {
    return false;
  }
  if (!(value.pdf_path === null || typeof value.pdf_path === "string")) {
    return false;
  }
  return isTruthPayload(value.payload);
}

function spawnCollect(
  command: string,
  args: string[],
  cwd: string,
  stdinData?: string
): Promise<{ stdout: string; stderr: string; exitCode: number | null }> {
  return new Promise((resolve) => {
    const child = spawn(command, args, { cwd });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d: Buffer) => {
      stdout += d.toString();
    });
    child.stderr.on("data", (d: Buffer) => {
      stderr += d.toString();
    });
    child.on("close", (code) => resolve({ stdout, stderr, exitCode: code }));
    if (stdinData !== undefined) {
      child.stdin.write(stdinData);
    }
    child.stdin.end();
  });
}

function openWizard(context: vscode.ExtensionContext): void {
  const panel = vscode.window.createWebviewPanel(
    "timelogExtractWizard",
    "Timelog Setup Wizard",
    vscode.ViewColumn.One,
    { enableScripts: true }
  );

  panel.webview.html = getWizardHtml();
  panel.webview.onDidReceiveMessage(async (msg) => {
    if (msg?.type === "saveSettings") {
      const cfg = vscode.workspace.getConfiguration("timelogExtract");
      await cfg.update("projectsConfig", msg.projectsConfig, vscode.ConfigurationTarget.Workspace);
      await cfg.update("worklogPath", msg.worklogPath, vscode.ConfigurationTarget.Workspace);
      await cfg.update("includeUncategorized", Boolean(msg.includeUncategorized), vscode.ConfigurationTarget.Workspace);
      await cfg.update("generatePdf", Boolean(msg.generatePdf), vscode.ConfigurationTarget.Workspace);
      void vscode.window.showInformationMessage("Timelog settings saved to workspace.");
    }
    if (msg?.type === "runToday") {
      await runTimelog({ today: true });
    }
  }, undefined, context.subscriptions);
}

function getWizardHtml(): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Timelog Setup Wizard</title>
  <style>
    body { font-family: sans-serif; max-width: 780px; margin: 24px auto; }
    h1 { font-size: 1.4rem; }
    .card { border: 1px solid #444; border-radius: 8px; padding: 12px; margin-bottom: 12px; }
    label { display: block; margin-top: 8px; font-weight: 600; }
    input[type=text] { width: 100%; margin-top: 4px; padding: 6px; }
    button { margin-right: 8px; margin-top: 10px; padding: 8px 12px; }
  </style>
</head>
<body>
  <h1>Timelog Setup Wizard</h1>
  <div class="card">
    <p>This plugin reads local activity logs to estimate work time. Review source consent before use.</p>
  </div>
  <div class="card">
    <label>Projects config path</label>
    <input id="projectsConfig" type="text" value="\${workspaceFolder}/timelog_projects.json" />
    <label>Worklog path</label>
    <input id="worklogPath" type="text" value="\${workspaceFolder}/TIMELOG.md" />
    <label><input id="includeUncategorized" type="checkbox" /> Include uncategorized events</label>
    <label><input id="generatePdf" type="checkbox" checked /> Generate PDF after run</label>
    <div>
      <button id="saveBtn">Save settings</button>
      <button id="runBtn">Run today</button>
    </div>
  </div>
  <script>
    const vscode = acquireVsCodeApi();
    document.getElementById("saveBtn").addEventListener("click", () => {
      vscode.postMessage({
        type: "saveSettings",
        projectsConfig: document.getElementById("projectsConfig").value,
        worklogPath: document.getElementById("worklogPath").value,
        includeUncategorized: document.getElementById("includeUncategorized").checked,
        generatePdf: document.getElementById("generatePdf").checked
      });
    });
    document.getElementById("runBtn").addEventListener("click", () => {
      vscode.postMessage({ type: "runToday" });
    });
  </script>
</body>
</html>`;
}
