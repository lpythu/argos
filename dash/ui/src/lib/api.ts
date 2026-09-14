export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }
  const resp = await fetch(path, { ...init, headers, credentials: "same-origin" })
  if (resp.status === 401) {
    throw new Error("unauthorized")
  }
  if (!resp.ok) {
    throw new Error(await resp.text())
  }
  return (await resp.json()) as T
}

export type Me = { login: string; name: string }

export type CaseRow = {
  id: string
  slug: string
  title: string
  group: string
  pack: string
  iteration: number
  status: string
  error: string
  elapsed_s: number
  steps: Step[]
  metrics: Record<string, unknown>
}

export type Operation = {
  label?: string
  type?: string
  operation?: unknown
  expected?: unknown
  actual?: unknown
  artifacts?: string[]
  elapsed_s?: number
}

export type Step = {
  name: string
  status: string
  detail: string
  started_at?: string
  ended_at?: string
  elapsed_s?: number | null
  operations?: Operation[]
}

export type CaseSummary = {
  id: string
  title: string
  pack: string
  group: string
  latest_status: string
  latest_error: string
  elapsed_s: number
  total: number
  passed: number
  failed: number
  skipped: number
  interrupted: number
  running: number
  success_rate: number | null
  iterations: { iteration: number; status: string }[]
  metrics: Record<string, unknown>
  metric_meta: Record<string, { unit?: string }>
  distributions: Record<string, { p95?: number; avg?: number; max?: number; unit?: string }>
  thresholds: { name: string; passed: boolean; actual: unknown; target: unknown; operator: string; unit?: string }[]
  steps: Step[]
}

export type CatalogCase = {
  id: string
  title: string
  pack: string
  group: string
  slug: string
  status: string
  env: string
  mode: string
  run_id: string
  run_slug: string
  seen_at: string
  typical_s: number
  mutex: string
  resources: string[]
  prefer_after: string[]
  modes: string[]
  tags: string[]
}

export type Artifact = { path: string; size: number }

export type Run = {
  id: string
  url: string
  stamp: string
  slug: string
  mode: string
  env: string
  status: string
  runner: string
  queries: string[]
  packs: string[]
  summary: { passed?: number; failed?: number; skipped?: number; elapsed_s?: number }
  created_at: string
  finished_at: string
  elapsed_s: number
  passed: number
  failed: number
  skipped: number
  interrupted: number
  cases: CaseRow[]
  case_summaries?: CaseSummary[]
  metric_series?: Record<string, Record<string, { iter: number; value: number }[]>>
  issues?: { fingerprint: string; message: string; count: number; cases: string[]; iterations: number[] }[]
  resource_audit?: Record<string, unknown>
  has_report?: boolean
  files?: Artifact[]
}

export type Comment = {
  id: string
  case_id: string
  body: string
  created_at: string
  author: { login: string; name: string }
}

export type OverviewIssue = {
  fingerprint: string
  message: string
  count: number
  cases: string[]
  envs: string[]
  first: string
  last: string
  latest_run: string
  latest_slug: string
  open: boolean
  max_streak: number
}

export type LiveRun = {
  id: string
  slug: string
  env: string
  mode: string
  status: string
  runner: string
  created_at: string
  passed: number
  failed: number
  skipped: number
  current: { case_id?: string; status?: string; iteration?: number; step?: string }
}

export type Overview = {
  generated_at: string
  hours: number
  env: string
  totals: {
    runs: number
    passed: number
    failed: number
    skipped: number
    interrupted: number
    success_rate: number | null
  }
  coverage: string[]
  coverage_total: number
  open_issues: number
  consecutive_failure_cases: number
  cleanup_failures: number
  issues: OverviewIssue[]
  live: LiveRun[]
}

export type Catalog = {
  cases: CatalogCase[]
  packs: string[]
  groups: string[]
  envs: string[]
}

export type EventRow = Record<string, unknown>
