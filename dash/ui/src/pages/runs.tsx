import { useEffect, useState } from "react"
import { Link } from "react-router-dom"

import { Field } from "@/components/field"
import { PassBar } from "@/components/pass-bar"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { api, type Run } from "@/lib/api"
import { fmtDur, fmtWhen } from "@/lib/fmt"
import { t } from "@/lib/i18n"
import { statusVariant } from "@/lib/status"

export function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([])
  const [envs, setEnvs] = useState<string[]>([])
  const [env, setEnv] = useState("all")
  const [status, setStatus] = useState("all")
  const [q, setQ] = useState("")

  async function load() {
    const query = new URLSearchParams()
    if (env !== "all") query.set("env", env)
    if (status !== "all") query.set("status", status)
    if (q.trim()) query.set("q", q.trim())
    const [data, meta] = await Promise.all([
      api<{ runs: Run[] }>(`/api/runs?${query}`),
      api<{ envs: string[] }>("/api/envs"),
    ])
    setRuns(data.runs)
    setEnvs(meta.envs)
  }

  useEffect(() => {
    void load()
    const timer = window.setInterval(() => void load(), 4000)
    return () => window.clearInterval(timer)
  }, [env, status, q])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-lg font-medium">{t("runs")}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <Input className="w-56" value={q} onChange={(event) => setQ(event.target.value)} placeholder={t("filter")} />
          <Field value={env} onChange={(event) => setEnv(event.target.value)}>
            <option value="all">{t("allEnvs")}</option>
            {envs.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </Field>
          <Field value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="all">{t("status")}</option>
            {["running", "pass", "fail", "skip"].map((item) => (
              <option key={item}>{item}</option>
            ))}
          </Field>
        </div>
      </div>
      {runs.length ? (
        <div className="overflow-x-auto rounded-xl ring-1 ring-foreground/10">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/50 text-muted-foreground">
              <tr>
                <th className="px-3 py-2">{t("status")}</th>
                <th className="px-3 py-2">id</th>
                <th className="px-3 py-2">{t("env")}</th>
                <th className="px-3 py-2">{t("pack")}</th>
                <th className="px-3 py-2">P/F/S</th>
                <th className="px-3 py-2">{t("elapsed")}</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id} className="border-t align-top">
                  <td className="px-3 py-2">
                    <Badge variant={statusVariant(run.status)}>{run.status}</Badge>
                  </td>
                  <td className="px-3 py-2">
                    <Link to={`/runs/${run.id}`} className="underline-offset-2 hover:underline">
                      {run.slug || run.id.slice(0, 8)}
                    </Link>
                    <div className="text-xs text-muted-foreground">{fmtWhen(run.created_at)}</div>
                    {run.queries?.length ? (
                      <div className="text-xs text-muted-foreground">{run.queries.join(" ")}</div>
                    ) : null}
                    <div className="mt-1 w-32">
                      <PassBar passed={run.passed} failed={run.failed} skipped={run.skipped} />
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    {run.env || "—"} · {run.mode}
                  </td>
                  <td className="px-3 py-2">{run.packs.join(", ") || "—"}</td>
                  <td className="px-3 py-2 tabular-nums">
                    {run.passed} / {run.failed} / {run.skipped}
                  </td>
                  <td className="px-3 py-2">{fmtDur(run.elapsed_s)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{t("emptyRuns")}</p>
      )}
    </div>
  )
}
