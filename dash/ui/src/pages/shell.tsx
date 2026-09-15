import { useEffect, useState } from "react"
import { Link, NavLink, Navigate, Outlet } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { api, type Me, type Overview } from "@/lib/api"
import { t } from "@/lib/i18n"

const links = [
  { to: "/", label: t("home"), end: true },
  { to: "/cases", label: t("cases") },
  { to: "/plan", label: t("plan") },
  { to: "/runs", label: t("runs") },
  { to: "/cli", label: t("cli") },
  { to: "/skill", label: t("skill") },
]

export function AppShell() {
  const [me, setMe] = useState<Me | null>(null)
  const [ready, setReady] = useState(false)
  const [live, setLive] = useState(0)

  useEffect(() => {
    api<Me>("/api/me")
      .then(setMe)
      .catch(() => setMe(null))
      .finally(() => setReady(true))
  }, [])

  useEffect(() => {
    if (!me) return
    const tick = () =>
      api<Overview>("/api/overview?hours=24")
        .then((data) => setLive(data.live.length))
        .catch(() => setLive(0))
    void tick()
    const timer = window.setInterval(tick, 4000)
    return () => window.clearInterval(timer)
  }, [me])

  if (!ready) {
    return null
  }
  if (!me) {
    return <Navigate to="/login" replace />
  }

  async function logout() {
    await api("/api/logout", { method: "POST" })
    window.location.href = "/login"
  }

  return (
    <div className="min-h-svh">
      <header className="flex items-center justify-between border-b px-6 py-3">
        <nav className="flex items-center gap-4 text-sm">
          <Link to="/" className="font-medium">
            {t("brand")}
          </Link>
          {links.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? "font-medium" : "text-muted-foreground")}
            >
              {item.label}
            </NavLink>
          ))}
          {live ? <Badge variant="running">{live} live</Badge> : null}
        </nav>
        <div className="flex items-center gap-3 text-sm">
          <span className="text-muted-foreground">{me.login}</span>
          <Button variant="ghost" size="sm" onClick={() => void logout()}>
            {t("logout")}
          </Button>
        </div>
      </header>
      <main className="mx-auto max-w-6xl p-6">
        <Outlet />
      </main>
    </div>
  )
}
