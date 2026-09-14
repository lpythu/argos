import { type FormEvent, useEffect, useMemo, useState } from "react"
import { useParams } from "react-router-dom"

import { Field } from "@/components/field"
import { IterStrip } from "@/components/iter-strip"
import { PassBar } from "@/components/pass-bar"
import { Spark } from "@/components/spark"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { api, type Comment, type EventRow, type Run } from "@/lib/api"
import { fmtDur, fmtWhen, metricValue } from "@/lib/fmt"
import { t } from "@/lib/i18n"
import { statusVariant } from "@/lib/status"

function formatEvent(row: EventRow): string {
  const parts = [
    row.ended_at || row.started_at || row.at || "",
    row.iteration ? `#${row.iteration}` : "",
    row.type || "",
    row.id || "",
    row.message || row.name || "",
    row.status || "",
    row.detail || "",
  ]
  return parts.map((item) => String(item)).filter(Boolean).join("  ")
}

export function RunDetailPage() {
  const { id } = useParams()
  const [run, setRun] = useState<Run | null>(null)
  const [comments, setComments] = useState<Comment[]>([])
  const [body, setBody] = useState("")
  const [events, setEvents] = useState<EventRow[]>([])
  const [eventTotal, setEventTotal] = useState(0)
  const [caseId, setCaseId] = useState("")
  const [metric, setMetric] = useState("")

  async function refresh() {
    if (!id) return
    const [next, note, log] = await Promise.all([
      api<Run>(`/api/runs/${id}`),
      api<{ comments: Comment[] }>(`/api/runs/${id}/comments`),
      api<{ events: EventRow[]; total: number }>(`/api/runs/${id}/events?limit=80`),
    ])
    setRun(next)
    setComments(note.comments)
    setEvents(log.events)
    setEventTotal(log.total)
    const first = next.case_summaries?.[0]?.id || next.cases[0]?.id || ""
    setCaseId((current) => current || first)
  }

  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => void refresh(), 2000)
    return () => window.clearInterval(timer)
  }, [id])

  const summaries = run?.case_summaries || []
  const selected = summaries.find((item) => item.id === caseId) || summaries[0]
  const seriesMap = (run?.metric_series || {})[selected?.id || ""] || {}
  const metricKeys = Object.keys(seriesMap)
  const activeMetric = metricKeys.includes(metric) ? metric : metricKeys[0] || ""
  const series = useMemo(
    () => (activeMetric ? [...(seriesMap[activeMetric] || [])].sort((a, b) => a.iter - b.iter) : []),
    [activeMetric, seriesMap],
  )
  const audit = run?.resource_audit || {}

  async function onComment(event: FormEvent) {
    event.preventDefault()
    if (!id || !body.trim()) return
    await api(`/api/runs/${id}/comments`, {
      method: "POST",
      body: JSON.stringify({ body, case_id: selected?.id || "" }),
    })
    setBody("")
    await refresh()
  }

  if (!run) return null

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-lg font-medium">{run.slug || run.id}</h1>
            <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {fmtWhen(run.created_at)} · {run.mode} · {run.env || "—"} · {t("runner")} {run.runner || "—"}
            {run.queries?.length ? ` · ${run.queries.join(" ")}` : ""}
          </p>
        </div>
        {run.has_report ? (
          <a
            className="inline-flex h-8 items-center rounded-lg border border-border px-2.5 text-sm hover:bg-muted"
            href={`/api/runs/${run.id}/report`}
            target="_blank"
            rel="noreferrer"
          >
            {t("report")}
          </a>
        ) : null}
      </div>

      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label={t("cases")} value={String(summaries.length || run.cases.length)} />
        <Stat label={t("passed")} value={String(run.passed)} />
        <Stat label={t("failed")} value={String(run.failed)} />
        <Stat label={t("skipped")} value={String(run.skipped)} />
        <Stat label={t("interrupted")} value={String(run.interrupted)} />
        <Stat label={t("elapsed")} value={fmtDur(run.elapsed_s)} />
      </div>
      <PassBar passed={run.passed} failed={run.failed} skipped={run.skipped + run.interrupted} />

      <Card className="space-y-3">
        <CardTitle>{t("caseOverview")}</CardTitle>
        <table className="w-full text-left text-sm">
          <thead className="text-muted-foreground">
            <tr>
              <th className="py-1 font-medium">{t("cases")}</th>
              <th className="py-1 font-medium">{t("lastStatus")}</th>
              <th className="py-1 font-medium">P/F</th>
              <th className="py-1 font-medium">{t("elapsed")}</th>
              <th className="py-1 font-medium">{t("rounds")}</th>
            </tr>
          </thead>
          <tbody>
            {summaries.map((item) => (
              <tr
                key={item.id}
                className={`cursor-pointer border-t ${item.id === selected?.id ? "bg-muted/40" : ""}`}
                onClick={() => {
                  setCaseId(item.id)
                  setMetric("")
                }}
              >
                <td className="py-2">
                  <code>{item.id}</code>
                  <div className="text-xs text-muted-foreground">{item.title}</div>
                </td>
                <td>
                  <Badge variant={statusVariant(item.latest_status)}>{item.latest_status}</Badge>
                </td>
                <td>
                  {item.passed} / {item.failed}
                  {item.success_rate != null ? ` · ${item.success_rate}%` : ""}
                </td>
                <td>{fmtDur(item.elapsed_s)}</td>
                <td>
                  <IterStrip items={item.iterations} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="space-y-3">
          <div className="flex items-center justify-between gap-2">
            <CardTitle>{t("currentCase")}</CardTitle>
            {summaries.length ? (
              <Field
                value={selected?.id || ""}
                onChange={(event) => {
                  setCaseId(event.target.value)
                  setMetric("")
                }}
              >
                {summaries.map((item) => (
                  <option key={item.id}>{item.id}</option>
                ))}
              </Field>
            ) : null}
          </div>
          {selected ? (
            <>
              <div className="flex items-center gap-2 text-sm">
                <Badge variant={statusVariant(selected.latest_status)}>{selected.latest_status}</Badge>
                <span>
                  {selected.total} · {fmtDur(selected.elapsed_s)}
                </span>
              </div>
              <IterStrip items={selected.iterations} />
              {selected.latest_error ? <p className="text-sm text-destructive">{selected.latest_error}</p> : null}
              {selected.steps?.length ? (
                <ul className="space-y-1 text-sm">
                  {selected.steps.map((step) => (
                    <li key={step.name}>
                      <Badge variant={statusVariant(step.status)}>{step.status}</Badge> {step.name}
                      {step.detail ? <span className="text-muted-foreground"> · {step.detail}</span> : null}
                    </li>
                  ))}
                </ul>
              ) : null}
              <h3 className="text-sm font-medium">{t("metrics")}</h3>
              {Object.keys(selected.metrics || {}).length ? (
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(selected.metrics).map(([key, value]) => (
                    <div key={key} className="rounded-lg bg-muted/50 p-2">
                      <div className="text-xs text-muted-foreground">{key}</div>
                      <div className="font-medium">{metricValue(value, selected.metric_meta?.[key]?.unit)}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">{t("noMetrics")}</p>
              )}
              {Object.keys(selected.distributions || {}).length ? (
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(selected.distributions).map(([key, value]) => (
                    <div key={key} className="rounded-lg bg-muted/50 p-2">
                      <div className="text-xs text-muted-foreground">{key} · P95</div>
                      <div className="font-medium">{metricValue(value.p95, value.unit)}</div>
                      <div className="text-xs text-muted-foreground">
                        avg {metricValue(value.avg, value.unit)} · max {metricValue(value.max, value.unit)}
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
              {(selected.thresholds || []).map((item) => (
                <div key={item.name} className="flex items-center gap-2 text-sm">
                  <Badge variant={item.passed ? "pass" : "fail"}>{item.passed ? t("passed") : t("failed")}</Badge>
                  {item.name}: {metricValue(item.actual, item.unit)} {item.operator} {metricValue(item.target, item.unit)}
                </div>
              ))}
              {series.length > 1 ? (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm">{t("metricSeries")}</span>
                    <Field value={activeMetric} onChange={(event) => setMetric(event.target.value)}>
                      {metricKeys.map((key) => (
                        <option key={key}>{key}</option>
                      ))}
                    </Field>
                  </div>
                  <Spark points={series} />
                </div>
              ) : null}
            </>
          ) : (
            <p className="text-sm text-muted-foreground">{t("emptyCases")}</p>
          )}
        </Card>

        <Card className="space-y-3">
          <CardTitle>{t("resource")}</CardTitle>
          <div className="grid grid-cols-3 gap-2 text-sm">
            <div>
              <div className="text-xs text-muted-foreground">registered</div>
              <div className="text-lg font-medium">{String(audit.registered ?? 0)}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">cleanup ok</div>
              <div className="text-lg font-medium">{String(audit.cleanup_completed ?? 0)}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">cleanup fail</div>
              <div className="text-lg font-medium">{String(audit.cleanup_failed ?? 0)}</div>
            </div>
          </div>
          <p className="text-sm text-muted-foreground">{String(audit.cleanup_status || "—")}</p>
          {run.files?.length ? (
            <>
              <h3 className="text-sm font-medium">{t("artifacts")}</h3>
              <ul className="space-y-1 text-sm">
                {run.files.map((file) => (
                  <li key={file.path}>
                    <a className="hover:underline" href={`/api/runs/${run.id}/file?path=${encodeURIComponent(file.path)}`}>
                      {file.path}
                    </a>
                    <span className="text-xs text-muted-foreground"> · {file.size}</span>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </Card>
      </div>

      {run.issues?.length ? (
        <Card className="space-y-3">
          <CardTitle>{t("issues")}</CardTitle>
          <table className="w-full text-left text-sm">
            <tbody>
              {run.issues.map((issue) => (
                <tr key={issue.fingerprint} className="border-t align-top">
                  <td className="py-2 text-destructive">{issue.message}</td>
                  <td>
                    {issue.cases.map((item) => (
                      <code key={item} className="mr-2">
                        {item}
                      </code>
                    ))}
                  </td>
                  <td>{issue.count}</td>
                  <td>{issue.iterations.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      ) : null}

      <Card className="space-y-3">
        <div className="flex items-center justify-between">
          <CardTitle>{t("events")}</CardTitle>
          <span className="text-xs text-muted-foreground">
            {events.length} / {eventTotal}
          </span>
        </div>
        <pre className="max-h-64 overflow-auto text-xs text-muted-foreground">
          {events.map(formatEvent).join("\n")}
        </pre>
      </Card>

      <Card className="space-y-3">
        <CardTitle>{t("comments")}</CardTitle>
        {comments.length ? (
          <ul className="space-y-2">
            {comments.map((row) => (
              <li key={row.id} className="rounded-lg bg-muted/50 p-3">
                <div className="text-xs text-muted-foreground">
                  {row.author.name || row.author.login} · {fmtWhen(row.created_at)}
                  {row.case_id ? ` · ${row.case_id}` : ""}
                </div>
                <p className="mt-1 whitespace-pre-wrap">{row.body}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">{t("emptyComments")}</p>
        )}
        <form className="space-y-2" onSubmit={(e) => void onComment(e)}>
          <Textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder={t("commentPlaceholder")} />
          <Button type="submit">{t("addComment")}</Button>
        </form>
      </Card>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-xl font-semibold">{value}</div>
    </Card>
  )
}
