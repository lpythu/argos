import type { VariantProps } from "class-variance-authority"

import { badgeVariants } from "@/components/ui/badge"

type Variant = NonNullable<VariantProps<typeof badgeVariants>["variant"]>

export function statusVariant(status: string): Variant {
  if (status === "pass" || status === "ok") return "pass"
  if (status === "fail" || status === "failed") return "fail"
  if (status === "skip") return "skip"
  if (status === "running" || status === "starting" || status === "waiting") return "running"
  return "secondary"
}
