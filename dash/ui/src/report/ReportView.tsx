import { PassBar } from "@/components/pass-bar"
import { Badge } from "@/components/ui/badge"
import { Card, CardTitle } from "@/components/ui/card"
import { fmtDur, metricValue } from "@/lib/fmt"
import { t } from "@/lib/i18n"
import { statusVariant } from "@/lib/status"

import {
  caseAnchor,
  displayTime,
  errorGroups,
  formatSize,
  operationPassed,
  pretty,
  stepLabel,
  successRate,
} from "./logic"
import type { ReportCase, ReportOperation, ReportPayload } from "./types"

export function ReportView({
  report,
  artifactHref,
}: {
  report: ReportPayload
  artifactHref?: (path: string) => string
}) {
  const cases = report.cases || []
  const cleanup = report.cleanup || {}
  const errors = errorGroups(cases)
  const rate = successRate(report)
  const passed = Number(report.passed || 0)
  const failed = Number(report.failed || 0)
  const skipped = Number(report.skipped || 0)
  const interrupted = Number(report.interrupted || 0)
  const status = report.status || "unknown"
  const statusLabel =
    { pass: t("passed"), fail: t("failed"), skip: t("skipped"), interrupted: t("interrupted") }[status] || status
  const cleanupLabel =
    { pass: t("passed"), fail: t("failed"), unknown: "—" }[cleanup.status || "unknown"] || cleanup.status || "—"
  const planned = report.duration || (report.mode === "soak" ? "—" : t("once"))
  const queries = (report.queries || []).join(" ")
  const top = errors[0]
  let conclusion = top
    ? `主要问题：${top.message}，共出现 ${top.count} 次。`
    : "所有已完成轮次均未发现失败。"
  if (cleanup.status === "fail") conclusion += ` 有 ${cleanup.failed || 0} 个清理阶段失败。`
  else if (cleanup.status === "pass") conclusion += " 已记录的资源清理均成功。"

  const openKeys = new Set(
    errors.map((row) => `${row.representative_case}:${row.representative_iteration}`),
  )

  function href(path: string): string {
    return artifactHref ? artifactHref(path) : encodeURI(path)
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-lg font-medium">{t("reportTitle")}</h1>
            <Badge variant={statusVariant(status)}>{statusLabel}</Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {displayTime(report.started)} · {report.mode || "—"} · {report.env || "—"}
            {queries ? ` · ${queries}` : ""}
          </p>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label={t("env")} value={String(report.env || "—")} />
        <Stat label={t("mode")} value={String(report.mode || "—")} />
        <Stat label={t("elapsed")} value={fmtDur(report.elapsed_s)} />
        <Stat label={t("duration")} value={String(planned)} />
        <Stat label={t("successRate")} value={rate == null ? "—" : `${rate.toFixed(1)}%`} />
        <Stat label={t("resource")} value={String(cleanupLabel)} />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label={t("passed")} value={String(passed)} />
        <Stat label={t("failed")} value={String(failed)} />
        <Stat label={t("skipped")} value={String(skipped)} />
        <Stat label={t("interrupted")} value={String(interrupted)} />
      </div>

      <PassBar passed={passed} failed={failed} skipped={skipped + interrupted} />

      <Card className="space-y-2">
        <CardTitle>{t("conclusion")}</CardTitle>
        <p className="text-sm">{conclusion}</p>
      </Card>

      <Card className="space-y-3">
        <CardTitle>{t("issues")}</CardTitle>
        {errors.length ? (
          <table className="w-full text-left text-sm">
            <thead className="text-muted-foreground">
              <tr>
                <th className="py-1 font-medium">{t("errorFingerprint")}</th>
                <th className="py-1 font-medium">{t("cases")}</th>
                <th className="py-1 font-medium">#</th>
                <th className="py-1 font-medium">{t("rounds")}</th>
                <th className="py-1 font-medium" />
              </tr>
            </thead>
            <tbody>
              {errors.map((row) => (
                <tr key={row.message} className="border-t align-top">
                  <td className="py-2 text-destructive">{row.message}</td>
                  <td className="py-2">
                    {row.cases.map((id) => (
                      <code key={id} className="mr-2">
                        {id}
                      </code>
                    ))}
                  </td>
                  <td className="py-2 tabular-nums">{row.count}</td>
                  <td className="py-2">{row.iterations.join(", ")}</td>
                  <td className="py-2">
                    <a
                      className="text-sm hover:underline"
                      href={`#${caseAnchor(row.representative_case, row.representative_iteration)}`}
                    >
                      {t("view")}
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-muted-foreground">{t("emptyIssues")}</p>
        )}
      </Card>

      <Card className="space-y-3">
        <CardTitle>{t("roundsDetail")}</CardTitle>
        <div className="space-y-2">
          {cases.map((item) => (
            <CaseBlock
              key={`${item.id}-${item.iteration}`}
              item={item}
              open={openKeys.has(`${item.id || ""}:${item.iteration || 1}`) || item.status === "interrupted"}
              href={href}
            />
          ))}
        </div>
      </Card>

      <Card className="space-y-3">
        <CardTitle>{t("resource")}</CardTitle>
        <div className="grid grid-cols-3 gap-2 text-sm">
          <div>
            <div className="text-xs text-muted-foreground">{t("registered")}</div>
            <div className="text-lg font-medium">{String(report.resource_audit?.registered ?? 0)}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">{t("cleanupOk")}</div>
            <div className="text-lg font-medium">{String(cleanup.completed ?? 0)}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">{t("cleanupFail")}</div>
            <div className="text-lg font-medium">{String(cleanup.failed ?? 0)}</div>
          </div>
        </div>
      </Card>

      <Card className="space-y-3">
        <CardTitle>{t("artifacts")}</CardTitle>
        {(report.artifacts || []).length ? (
          <table className="w-full text-left text-sm">
            <thead className="text-muted-foreground">
              <tr>
                <th className="py-1 font-medium">{t("file")}</th>
                <th className="py-1 font-medium">{t("size")}</th>
              </tr>
            </thead>
            <tbody>
              {(report.artifacts || []).map((row) => (
                <tr key={row.path} className="border-t">
                  <td className="py-2">
                    <a className="hover:underline" href={href(row.path)} target="_blank" rel="noreferrer">
                      {row.path}
                    </a>
                  </td>
                  <td className="py-2 tabular-nums text-muted-foreground">{formatSize(row.bytes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="text-sm text-muted-foreground">{t("noArtifacts")}</p>
        )}
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

function CaseBlock({
  item,
  open,
  href,
}: {
  item: ReportCase
  open: boolean
  href: (path: string) => string
}) {
  const iteration = Number(item.iteration || 1)
  const anchor = caseAnchor(String(item.id || ""), iteration)
  return (
    <details
      id={anchor}
      className="scroll-mt-3 overflow-hidden rounded-xl bg-card ring-1 ring-foreground/10"
      open={open}
    >
      <summary className="cursor-pointer px-4 py-3 text-sm">
        <Badge variant={statusVariant(String(item.status || ""))}>{item.status}</Badge>{" "}
        <span className="font-medium">{item.id}</span>
        <span className="text-muted-foreground">
          {" "}
          · {t("roundN", { n: iteration })} · {fmtDur(item.elapsed_s)}
        </span>
      </summary>
      <div className="space-y-3 border-t px-4 py-3 text-sm">
        {item.error ? <p className="rounded-lg bg-destructive/10 p-3 text-destructive whitespace-pre-wrap">{item.error}</p> : null}
        {Object.keys(item.metrics || {}).length ? (
          <div className="flex flex-wrap gap-2">
            {Object.entries(item.metrics || {}).map(([key, value]) => (
              <span key={key} className="rounded-full bg-muted px-2 py-0.5 text-xs">
                {key}={metricValue(value, item.metric_meta?.[key]?.unit)}
              </span>
            ))}
          </div>
        ) : (
          <p className="text-muted-foreground">{t("noMetrics")}</p>
        )}
        {(item.steps || []).length ? (
          <table className="w-full text-left text-sm">
            <thead className="text-muted-foreground">
              <tr>
                <th className="py-1 font-medium">{t("stage")}</th>
                <th className="py-1 font-medium">{t("status")}</th>
                <th className="py-1 font-medium">{t("elapsed")}</th>
                <th className="py-1 font-medium">{t("note")}</th>
              </tr>
            </thead>
            <tbody>
              {(item.steps || []).map((step) => (
                <tr key={step.name} className="border-t align-top">
                  <td className="py-2">{step.name}</td>
                  <td className="py-2">
                    <Badge variant={statusVariant(String(step.status || ""))}>
                      {stepLabel(step.status, item.status)}
                    </Badge>
                  </td>
                  <td className="py-2 tabular-nums">{step.elapsed_s != null ? fmtDur(step.elapsed_s) : "—"}</td>
                  <td className="py-2">
                    {step.detail || ""}
                    {(step.status === "failed" || step.status === "running") &&
                    (item.status === "fail" || item.status === "interrupted")
                      ? (step.operations || []).map((operation, index) => (
                          <OperationBlock key={`${step.name}-${index}`} operation={operation} href={href} />
                        ))
                      : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
        {(item.notes || []).length ? (
          <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
            {(item.notes || []).map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        ) : null}
      </div>
    </details>
  )
}

function OperationBlock({
  operation,
  href,
}: {
  operation: ReportOperation
  href: (path: string) => string
}) {
  const passed = operationPassed(operation)
  return (
    <details className="mt-2 rounded-md border border-border bg-background p-2" open={!passed}>
      <summary className="cursor-pointer text-xs font-medium">
        <Badge variant={passed ? "pass" : "fail"}>{passed ? t("passed") : t("failed")}</Badge>{" "}
        {operation.label || operation.type || "op"}
      </summary>
      <pre className="mt-2 max-h-64 overflow-auto text-xs text-muted-foreground whitespace-pre-wrap">
        {t("expected")}: {pretty(operation.expected)}
        {"\n"}
        {t("actual")}: {pretty(operation.actual)}
      </pre>
      {(operation.artifacts || []).length ? (
        <div className="mt-2 space-x-2 text-xs">
          {(operation.artifacts || []).map((path) => (
            <a key={path} className="hover:underline" href={href(path)} target="_blank" rel="noreferrer">
              {path.split("/").pop()}
            </a>
          ))}
        </div>
      ) : null}
    </details>
  )
}
