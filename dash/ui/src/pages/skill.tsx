import { useEffect, useState } from "react"
import Markdown from "react-markdown"
import remarkGfm from "remark-gfm"

import { Button } from "@/components/ui/button"
import { Card, CardTitle } from "@/components/ui/card"
import { t } from "@/lib/i18n"

export function SkillPage() {
  const [text, setText] = useState("")
  const [copied, setCopied] = useState("")
  const install = `Install ${window.location.origin}/skill.md`

  useEffect(() => {
    fetch("/skill.md")
      .then((resp) => resp.text())
      .then(setText)
      .catch(() => setText(""))
  }, [])

  async function copy(value: string, label: string) {
    await navigator.clipboard.writeText(value)
    setCopied(label)
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        <Button onClick={() => void copy(text, t("copySkill"))}>{t("copySkill")}</Button>
        <Button variant="outline" onClick={() => void copy(install, t("copyInstall"))}>
          {t("copyInstall")}
        </Button>
        {copied ? <span className="self-center text-sm text-muted-foreground">{t("copied")}</span> : null}
      </div>
      <Card className="space-y-3">
        <CardTitle>{t("skill")}</CardTitle>
        <p className="font-mono text-sm">{install}</p>
        <div className="prose prose-sm max-w-none dark:prose-invert">
          <Markdown remarkPlugins={[remarkGfm]}>{text}</Markdown>
        </div>
      </Card>
    </div>
  )
}
