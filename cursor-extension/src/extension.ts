import * as path from "path";
import * as vscode from "vscode";
import { spawn } from "child_process";

type RunOptions = {
  dateFrom?: string;
  dateTo?: string;
  today?: boolean;
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

  const args = [
    "timelog_extract.py",
    "--projects-config",
    projectsConfig,
    "--worklog",
    worklogPath,
    "--source-summary",
  ];

  if (options.today) {
    args.push("--today");
  }
  if (options.dateFrom) {
    args.push("--from", options.dateFrom);
  }
  if (options.dateTo) {
    args.push("--to", options.dateTo);
  }
  if (includeUncategorized) {
    args.push("--include-uncategorized");
  }
  if (generatePdf) {
    args.push("--invoice-pdf");
  }

  const output = vscode.window.createOutputChannel("Timelog Extract");
  output.show(true);
  output.appendLine(`Running: ${pythonPath} ${args.join(" ")}`);

  await vscode.window.withProgress(
    {
      location: vscode.ProgressLocation.Notification,
      title: "Timelog report in progress",
      cancellable: false,
    },
    async () =>
      new Promise<void>((resolve) => {
        const child = spawn(pythonPath, args, { cwd: root });
        child.stdout.on("data", (d: Buffer) => output.append(d.toString()));
        child.stderr.on("data", (d: Buffer) => output.append(d.toString()));
        child.on("close", (code) => {
          if (code === 0) {
            void vscode.window.showInformationMessage(
              "Timelog run completed. See 'Timelog Extract' output channel."
            );
          } else {
            void vscode.window.showErrorMessage(
              `Timelog run failed with exit code ${code}.`
            );
          }
          resolve();
        });
      })
  );
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
