import test from "node:test";
import assert from "node:assert/strict";
import { mergeWizardSettings, type WizardSettings } from "./wizard_settings";

test("wizard safe-edit: editing githubUser does not overwrite unrelated selections", () => {
  const current: WizardSettings = {
    projectsConfig: "${workspaceFolder}/timelog_projects.json",
    worklogPath: "${workspaceFolder}/TIMELOG.md",
    includeUncategorized: false,
    generatePdf: true,
    chromeSource: "off",
    mailSource: "on",
    githubSource: "auto",
    screenTime: "off",
    githubUser: "old-user",
    consentAccepted: true,
  };

  const merged = mergeWizardSettings(current, { githubUser: "work-user,personal-user" });

  assert.equal(merged.githubUser, "work-user,personal-user");
  assert.equal(merged.chromeSource, "off");
  assert.equal(merged.mailSource, "on");
  assert.equal(merged.githubSource, "auto");
  assert.equal(merged.screenTime, "off");
  assert.equal(merged.includeUncategorized, false);
  assert.equal(merged.generatePdf, true);
  assert.equal(merged.projectsConfig, "${workspaceFolder}/timelog_projects.json");
});
