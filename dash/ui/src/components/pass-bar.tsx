export function PassBar({
  passed,
  failed,
  skipped,
}: {
  passed: number
  failed: number
  skipped: number
}) {
  const total = Math.max(1, passed + failed + skipped)
  return (
    <div className="flex h-2 overflow-hidden rounded-full bg-muted">
      <i className="bg-emerald-500" style={{ width: `${(100 * passed) / total}%` }} />
      <i className="bg-destructive" style={{ width: `${(100 * failed) / total}%` }} />
      <i className="bg-amber-400" style={{ width: `${(100 * skipped) / total}%` }} />
    </div>
  )
}
