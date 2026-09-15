import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"

import { api } from "@/lib/api"
import { t } from "@/lib/i18n"
import { ReportView } from "@/report/ReportView"
import type { ReportPayload } from "@/report/types"

export function ReportPage() {
  const { id } = useParams()
  const [report, setReport] = useState<ReportPayload | null>(null)
  const [error, setError] = useState("")

  useEffect(() => {
    if (!id) return
    api<ReportPayload>(`/api/runs/${id}/report`)
      .then(setReport)
      .catch((err: Error) => setError(err.message || "failed"))
  }, [id])

  if (error) {
    return (
      <div className="space-y-3">
        <Back id={id} />
        <p className="text-sm text-destructive">{error}</p>
      </div>
    )
  }
  if (!report) return null

  return (
    <div className="space-y-4">
      <Back id={id} />
      <ReportView
        report={report}
        artifactHref={(path) => `/api/runs/${id}/file?path=${encodeURIComponent(path)}`}
      />
    </div>
  )
}

function Back({ id }: { id?: string }) {
  return (
    <div className="flex items-center gap-3 text-sm">
      <Link className="text-muted-foreground hover:text-foreground" to={id ? `/runs/${id}` : "/runs"}>
        {t("backToRun")}
      </Link>
      <span className="text-muted-foreground">/</span>
      <span className="font-medium">{t("reportPage")}</span>
    </div>
  )
}
