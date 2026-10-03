import type { EngineInterface, Register } from 'claude-code'

import { isUnconfiguredLine, parsePayload, summaryText, type TruthPayload } from './summary'

// `/gittan [range]`: the word after the command picks the report flag.
const RANGES: Record<string, { flag: string; label: string }> = {
  today: { flag: '--today', label: 'today' },
  yesterday: { flag: '--yesterday', label: 'yesterday' },
  week: { flag: '--last-week', label: 'last 7 days' },
}

const STATUS_TIMEOUT_MS = 15_000
const REPORT_TIMEOUT_MS = 180_000

// Once per load: an unconfigured repo is worth one nudge, not one per turn.
let hasWarnedUnconfigured = false

// The status line is `gittan statusline`: config, git remote and the observed
// cache only, no collectors, so it is cheap enough to run after every turn.
async function refreshStatus($: EngineInterface, command: string): Promise<void> {
  const cwd = await $.session.cwd()
  let line = ''
  try {
    const ran = await $.process.run([command, 'statusline', '--cwd', cwd], { timeoutMs: STATUS_TIMEOUT_MS })
    line = ran.exitCode === 0 ? ran.stdout.trim() : ''
  } catch {
    line = `gittan: could not run "${command}" (set the plugin's gittan executable in /config)`
  }
  $.ui.status(line || undefined)
  if (isUnconfiguredLine(line) && !hasWarnedUnconfigured) {
    hasWarnedUnconfigured = true
    $.ui.toast('gittan: this repo matches no project profile, so its hours land unclassified. Run `gittan map`.', {
      timeoutMs: 8000,
    })
  }
}

async function runReport($: EngineInterface, command: string, flag: string): Promise<TruthPayload | string> {
  const argv = [command, 'report', flag, '--format', 'json', '--screen-time', 'off', '--quiet']
  let ran
  try {
    ran = await $.process.run(argv, { timeoutMs: REPORT_TIMEOUT_MS })
  } catch {
    return `could not run "${command}" (set the plugin's gittan executable in /config)`
  }
  if (ran.exitCode !== 0) return `"${command} report" exited ${ran.exitCode}`
  return parsePayload(ran.stdout) ?? 'report output was not JSON'
}

export const register: Register = (on, options) => {
  const command = String(options.command ?? 'gittan') || 'gittan'
  hasWarnedUnconfigured = false

  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'gittan',
      description: 'Gittan hours: /gittan [today|yesterday|week (last 7 days)]',
    })
    // Off the start dispatch, so the first prompt never waits on gittan.
    if (e.isInteractive) $.clock.after(0, () => void refreshStatus($, command))
    return next(e)
  })

  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    // The main loop's turns only: a subagent finishing changes nothing here.
    if (e.agentId === undefined) $.clock.after(0, () => void refreshStatus($, command))
    return done
  })

  on('command.run', { command: 'gittan' }, async ($, e) => {
    const word = e.args.trim().toLowerCase() || 'today'
    const range = RANGES[word]
    if (!range) return { text: `Usage: /gittan [${Object.keys(RANGES).join('|')}]` }
    const payload = await runReport($, command, range.flag)
    if (typeof payload === 'string') return { text: `gittan: ${payload}` }
    return { text: summaryText(payload, range.label) }
  })
}
