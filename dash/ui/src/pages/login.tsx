import { type FormEvent, useState } from "react"
import { useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { Card, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { api } from "@/lib/api"
import { t } from "@/lib/i18n"

export function LoginPage() {
  const navigate = useNavigate()
  const [login, setLogin] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")

  async function onSubmit(event: FormEvent) {
    event.preventDefault()
    setError("")
    try {
      await api("/api/login", { method: "POST", body: JSON.stringify({ login, password }) })
      navigate("/")
    } catch {
      setError(t("loginError"))
    }
  }

  return (
    <div className="flex min-h-svh items-center justify-center bg-muted p-6">
      <Card className="w-full max-w-sm space-y-4">
        <CardTitle>{t("brand")}</CardTitle>
        <form className="space-y-3" onSubmit={onSubmit}>
          <label className="block space-y-1 text-sm">
            <span>{t("username")}</span>
            <Input value={login} onChange={(e) => setLogin(e.target.value)} autoComplete="username" />
          </label>
          <label className="block space-y-1 text-sm">
            <span>{t("password")}</span>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </label>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
          <Button type="submit" className="w-full">
            {t("login")}
          </Button>
        </form>
      </Card>
    </div>
  )
}
