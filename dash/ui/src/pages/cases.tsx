import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"

import { Field } from "@/components/field"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { api, type Catalog, type CatalogCase } from "@/lib/api"
import { fmtDur } from "@/lib/fmt"
import { t } from "@/lib/i18n"
import { addPlan, togglePlan, usePlanIds } from "@/lib/plan"
import { statusVariant } from "@/lib/status"

export function CasesPage() {
  const [catalog, setCatalog] = useState<Catalog>({ cases: [], packs: [], groups: [], envs: [] })
  const [q, setQ] = useState("")
  const [pack, setPack] = useState("all")
  const [group, setGroup] = useState("all")
  const selected = usePlanIds()

  useEffect(() => {
    api<Catalog>("/api/catalog")
      .then(setCatalog)
      .catch(() => setCatalog({ cases: [], packs: [], groups: [], envs: [] }))
  }, [])

  const visible = useMemo(
    () =>
      catalog.cases.filter((item) => {
        if (pack !== "all" && item.pack !== pack) return false
        if (group !== "all" && item.group !== group) return false
        if (!q.trim()) return true
        const hay = `${item.id} ${item.title} ${item.pack} ${item.group}`.toLowerCase()
        return hay.includes(q.trim().toLowerCase())
      }),
    [catalog.cases, group, pack, q],
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-lg font-medium">{t("cases")}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <Input className="w-56" value={q} onChange={(event) => setQ(event.target.value)} placeholder={t("filter")} />
          <Field value={pack} onChange={(event) => setPack(event.target.value)}>
            <option value="all">{t("pack")}</option>
            {catalog.packs.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </Field>
          <Field value={group} onChange={(event) => setGroup(event.target.value)}>
            <option value="all">{t("group")}</option>
            {catalog.groups.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </Field>
          <Button variant="outline" onClick={() => addPlan(visible.map((item) => item.id))}>
            {t("addVisible")}
          </Button>
          <Link to="/plan" className="text-sm text-muted-foreground hover:underline">
            {t("plan")} ({selected.length})
          </Link>
        </div>
      </div>
      {visible.length ? (
        <div className="overflow-x-auto rounded-xl ring-1 ring-foreground/10">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/50 text-muted-foreground">
              <tr>
                <th className="px-3 py-2 w-8" />
                <th className="px-3 py-2">id</th>
                <th className="px-3 py-2">{t("pack")}</th>
                <th className="px-3 py-2">{t("typical")}</th>
                <th className="px-3 py-2">{t("mutex")}</th>
                <th className="px-3 py-2">{t("lastStatus")}</th>
                <th className="px-3 py-2">{t("lastEnv")}</th>
                <th className="px-3 py-2">{t("lastRun")}</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((item) => (
                <CaseRow key={item.id} item={item} on={selected.includes(item.id)} />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{t("emptyCases")}</p>
      )}
    </div>
  )
}

function CaseRow({ item, on }: { item: CatalogCase; on: boolean }) {
  return (
    <tr className={`border-t ${on ? "bg-muted/40" : ""}`}>
      <td className="px-3 py-2">
        <input type="checkbox" checked={on} onChange={() => togglePlan(item.id)} />
      </td>
      <td className="px-3 py-2">
        <code>{item.id}</code>
        <div className="text-xs text-muted-foreground">{item.title}</div>
      </td>
      <td className="px-3 py-2">
        {item.pack || "—"}
        {item.group ? <div className="text-xs text-muted-foreground">{item.group}</div> : null}
      </td>
      <td className="px-3 py-2">{item.typical_s ? fmtDur(item.typical_s) : "—"}</td>
      <td className="px-3 py-2">{item.mutex || (item.resources || []).join(", ") || "—"}</td>
      <td className="px-3 py-2">
        <Badge variant={statusVariant(item.status)}>{item.status}</Badge>
      </td>
      <td className="px-3 py-2">{item.env || "—"}</td>
      <td className="px-3 py-2">
        <Link to={`/runs/${item.run_id}`} className="hover:underline">
          {item.run_slug || item.run_id.slice(0, 8)}
        </Link>
      </td>
    </tr>
  )
}
