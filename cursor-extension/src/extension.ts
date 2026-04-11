import * as path from "path";
import * as os from "os";
import * as fs from "fs/promises";
import * as vscode from "vscode";
import { spawn } from "child_process";

type RunOptions = {
  dateFrom?: string;
  dateTo?: string;
  today?: boolean;
};

type SourceMode = "on" | "off" | "auto";

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
    chrome_source?: "on" | "off";
    mail_source?: SourceMode;
    github_source?: SourceMode;
    screen_time?: SourceMode;
    github_user?: string;
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
    vscode.commands.registerCommand("timelogExtract.openWizardBrowserPreview", () =>
      openWizardBrowserPreview()
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
    }),
    vscode.commands.registerCommand("timelogExtract.quickStart", async () => {
      const pick = await vscode.window.showQuickPick(
        [
          { label: "Open Setup Wizard", id: "wizard" },
          { label: "Open Setup Wizard (Browser Preview)", id: "preview" },
          { label: "Run Report (Today)", id: "today" },
        ],
        { placeHolder: "Timelog quick start" }
      );
      if (!pick) {
        return;
      }
      if (pick.id === "wizard") {
        await vscode.commands.executeCommand("timelogExtract.openWizard");
      } else if (pick.id === "preview") {
        await vscode.commands.executeCommand("timelogExtract.openWizardBrowserPreview");
      } else if (pick.id === "today") {
        await vscode.commands.executeCommand("timelogExtract.runToday");
      }
    })
  );

  const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBar.text = "$(clock) Timelog Setup";
  statusBar.tooltip = "Open Timelog quick start";
  statusBar.command = "timelogExtract.quickStart";
  statusBar.show();
  context.subscriptions.push(statusBar);

  void maybeShowFirstRunPrompt(context);
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
  const chromeSource = cfg.get<"on" | "off">("chromeSource", "on");
  const mailSource = cfg.get<SourceMode>("mailSource", "auto");
  const githubSource = cfg.get<SourceMode>("githubSource", "auto");
  const screenTime = cfg.get<SourceMode>("screenTime", "auto");
  const githubUser = cfg.get<string>("githubUser", "");

  const output = vscode.window.createOutputChannel("Timelog Extract");
  output.show(true);
  output.appendLine(
    `Running timelog engine API (chrome=${chromeSource}, mail=${mailSource}, github=${githubSource}, screenTime=${screenTime})...`
  );

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Timelog report in progress",
      cancellable: false,
    },
    async () => {
      try {
        const result = await runEngineExtract(
          root,
          pythonPath,
          projectsConfig,
          worklogPath,
          options,
          includeUncategorized,
          generatePdf,
          chromeSource,
          mailSource,
          githubSource,
          screenTime,
          githubUser
        );
        const payload = result.payload;
        output.appendLine(
          `Done. Estimated hours: ${payload?.totals?.hours_estimated ?? 0}, days: ${payload?.totals?.days_with_activity ?? 0}, events: ${payload?.totals?.event_count ?? 0}`
        );
        output.appendLine(JSON.stringify(payload, null, 2));

        if (result.pdf_path) {
          output.appendLine(`PDF created: ${result.pdf_path}`);
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

async function runEngineExtract(
  root: string,
  pythonPath: string,
  projectsConfig: string,
  worklogPath: string,
  options: RunOptions,
  includeUncategorized: boolean,
  generatePdf: boolean,
  chromeSource: "on" | "off",
  mailSource: SourceMode,
  githubSource: SourceMode,
  screenTime: SourceMode,
  githubUser: string
): Promise<EngineRunWithPdfResponse> {
  const request: EngineRunRequest & { generate_pdf: boolean } = {
    config_path: projectsConfig,
    date_from: options.dateFrom ?? null,
    date_to: options.dateTo ?? null,
    options: {
      today: Boolean(options.today),
      worklog: worklogPath,
      include_uncategorized: includeUncategorized,
      quiet: true,
      source_summary: true,
      chrome_source: chromeSource,
      mail_source: mailSource,
      github_source: githubSource,
      screen_time: screenTime,
      github_user: githubUser.trim() || undefined,
    },
    generate_pdf: generatePdf,
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
    throw new Error(stderr || `Engine API failed with exit code ${exitCode}`);
  }
  return parsePdfResponseOrThrow(stdout);
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
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd });
    let stdout = "";
    let stderr = "";
    let settled = false;
    child.stdout.on("data", (d: Buffer) => {
      stdout += d.toString();
    });
    child.stderr.on("data", (d: Buffer) => {
      stderr += d.toString();
    });
    child.on("error", (err) => {
      if (!settled) {
        settled = true;
        reject(err);
      }
    });
    child.on("close", (code) => {
      if (!settled) {
        settled = true;
        resolve({ stdout, stderr, exitCode: code });
      }
    });
    if (stdinData !== undefined && child.stdin) {
      child.stdin.write(stdinData);
    }
    if (child.stdin) {
      child.stdin.end();
    }
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
    const cfg = vscode.workspace.getConfiguration("timelogExtract");
    if (msg?.type === "requestSettings") {
      panel.webview.postMessage({
        type: "settings",
        projectsConfig: cfg.get<string>("projectsConfig", "${workspaceFolder}/timelog_projects.json"),
        worklogPath: cfg.get<string>("worklogPath", "${workspaceFolder}/TIMELOG.md"),
        includeUncategorized: cfg.get<boolean>("includeUncategorized", false),
        generatePdf: cfg.get<boolean>("generatePdf", true),
        chromeSource: cfg.get<"on" | "off">("chromeSource", "on"),
        mailSource: cfg.get<SourceMode>("mailSource", "auto"),
        githubSource: cfg.get<SourceMode>("githubSource", "auto"),
        screenTime: cfg.get<SourceMode>("screenTime", "auto"),
        githubUser: cfg.get<string>("githubUser", ""),
        consentAccepted: cfg.get<boolean>("consentAccepted", false),
      });
    }
    if (msg?.type === "saveSettings") {
      if (!msg.consentAccepted) {
        void vscode.window.showErrorMessage("Please accept consent before saving settings.");
        return;
      }
      await cfg.update("projectsConfig", msg.projectsConfig, vscode.ConfigurationTarget.Workspace);
      await cfg.update("worklogPath", msg.worklogPath, vscode.ConfigurationTarget.Workspace);
      await cfg.update("includeUncategorized", Boolean(msg.includeUncategorized), vscode.ConfigurationTarget.Workspace);
      await cfg.update("generatePdf", Boolean(msg.generatePdf), vscode.ConfigurationTarget.Workspace);
      await cfg.update("chromeSource", msg.chromeSource, vscode.ConfigurationTarget.Workspace);
      await cfg.update("mailSource", msg.mailSource, vscode.ConfigurationTarget.Workspace);
      await cfg.update("githubSource", msg.githubSource, vscode.ConfigurationTarget.Workspace);
      await cfg.update("screenTime", msg.screenTime, vscode.ConfigurationTarget.Workspace);
      await cfg.update("githubUser", msg.githubUser, vscode.ConfigurationTarget.Workspace);
      await cfg.update("consentAccepted", true, vscode.ConfigurationTarget.Workspace);
      void vscode.window.showInformationMessage("Timelog settings saved to workspace.");
    }
    if (msg?.type === "runToday") {
      if (!cfg.get<boolean>("consentAccepted", false)) {
        void vscode.window.showErrorMessage("Accept consent and save settings before running.");
        return;
      }
      await runTimelog({ today: true });
    }
  }, undefined, context.subscriptions);
}

async function openWizardBrowserPreview(): Promise<void> {
  const previewHtml = getWizardHtml().replace(
    "const vscode = acquireVsCodeApi();",
    "const vscode = { postMessage: () => {} };"
  );
  const previewPath = path.join(os.tmpdir(), "timelog-wizard-preview.html");
  await fs.writeFile(previewPath, previewHtml, "utf-8");
  await vscode.env.openExternal(vscode.Uri.file(previewPath));
  void vscode.window.showInformationMessage("Opened wizard browser preview.");
}

async function maybeShowFirstRunPrompt(context: vscode.ExtensionContext): Promise<void> {
  const seenKey = "timelog.quickStartPromptSeen";
  if (context.globalState.get<boolean>(seenKey, false)) {
    return;
  }
  const action = await vscode.window.showInformationMessage(
    "Timelog Extract is ready. Open setup now?",
    "Open Wizard",
    "Browser Preview",
    "Later"
  );
  await context.globalState.update(seenKey, true);
  if (action === "Open Wizard") {
    await vscode.commands.executeCommand("timelogExtract.openWizard");
  } else if (action === "Browser Preview") {
    await vscode.commands.executeCommand("timelogExtract.openWizardBrowserPreview");
  }
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
    select { width: 100%; margin-top: 4px; padding: 6px; }
    button { margin-right: 8px; margin-top: 10px; padding: 8px 12px; }
    .muted { color: #777; font-size: 0.9rem; }
  </style>
</head>
<body>
  <h1>Timelog Setup Wizard</h1>
  <div class="card">
    <p><strong>Consent</strong>: Timelog Extract reads local files/databases only. No cloud upload path is used in the report engine.</p>
    <label><input id="consentAccepted" type="checkbox" /> I understand and consent to local data source scanning for this workspace.</label>
    <p class="muted">Privacy-sensitive sources: Apple Mail, browser history, and Screen Time. Keep them off/auto unless needed.</p>
  </div>
  <div class="card">
    <label>Projects config path</label>
    <input id="projectsConfig" type="text" value="\${workspaceFolder}/timelog_projects.json" />
    <label>Worklog path</label>
    <input id="worklogPath" type="text" value="\${workspaceFolder}/TIMELOG.md" />
    <label><input id="includeUncategorized" type="checkbox" /> Include uncategorized events</label>
    <label><input id="generatePdf" type="checkbox" checked /> Generate PDF after run</label>
    <label>Chrome source</label>
    <select id="chromeSource">
      <option value="on">on</option>
      <option value="off">off</option>
    </select>
    <label>Apple Mail source</label>
    <select id="mailSource">
      <option value="auto">auto</option>
      <option value="on">on</option>
      <option value="off">off</option>
    </select>
    <label>GitHub source</label>
    <select id="githubSource">
      <option value="auto">auto</option>
      <option value="on">on</option>
      <option value="off">off</option>
    </select>
    <label>Screen Time source</label>
    <select id="screenTime">
      <option value="auto">auto</option>
      <option value="on">on</option>
      <option value="off">off</option>
    </select>
    <label>GitHub user (optional, for GitHub source)</label>
    <input id="githubUser" type="text" placeholder="your-login" />
    <p id="scanSummary" class="muted"></p>
    <div>
      <button id="saveBtn">Save settings</button>
      <button id="runBtn">Run today</button>
    </div>
  </div>
  <script>
    const vscode = acquireVsCodeApi();
    const ids = {
      projectsConfig: document.getElementById("projectsConfig"),
      worklogPath: document.getElementById("worklogPath"),
      includeUncategorized: document.getElementById("includeUncategorized"),
      generatePdf: document.getElementById("generatePdf"),
      chromeSource: document.getElementById("chromeSource"),
      mailSource: document.getElementById("mailSource"),
      githubSource: document.getElementById("githubSource"),
      screenTime: document.getElementById("screenTime"),
      githubUser: document.getElementById("githubUser"),
      consentAccepted: document.getElementById("consentAccepted"),
      scanSummary: document.getElementById("scanSummary")
    };

    const updateSummary = () => {
      ids.scanSummary.textContent =
        "Will scan with sources: " +
        "chrome=" + ids.chromeSource.value + ", " +
        "mail=" + ids.mailSource.value + ", " +
        "github=" + ids.githubSource.value + ", " +
        "screenTime=" + ids.screenTime.value + ".";
    };

    window.addEventListener("message", (event) => {
      const msg = event.data;
      if (msg?.type !== "settings") return;
      ids.projectsConfig.value = msg.projectsConfig || ids.projectsConfig.value;
      ids.worklogPath.value = msg.worklogPath || ids.worklogPath.value;
      ids.includeUncategorized.checked = Boolean(msg.includeUncategorized);
      ids.generatePdf.checked = Boolean(msg.generatePdf);
      ids.chromeSource.value = msg.chromeSource || "on";
      ids.mailSource.value = msg.mailSource || "auto";
      ids.githubSource.value = msg.githubSource || "auto";
      ids.screenTime.value = msg.screenTime || "auto";
      ids.githubUser.value = msg.githubUser || "";
      ids.consentAccepted.checked = Boolean(msg.consentAccepted);
      updateSummary();
    });

    ["chromeSource","mailSource","githubSource","screenTime"].forEach((id) => {
      document.getElementById(id).addEventListener("change", updateSummary);
    });

    document.getElementById("saveBtn").addEventListener("click", () => {
      vscode.postMessage({
        type: "saveSettings",
        projectsConfig: ids.projectsConfig.value,
        worklogPath: ids.worklogPath.value,
        includeUncategorized: ids.includeUncategorized.checked,
        generatePdf: ids.generatePdf.checked,
        chromeSource: ids.chromeSource.value,
        mailSource: ids.mailSource.value,
        githubSource: ids.githubSource.value,
        screenTime: ids.screenTime.value,
        githubUser: ids.githubUser.value,
        consentAccepted: ids.consentAccepted.checked
      });
    });
    document.getElementById("runBtn").addEventListener("click", () => {
      vscode.postMessage({ type: "runToday" });
    });
    vscode.postMessage({ type: "requestSettings" });
    updateSummary();
  </script>
</body>
</html>`;
}
