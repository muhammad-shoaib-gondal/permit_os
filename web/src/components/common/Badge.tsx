import { cn } from "../../lib/utils";

export function Badge({
  children,
  variant = "default",
  className,
}: {
  children: React.ReactNode;
  variant?: "default" | "pass" | "fail" | "warn" | "ready";
  className?: string;
}) {
  const variants = {
    default: "bg-[var(--color-surface2)] text-[var(--color-muted)]",
    pass: "bg-emerald-500/15 text-[var(--color-pass)]",
    fail: "bg-red-500/15 text-[var(--color-fail)]",
    warn: "bg-amber-500/15 text-[var(--color-warn)]",
    ready: "bg-violet-500/15 text-violet-300",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium uppercase tracking-wide",
        variants[variant],
        className
      )}
    >
      {children}
    </span>
  );
}
