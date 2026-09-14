import { cn } from "@/lib/utils"

const tone: Record<string, string> = {
  pass: "bg-emerald-500",
  fail: "bg-destructive",
  skip: "bg-amber-400",
  running: "bg-sky-500",
  interrupted: "bg-foreground/40",
}

export function IterStrip({ items }: { items: { iteration: number; status: string }[] }) {
  if (!items.length) return null
  return (
    <div className="flex flex-wrap gap-0.5">
      {items.map((item) => (
        <i
          key={`${item.iteration}-${item.status}`}
          title={`#${item.iteration} ${item.status}`}
          className={cn("h-2 w-2 rounded-sm", tone[item.status] || tone.interrupted)}
        />
      ))}
    </div>
  )
}
