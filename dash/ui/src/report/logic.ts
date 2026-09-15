import type { ErrorGroup, ReportCase, ReportPayload } from "./types"

const UUID_RE = /\b[0-9a-f]{8}-[0-9a-f-]{27,}\b/gi
const HEX_RE = /\b[0-9a-f]{12,}\b/gi
const ARGOS_NAME_RE = /\bargos-[a-z0-9-]*-[0-9a-f]{8}\b/gi

export function fingerprint(error: string): string {
  return error
    .trim()
    .replace(UUID_RE, "<id>")
    .replace(HEX_RE, "<id>")
    .replace(ARGOS_NAME_RE, "<resource>") || "未记录失败原因"
}

export function errorGroups(cases: ReportCase[]): ErrorGroup[] {
  const groups = new Map<string, ErrorGroup & { caseSet: Set<string> }>()
  for (const item of cases) {
    if (item.status !== "fail" && item.status !== "interrupted") continue
    const message = fingerprint(String(item.error || ""))
    const caseId = String(item.id || "")
    const iteration = Number(item.iteration || 1)
    const row = groups.get(message)
    if (!row) {
      groups.set(message, {
        message,
        count: 1,
        cases: [],
        iterations: [iteration],
        representative_case: caseId,
        representative_iteration: iteration,
        caseSet: new Set([caseId]),
      })
      continue
    }
    row.count += 1
    row.caseSet.add(caseId)
    row.iterations.push(iteration)
  }
  return [...groups.values()]
    .map(({ caseSet, ...row }) => ({
      ...row,
      cases: [...caseSet].sort(),
      iterations: [...row.iterations].sort((a, b) => a - b),
    }))
    .sort((a, b) => b.count - a.count)
}

export function successRate(report: ReportPayload): number | null {
  const passed = Number(report.passed || 0)
  const failed = Number(report.failed || 0)
  const completed = passed + failed
  return completed ? (100 * passed) / completed : null
}

export function caseAnchor(caseId: string, iteration: number): string {
  return `case-${`${caseId}-${iteration}`.replace(/[^a-zA-Z0-9_-]+/g, "-").replace(/^-+|-+$/g, "")}`
}

export function formatSize(bytes: number): string {
  let size = bytes
  for (const unit of ["B", "KiB", "MiB", "GiB"] as const) {
    if (size < 1024 || unit === "GiB") {
      return unit === "B" ? `${size} ${unit}` : `${size.toFixed(1)} ${unit}`
    }
    size /= 1024
  }
  return `${bytes} B`
}

export function displayTime(value: unknown): string {
  const text = String(value || "")
  const compact = text.match(/^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})$/)
  if (compact) {
    return `${compact[1]}-${compact[2]}-${compact[3]} ${compact[4]}:${compact[5]}:${compact[6]}`
  }
  const date = new Date(text)
  if (!Number.isNaN(date.getTime())) return date.toLocaleString()
  return text || "—"
}

export function pretty(value: unknown): string {
  if (value == null) return "—"
  if (typeof value === "string") return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

export function operationPassed(operation: {
  type?: string
  expected?: unknown
  actual?: unknown
}): boolean {
  const expected =
    operation.expected && typeof operation.expected === "object" ? (operation.expected as Record<string, unknown>) : {}
  const actual =
    operation.actual && typeof operation.actual === "object" ? (operation.actual as Record<string, unknown>) : {}
  if (operation.type === "command") {
    const wanted = expected.returncode ?? 0
    const received = actual.returncode
    return wanted === "nonzero" ? received !== 0 : received === wanted
  }
  if (operation.type === "http") {
    const wanted = expected.http_status
    const received = actual.http_status
    return Array.isArray(wanted) ? wanted.includes(received) : received === wanted
  }
  return JSON.stringify(expected) === JSON.stringify(actual)
}

export function stepLabel(status: string | undefined, caseStatus: string | undefined): string {
  if (status === "running" && (caseStatus === "fail" || caseStatus === "skip" || caseStatus === "interrupted")) {
    return "未正常结束"
  }
  if (status === "ok") return "成功"
  if (status === "failed") return "失败"
  if (status === "running") return "执行中"
  if (status === "skip") return "跳过"
  return status || "—"
}
