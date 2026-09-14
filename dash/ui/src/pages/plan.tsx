import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"

import { Field } from "@/components/field"
import { Button } from "@/components/ui/button"
import { Card, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { api, type Catalog, type CatalogCase } from "@/lib/api"
import { copyText, fmtDur } from "@/lib/fmt"
import { t } from "@/lib/i18n"
import { buildCommand, clearPlan, togglePlan, usePlanIds } from "@/lib/plan"

function planHints(selected: CatalogCase[]) {
  const groups = new Map<string, string[]>()
  for (const item of selected) {
    const keys = [...new Set([item.mutex, ...(item.resources || [])].filter(Boolean))]
    for (const key of keys) {
      groups.set(key, [...(groups.get(key) || []), item.id])
    }
  }
  return {
    typical: selected.reduce((sum, item) => sum + (item.typical_s || 0), 0),
    conflicts: [...groups.entries()].filter(([, ids]) => new Set(ids).size > 1),
    after: selected.flatMap((item) =>
      (item.prefer_after || [])
        .filter((id) => selected.some((row) => row.id === id))
        .map((id) => `${id} → ${item.id}`),
    ),
  }
}

export function PlanPage() {
  const ids = usePlanIds()
  const [catalog, setCatalog] = useState<Catalog>({ cases: [], packs: [], groups: [], envs: [] })
  const [env, setEnv] = useState("office")
  const [soak, setSoak] = useState(false)
  const [duration, setDuration] = useState("8h")
  const [pause, setPause] = useState("2m")
  const [failFast, setFailFast] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    api<Catalog>("/api/catalog")
      .then((data) => {
        setCatalog(data)
        if (data.envs.length && !data.envs.includes(env)) setEnv(data.envs[0] || "office")
      })
      .catch(() => undefined)
  }, [])

  const selected = catalog.cases.filter((item) => ids.includes(item.id))
  const hints = useMemo(() => planHints(selected), [selected])
  const command = buildCommand({ ids, env, soak, duration, pause, failFast })

  async function copy() {
    await copyText(command)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-medium">{t("plan")}</h1>
        <p className="text-sm text-muted-foreground">{t("planHint")}</p>
      </div>
      <Card className="space-y-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="space-y-1 text-sm">
            <div>{t("mode")}</div>
            <Field value={soak ? "soak" : "once"} onChange={(event) => setSoak(event.target.value === "soak")}>
              <option value="once">{t("once")}</option>
              <option value="soak">{t("soak")}</option>
            </Field>
          </label>
          <label className="space-y-1 text-sm">
            <div>{t("env")}</div>
            <Field value={env} onChange={(event) => setEnv(event.target.value)}>
              {["office", "hk", ...catalog.envs.filter((item) => !["office", "hk"].includes(item))].map((item) => (
                <option key={item}>{item}</option>
              ))}
            </Field>
          </label>
          <label className="space-y-1 text-sm">
            <div>{t("duration")}</div>
            <Input className="w-24" value={duration} disabled={!soak} onChange={(event) => setDuration(event.target.value)} />
          </label>
          <label className="space-y-1 text-sm">
            <div>{t("pause")}</div>
            <Input className="w-24" value={pause} disabled={!soak} onChange={(event) => setPause(event.target.value)} />
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={failFast} onChange={(event) => setFailFast(event.target.checked)} />
            {t("failFast")}
          </label>
          <Button disabled={!ids.length} onClick={() => void copy()}>
            {copied ? t("copied") : t("copyCmd")}
          </Button>
        </div>
        <pre className="overflow-x-auto rounded-lg bg-muted/60 p-3 text-xs">{ids.length ? command : t("emptyPlan")}</pre>
        {selected.length ? (
          <div className="space-y-1 text-sm">
            <div>
              {t("estimated")}: {fmtDur(hints.typical)}
            </div>
            {hints.conflicts.map(([key, items]) => (
              <div key={key} className="text-destructive">
                {t("conflict")}: {key} · {items.join(", ")}
              </div>
            ))}
            {hints.after.length ? (
              <div className="text-muted-foreground">
                {t("preferAfter")}: {hints.after.join(" · ")}
              </div>
            ) : null}
          </div>
        ) : null}
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <CardTitle>
              {t("selected")} {selected.length}
            </CardTitle>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={clearPlan}>
                {t("clear")}
              </Button>
              <Link to="/cases" className="self-center text-sm text-muted-foreground hover:underline">
                {t("goCases")}
              </Link>
            </div>
          </div>
          {selected.length ? (
            <ul className="space-y-2">
              {selected.map((item) => (
                <li key={item.id} className="flex items-center justify-between gap-2">
                  <div>
                    <code>{item.id}</code>
                    <div className="text-xs text-muted-foreground">
                      {item.title}
                      {item.mutex ? ` · ${item.mutex}` : ""}
                      {item.typical_s ? ` · ${fmtDur(item.typical_s)}` : ""}
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => togglePlan(item.id)}>
                    {t("clear")}
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">{t("emptyPlan")}</p>
          )}
        </Card>
        <Card className="space-y-3">
          <CardTitle>{t("cases")}</CardTitle>
          <ul className="max-h-96 space-y-2 overflow-auto">
            {catalog.cases.map((item) => (
              <li key={item.id}>
                <button type="button" className="w-full text-left hover:underline" onClick={() => togglePlan(item.id)}>
                  <code>{item.id}</code>
                  <div className="text-xs text-muted-foreground">
                    {item.pack} · {item.title}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  )
}
