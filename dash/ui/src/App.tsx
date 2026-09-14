import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"

import { CasesPage } from "@/pages/cases"
import { HomePage } from "@/pages/home"
import { LoginPage } from "@/pages/login"
import { PlanPage } from "@/pages/plan"
import { RunDetailPage } from "@/pages/run-detail"
import { RunsPage } from "@/pages/runs"
import { AppShell } from "@/pages/shell"
import { SkillPage } from "@/pages/skill"

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<AppShell />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/cases" element={<CasesPage />} />
          <Route path="/plan" element={<PlanPage />} />
          <Route path="/runs" element={<RunsPage />} />
          <Route path="/runs/:id" element={<RunDetailPage />} />
          <Route path="/skill" element={<SkillPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
