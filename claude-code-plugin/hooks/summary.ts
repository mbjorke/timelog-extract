// Pure helpers over gittan's output. Kept free of `$` so the tests can feed
// them the generated fixture directly.

export type TruthPayload = {
  totals?: { hours_estimated?: number }
  projects?: Record<string, number>
}

// `gittan statusline` leads its unconfigured-repo line with this mark
// (scripts/gittan_statusline.py::WARNING).
export const isUnconfiguredLine = (line: string): boolean => line.startsWith('⚠')

export function parsePayload(stdout: string): TruthPayload | null {
  const start = stdout.indexOf('{')
  if (start < 0) return null
  try {
    const parsed: unknown = JSON.parse(stdout.slice(start))
    return parsed !== null && typeof parsed === 'object' ? (parsed as TruthPayload) : null
  } catch {
    return null
  }
}

export const formatHours = (hours: number): string => `${hours.toFixed(1)}h`

export function summaryText(payload: TruthPayload, label: string): string {
  const rows = Object.entries(payload.projects ?? {})
    .filter(([, hours]) => hours > 0)
    .sort(([, a], [, b]) => b - a)
  if (rows.length === 0) return `gittan ${label}: no attributed hours yet.`
  const total = payload.totals?.hours_estimated ?? 0
  const width = Math.max(...rows.map(([name]) => name.length))
  const lines = rows.map(([name, hours]) => `  ${name.padEnd(width)}  ${formatHours(hours)}`)
  return [`gittan ${label}: ${formatHours(total)} estimated`, ...lines].join('\n')
}
