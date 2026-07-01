import { Badge } from "../common/Badge";

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  const variant =
    normalized === "pass" || normalized === "ready"
      ? "pass"
      : normalized === "fail" || normalized === "blocked"
        ? "fail"
        : normalized === "warn" || normalized === "needs_changes"
          ? "warn"
          : "default";
  return <Badge variant={variant}>{status}</Badge>;
}
