type SourceMode = "on" | "off" | "auto";

export type WizardSettings = {
  projectsConfig: string;
  worklogPath: string;
  includeUncategorized: boolean;
  generatePdf: boolean;
  chromeSource: "on" | "off";
  mailSource: SourceMode;
  githubSource: SourceMode;
  screenTime: SourceMode;
  githubUser: string;
  consentAccepted: boolean;
};

export function mergeWizardSettings(
  current: WizardSettings,
  patch: Partial<WizardSettings>
): WizardSettings {
  return {
    projectsConfig: patch.projectsConfig ?? current.projectsConfig,
    worklogPath: patch.worklogPath ?? current.worklogPath,
    includeUncategorized: patch.includeUncategorized ?? current.includeUncategorized,
    generatePdf: patch.generatePdf ?? current.generatePdf,
    chromeSource: patch.chromeSource ?? current.chromeSource,
    mailSource: patch.mailSource ?? current.mailSource,
    githubSource: patch.githubSource ?? current.githubSource,
    screenTime: patch.screenTime ?? current.screenTime,
    githubUser: patch.githubUser ?? current.githubUser,
    consentAccepted: patch.consentAccepted ?? current.consentAccepted,
  };
}
