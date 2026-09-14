import { useEffect, useState } from "react"
import { Link } from "react-router-dom"

import { PassBar } from "@/components/pass-bar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardTitle } from "@/components/ui/card"
import { Field } from "@/components/field"
import { api, type Overview, type Run } from "@/lib/api"
import { fmtWhen } from "@/lib/fmt"
import { t } from "@/lib/i18n"
import { statusVariant } from "@/lib/status"

const HOURS = [
  { value: 24, label: t("hours24") },
  { value: 168, label: t("hours7d") },
  { value: 720, label: t("hours30d") },
]

export function HomePage() {
  const [hours, setHours] = useState(24)
  const [env, setEnv] = useState("all")
  const [envs, setEnvs] = useState<string[]>([])
  const [overview, setOverview] = useState<Overview | null>(null)
  const [recent, setRecent] = useState<Run[]>([])

  async function load(nextEnv = env, nextHours = hours) {
    const query = new URLSearchParams({ hours: String(nextHours) })
    if (nextEnv !== "all") query.set("env", nextEnv)
    try {
      const [next, runs, meta] = await Promise.all([
        api<Overview>(`/api/overview?${query}`),
        api<{ runs: Run[] }>(`/api/runs?${query}`),
        api<{ envs: string[] }>("/api/envs"),
      ])
      setOverview(next)
      setRecent(runs.runs.slice(0, 8))
      setEnvs(meta.envs)
    } catch {
      setOverview((current) => current)
    }
  }

  useEffect(() => {
    void load()
    const timer = window.setInterval(() => void load(), 4000)
    return () => window.clearInterval(timer)
  }, [env, hours])

  if (!overview) return null

  const totals = overview.totals
  const openIssues = overview.issues.filter((item) => item.open)
  const coverageRate = overview.coverage_total
    ? Math.round((1000 * overview.coverage.length) / overview.coverage_total) / 10
    : 0
  const health =
    overview.cleanup_failures > 0 || overview.consecutive_failure_cases > 0
      ? "fail"
      : openIssues.length
        ? "warn"
        : overview.live.length
          ? "live"
          : "idle"
  const headline =
    health === "fail"
      ? t("healthFail")
      : health === "warn"
        ? t("healthWarn")
        : health === "live"
          ? t("healthLive")
          : t("healthIdle")
  const banner =
    health === "fail"
      ? "border-destructive/40 bg-destructive/5"
      : health === "warn"
        ? "border-amber-400/50 bg-amber-50 dark:bg-amber-950/20"
        : health === "live"
          ? "border-emerald-400/50 bg-emerald-50 dark:bg-emerald-950/20"
          : "border-border"

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-medium">{t("home")}</h1>
          <p className="text-sm text-muted-foreground">{fmtWhen(overview.generated_at)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Field
            value={env}
            onChange={(event) => {
              setEnv(event.target.value)
            }}
          >
            <option value="all">{t("allEnvs")}</option>
            {envs.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </Field>
          <Field
            value={String(hours)}
            onChange={(event) => {
              setHours(Number(event.target.value))
            }}
          >
            {HOURS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </Field>
          <Button variant="outline" onClick={() => void load()}>
            {t("refresh")}
          </Button>
        </div>
      </div>

      <Card className={`flex flex-wrap items-center gap-6 ${banner}`}>
        <div className="min-w-56 flex-1">
          <div className="font-medium">{headline}</div>
          <p className="mt-1 text-sm text-muted-foreground">
            {openIssues[0]
              ? `${openIssues[0].cases.join("、")} · ${openIssues[0].message}`
              : overview.live.length
                ? `${overview.live.length} ${t("liveRuns")}`
                : t("emptyIssues")}
          </p>
        </div>
        <div>
          <div className="text-2xl font-semibold">{totals.success_rate == null ? "—" : `${totals.success_rate}%`}</div>
          <div className="text-xs text-muted-foreground">{t("successRate")}</div>
        </div>
        <div>
          <div className="text-2xl font-semibold">{openIssues.length}</div>
          <div className="text-xs text-muted-foreground">{t("openIssues")}</div>
        </div>
        <div>
          <div className="text-2xl font-semibold">{overview.cleanup_failures}</div>
          <div className="text-xs text-muted-foreground">{t("cleanup")}</div>
        </div>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Kpi
          label={t("successRate")}
          value={totals.success_rate == null ? "—" : `${totals.success_rate}%`}
          hint={`${totals.passed} pass / ${totals.failed} fail`}
        />
        <Kpi
          label={t("openIssues")}
          value={String(openIssues.length)}
          hint={`${overview.consecutive_failure_cases} consecutive`}
        />
        <Kpi label={t("liveRuns")} value={String(overview.live.length)} hint={t("liveRuns")} />
        <Kpi
          label={t("coverage")}
          value={`${coverageRate}%`}
          hint={`${overview.coverage.length} / ${overview.coverage_total}`}
        />
        <Kpi label={t("cleanup")} value={String(overview.cleanup_failures)} hint={t("cleanup")} />
        <Kpi
          label={t("rounds")}
          value={String(totals.passed + totals.failed + totals.skipped)}
          hint={`${totals.skipped} skip`}
        />
      </div>

      <Card className="space-y-3">
        <div className="flex items-center justify-between">
          <CardTitle>{t("liveRuns")}</CardTitle>
          <Link to="/plan" className="text-sm text-muted-foreground hover:underline">
            {t("goPlan")}
          </Link>
        </div>
        {overview.live.length ? (
          <table className="w-full text-left text-sm">
            <thead className="text-muted-foreground">
              <tr>
                <th className="py-1 font-medium">{t("runs")}</th>
                <th className="py-1 font-medium">{t("env")}</th>
                <th className="py-1 font-medium">{t("status")}</th>
                <th className="py-1 font-medium">{t("currentCase")}</th>
                <th className="py-1 font-medium">{t("cases")}</th>
              </tr>
            </thead>
            <tbody>
              {overview.live.map((row) => (
                <tr key={row.id} className="border-t">
                  <td className="py-2">
                    <Link to={`/runs/${row.id}`} className="hover:underline">
                      {row.slug}
                    </Link>
                    <div className="text-xs text-muted-foreground">{fmtWhen(row.created_at)}</div>
                  </td>
                  <td>
                    {row.env || "—"} · {row.mode}
                  </td>
                  <td>
                    <Badge variant={statusVariant(row.status)}>{row.status}</Badge>
                  </td>
                  <td>
                    <code>{row.current.case_id || "—"}</code>
                    <div className="text-xs text-muted-foreground">{row.current.step || ""}</div>
                  </td>
                  <td>
                    {row.passed} / {row.failed} / {row.skipped}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-muted-foreground">{t("emptyLive")}</p>
        )}
      </Card>

      <Card className="space-y-3">
        <CardTitle>{t("issues")}</CardTitle>
        {openIssues.length ? (
          <table className="w-full text-left text-sm">
            <thead className="text-muted-foreground">
              <tr>
                <th className="py-1 font-medium">{t("issues")}</th>
                <th className="py-1 font-medium">{t("cases")}</th>
                <th className="py-1 font-medium">n</th>
                <th className="py-1 font-medium">{t("lastRun")}</th>
              </tr>
            </thead>
            <tbody>
              {openIssues.map((issue) => (
                <tr key={issue.fingerprint} className="border-t align-top">
                  <td className="py-2">
                    <Badge variant="fail">{t("openIssues")}</Badge>
                    <p className="mt-1">{issue.message}</p>
                  </td>
                  <td>
                    <code>{issue.cases.join("、")}</code>
                    <div className="text-xs text-muted-foreground">{issue.envs.join("、")}</div>
                  </td>
                  <td>
                    {issue.count}
                    {issue.max_streak >= 2 ? ` · ×${issue.max_streak}` : ""}
                  </td>
                  <td>
                    <Link to={`/runs/${issue.latest_run}`} className="hover:underline">
                      {issue.latest_slug}
                    </Link>
                    <div className="text-xs text-muted-foreground">{fmtWhen(issue.last)}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-muted-foreground">{t("emptyIssues")}</p>
        )}
      </Card>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-medium">{t("recentRuns")}</h2>
          <Link to="/runs" className="text-sm text-muted-foreground hover:underline">
            {t("viewAll")}
          </Link>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          {recent.map((run) => (
            <Link key={run.id} to={`/runs/${run.id}`}>
              <Card className="space-y-2 hover:bg-muted/40">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{run.slug || run.id.slice(0, 8)}</span>
                  <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  {fmtWhen(run.created_at)} · {run.env || "—"} · {run.mode}
                </p>
                <PassBar passed={run.passed} failed={run.failed} skipped={run.skipped} />
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}

function Kpi({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <Card>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="text-2xl font-semibold">{value}</div>
      <div className="text-xs text-muted-foreground">{hint}</div>
    </Card>
  )
}
