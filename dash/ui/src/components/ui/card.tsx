import type { ComponentProps } from "react"
import { cn } from "cn"

function Card({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("rounded-xl bg-card p-4 text-sm ring-1 ring-foreground/10", className)} {...props} />
}

function CardTitle({ className, ...props }: ComponentProps<"div">) {
  return <div className={cn("text-base font-medium", className)} {...props} />
}

export { Card, CardTitle }
