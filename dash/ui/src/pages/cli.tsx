import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Card, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { t } from "@/lib/i18n"

type CliConfig = {
  url: string
  token: string
  env: string
  library_skill: string
}

export function CliPage() {
  const [cfg, setCfg] = useState<CliConfig | null>(null)
  const [error, setError] = useState("")
  const [revealed, setRevealed] = useState(false)
  const [copied, setCopied] = useState("")

  useEffect(() => {
    api<CliConfig>("/api/cli-config")
      .then(setCfg)
      .catch((exc: Error) => setError(exc.message || t("cliTokenMissing")))
  }, [])

  async function copy(value: string, label: string) {
    await navigator.clipboard.writeText(value)
    setCopied(label)
    window.setTimeout(() => setCopied(""), 1500)
  }

  function download() {
    window.location.href = "/api/cli-config/dash.env"
  }

  const installLib = cfg ? `Install ${cfg.library_skill}` : ""
  const runExample = "argos run <id> --dash ./dash.env"

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-medium">{t("cli")}</h1>
        <p className="text-sm text-muted-foreground">{t("cliHint")}</p>
      </div>
      {error ? (
        <Card className="space-y-2">
          <CardTitle>{t("cliTokenMissing")}</CardTitle>
          <p className="text-sm text-muted-foreground font-mono">{error}</p>
        </Card>
      ) : null}
      {cfg ? (
        <>
          <Card className="space-y-3">
            <CardTitle>{t("cliOrigin")}</CardTitle>
            <div className="flex flex-wrap gap-2">
              <Input className="font-mono text-sm" readOnly value={cfg.url} />
              <Button variant="outline" onClick={() => void copy(cfg.url, t("cliOrigin"))}>
                {t("copy")}
              </Button>
            </div>
          </Card>
          <Card className="space-y-3">
            <CardTitle>{t("cliToken")}</CardTitle>
            <div className="flex flex-wrap gap-2">
              <Input
                className="font-mono text-sm"
                readOnly
                type={revealed ? "text" : "password"}
                value={cfg.token}
              />
              <Button variant="outline" onClick={() => setRevealed((v) => !v)}>
                {revealed ? t("cliHide") : t("cliReveal")}
              </Button>
              <Button variant="outline" onClick={() => void copy(cfg.token, t("cliToken"))}>
                {t("copy")}
              </Button>
            </div>
          </Card>
          <Card className="space-y-3">
            <CardTitle>{t("cliDownload")}</CardTitle>
            <p className="text-sm text-muted-foreground">{t("cliDownloadHint")}</p>
            <pre className="overflow-x-auto rounded-lg border bg-muted/40 p-3 font-mono text-xs">{cfg.env}</pre>
            <div className="flex flex-wrap gap-2">
              <Button onClick={download}>{t("cliDownload")}</Button>
              <Button variant="outline" onClick={() => void copy(cfg.env, t("cliDownload"))}>
                {t("copyEnv")}
              </Button>
              <Button variant="outline" onClick={() => void copy(runExample, t("cliRunExample"))}>
                {t("copyCmd")}
              </Button>
            </div>
            <p className="font-mono text-sm">{runExample}</p>
          </Card>
          <Card className="space-y-3">
            <CardTitle>{t("cliLibrary")}</CardTitle>
            <p className="text-sm text-muted-foreground">{t("cliLibraryHint")}</p>
            <p className="font-mono text-sm">{installLib}</p>
            <Button variant="outline" onClick={() => void copy(installLib, t("cliLibrary"))}>
              {t("copyInstall")}
            </Button>
          </Card>
        </>
      ) : null}
      {copied ? <span className="text-sm text-muted-foreground">{t("copied")}: {copied}</span> : null}
    </div>
  )
}
