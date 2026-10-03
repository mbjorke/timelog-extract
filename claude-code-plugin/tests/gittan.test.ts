import type { On } from 'claude-code'
import { describe, expect, mock, test } from 'claude-code/testing'

import { STATUSLINES, TODAY_PAYLOAD, UNMATCHED_REPO } from './fixture'
import { isUnconfiguredLine, parsePayload, summaryText } from '../hooks/summary'

const PAYLOAD_TEXT = JSON.stringify(TODAY_PAYLOAD)
const ALPHA_LINE = STATUSLINES['project-alpha'] ?? ''
const UNMATCHED_LINE = STATUSLINES[UNMATCHED_REPO] ?? ''

type World = {
  argvs: string[][]
  statuses: (string | undefined)[]
  toasts: string[]
}

// The engine beneath the plugin: a host whose `gittan` answers with what the
// real CLI printed in the generated mock home, for a session sitting in `repo`.
function host(on: On, repo: string, gittan: 'ok' | 'missing' | 'fails' = 'ok'): World {
  const world: World = { argvs: [], statuses: [], toasts: [] }
  const cwd = `/mock/home/code/${repo}`
  const ok = (stdout: string, exitCode = 0) => ({
    value: { exitCode, stdout, stderr: '', isStdoutTruncated: false, isStderrTruncated: false },
  })
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('session.cwd', () => ({ value: cwd }))
  on('command.register', ($, e) => ({ value: { command: e.name } }))
  on('process.run', ($, e) => {
    world.argvs.push([...e.argv])
    if (gittan === 'missing') throw new Error('spawn gittan ENOENT')
    if (gittan === 'fails') return ok('', 2)
    if (e.argv[1] === 'statusline') return ok(`${STATUSLINES[repo] ?? ''}\n`)
    return ok(PAYLOAD_TEXT)
  })
  on('ui.status', ($, e) => {
    world.statuses.push(e.text)
    return { value: undefined }
  })
  on('ui.toast', ($, e) => {
    world.toasts.push(e.text)
    return { value: undefined }
  })
  return world
}

const start = { cwd: '/mock/home/code', surface: 'terminal', isInteractive: true } as const

const run = (args: string) => ({
  command: 'gittan',
  args,
  origin: { kind: 'composer' },
  presentation: { isFullscreen: false, columns: 120 },
}) as const

const turn = (agentId?: string) => ({
  answer: 'done',
  durationMs: 1,
  isAborted: false,
  turnId: 'turn-1',
  reason: 'answer',
  ...(agentId === undefined ? {} : { agentId }),
}) as const

const statuslineCalls = (world: World) => world.argvs.filter(argv => argv[1] === 'statusline')

describe('helpers over the generated fixture', () => {
  test('the fixture holds the matched and unconfigured statusline cases', () => {
    expect(ALPHA_LINE).toContain('gittan: project-alpha')
    expect(isUnconfiguredLine(ALPHA_LINE)).toBe(false)
    expect(isUnconfiguredLine(UNMATCHED_LINE)).toBe(true)
  })

  test('the summary lists each project with hours', () => {
    const text = summaryText(parsePayload(PAYLOAD_TEXT)!, 'today')
    expect(text).toContain('gittan today: 0.3h estimated')
    expect(text).toContain('project-alpha')
    expect(text).toContain('project-beta')
  })

  test('noise before the JSON is tolerated, garbage is not', () => {
    expect(parsePayload(`warning: something\n${PAYLOAD_TEXT}`)?.totals?.hours_estimated).toBe(0.25)
    expect(parsePayload('not json')).toBeNull()
  })
})

describe('the plugin in a session', () => {
  test('session start shows the statusline for the session directory', async ($, on) => {
    const clock = mock.clock(on)
    const world = host(on, 'project-alpha')
    await $.session.start(start)
    await clock.advance(1)

    expect(world.argvs[0]).toEqual(['gittan', 'statusline', '--cwd', '/mock/home/code/project-alpha'])
    expect(world.statuses).toEqual([ALPHA_LINE])
    expect(world.toasts).toHaveLength(0)
  })

  test('an unconfigured repo is nudged once, not after every turn', async ($, on) => {
    const clock = mock.clock(on)
    const world = host(on, UNMATCHED_REPO)
    on('turn.complete', () => ({ text: '' }))
    await $.session.start(start)
    await clock.advance(1)
    await $.turn.complete(turn())
    await clock.advance(1)
    await $.turn.complete(turn())
    await clock.advance(1)

    expect(statuslineCalls(world)).toHaveLength(3)
    expect(world.statuses[world.statuses.length - 1]).toBe(UNMATCHED_LINE)
    expect(world.toasts).toHaveLength(1)
  })

  test('a subagent finishing does not refresh the line', async ($, on) => {
    const clock = mock.clock(on)
    const world = host(on, 'project-alpha')
    on('turn.complete', () => ({ text: '' }))
    await $.session.start(start)
    await clock.advance(1)
    await $.turn.complete(turn('agent-1'))
    await clock.advance(1)

    expect(statuslineCalls(world)).toHaveLength(1)
  })

  test('a missing gittan says so in the status line', async ($, on) => {
    const clock = mock.clock(on)
    const world = host(on, 'project-alpha', 'missing')
    await $.session.start(start)
    await clock.advance(1)

    expect(world.statuses[world.statuses.length - 1]).toContain('could not run "gittan"')
    expect(world.toasts).toHaveLength(0)
  })

  test('a failing statusline clears the line rather than showing noise', async ($, on) => {
    const clock = mock.clock(on)
    const world = host(on, 'project-alpha', 'fails')
    await $.session.start(start)
    await clock.advance(1)

    expect(world.statuses).toEqual([undefined])
  })

  test('/gittan prints the summary from a JSON report', async ($, on) => {
    mock.clock(on)
    const world = host(on, 'project-alpha')
    await $.session.start({ ...start, isInteractive: false })

    const today = await $.command.run(run(''))
    expect(today.text).toContain('gittan today: 0.3h estimated')
    expect(world.argvs[world.argvs.length - 1]).toEqual(
      ['gittan', 'report', '--today', '--format', 'json', '--screen-time', 'off', '--quiet'],
    )

    await $.command.run(run('week'))
    expect(world.argvs[world.argvs.length - 1]).toContain('--last-week')
  })

  test('/gittan with an unknown range prints usage and runs nothing', async ($, on) => {
    mock.clock(on)
    const world = host(on, 'project-alpha')
    await $.session.start({ ...start, isInteractive: false })

    const answer = await $.command.run(run('fortnight'))
    expect(answer.text).toContain('Usage: /gittan')
    expect(world.argvs).toHaveLength(0)
  })

  test('a failing report surfaces its exit code', async ($, on) => {
    mock.clock(on)
    host(on, 'project-alpha', 'fails')
    await $.session.start({ ...start, isInteractive: false })

    const answer = await $.command.run(run('today'))
    expect(answer.text).toBe('gittan: "gittan report" exited 2')
  })
})
