import { useSyncExternalStore } from "react"

const KEY = "argos.plan.ids"

function read(): string[] {
  try {
    const raw = JSON.parse(sessionStorage.getItem(KEY) || "[]")
    return Array.isArray(raw) ? raw.filter((item): item is string => typeof item === "string") : []
  } catch {
    return []
  }
}

let ids = read()
const listeners = new Set<() => void>()

function emit() {
  for (const listener of listeners) listener()
}

function persist(next: string[]) {
  ids = [...new Set(next)]
  sessionStorage.setItem(KEY, JSON.stringify(ids))
  emit()
}

export function usePlanIds() {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => ids,
    () => ids,
  )
}

export function togglePlan(id: string) {
  persist(ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id])
}

export function addPlan(next: string[]) {
  persist([...ids, ...next])
}

export function clearPlan() {
  persist([])
}

export function buildCommand(opts: {
  ids: string[]
  env: string
  soak: boolean
  duration: string
  pause: string
  failFast: boolean
}): string {
  const parts = ["argos", "run", ...opts.ids]
  if (opts.env) parts.push("--env", opts.env)
  if (opts.soak) {
    parts.push("--soak")
    if (opts.duration) parts.push("--for", opts.duration)
    if (opts.pause && opts.pause !== "0s") parts.push("--pause", opts.pause)
  }
  if (opts.failFast) parts.push("--fail-fast")
  parts.push("--dash")
  return parts.join(" ")
}
