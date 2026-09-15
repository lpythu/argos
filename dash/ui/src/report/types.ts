export type ReportStep = {
  name?: string
  status?: string
  elapsed_s?: number
  detail?: string
  operations?: ReportOperation[]
}

export type ReportOperation = {
  type?: string
  label?: string
  operation?: unknown
  expected?: unknown
  actual?: unknown
  artifacts?: string[]
  elapsed_s?: number
}

export type ReportCase = {
  id?: string
  slug?: string
  iteration?: number
  title?: string
  status?: string
  elapsed_s?: number
  error?: string
  metrics?: Record<string, unknown>
  metric_meta?: Record<string, { unit?: string }>
  steps?: ReportStep[]
  notes?: string[]
  distributions?: Record<string, { p95?: unknown; avg?: unknown; max?: unknown; unit?: string }>
  thresholds?: { name: string; passed: boolean; actual: unknown; target: unknown; operator: string; unit?: string }[]
}

export type ReportArtifact = {
  path: string
  bytes: number
}

export type ReportCleanup = {
  status?: string
  completed?: number
  failed?: number
}

export type ReportPayload = {
  status?: string
  env?: string
  mode?: string
  started?: string
  finished_at?: string
  elapsed_s?: number
  duration?: string | null
  queries?: string[]
  packs?: string[]
  passed?: number
  failed?: number
  skipped?: number
  interrupted?: number
  cases?: ReportCase[]
  cleanup?: ReportCleanup
  artifacts?: ReportArtifact[]
  resource_audit?: {
    registered?: number
    owned?: unknown[]
  }
}

export type ErrorGroup = {
  message: string
  count: number
  cases: string[]
  iterations: number[]
  representative_case: string
  representative_iteration: number
}
