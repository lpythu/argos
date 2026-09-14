export function fmtDur(seconds: number | undefined): string {
  const value = Number(seconds || 0)
  if (!value) return "—"
  if (value < 60) return `${value.toFixed(value < 10 ? 1 : 0)}s`
  const minutes = Math.floor(value / 60)
  const rest = Math.round(value % 60)
  if (minutes < 60) return rest ? `${minutes}m ${rest}s` : `${minutes}m`
  const hours = Math.floor(minutes / 60)
  const mins = minutes % 60
  return mins ? `${hours}h ${mins}m` : `${hours}h`
}

export function fmtWhen(value: string | undefined): string {
  if (!value) return "—"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}

export function metricValue(value: unknown, unit = ""): string {
  const shown =
    typeof value === "number"
      ? Number(value.toFixed(3)).toString()
      : Array.isArray(value)
        ? value.join(", ")
        : String(value ?? "—")
  return unit ? `${shown} ${unit}` : shown
}

export async function copyText(value: string): Promise<void> {
  await navigator.clipboard.writeText(value)
}
