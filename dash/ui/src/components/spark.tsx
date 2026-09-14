export function Spark({ points }: { points: { iter: number; value: number }[] }) {
  if (points.length < 2) return null
  const ys = points.map((item) => item.value)
  const min = Math.min(...ys)
  const max = Math.max(...ys)
  const span = max - min || 1
  const width = 280
  const height = 56
  const d = points
    .map((item, index) => {
      const x = (index / (points.length - 1)) * width
      const y = height - ((item.value - min) / span) * (height - 8) - 4
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(" ")
  return (
    <div className="space-y-1">
      <svg viewBox={`0 0 ${width} ${height}`} className="h-14 w-full text-sky-600">
        <path d={d} fill="none" stroke="currentColor" strokeWidth="2" />
      </svg>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{min.toFixed(3)}</span>
        <span>{max.toFixed(3)}</span>
      </div>
    </div>
  )
}
