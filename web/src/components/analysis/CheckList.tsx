import type { Check } from "../../types";
import { StatusBadge } from "./StatusBadge";

export function CheckList({
  checks,
  title,
  pending,
  visible,
}: {
  checks: Check[];
  title: string;
  pending?: boolean;
  visible?: boolean;
}) {
  if (!visible && !checks.length) return null;
  if (!checks.length) {
    return (
      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
        <h3 className="mb-2 text-base font-semibold">{title}</h3>
        <p className="text-sm text-[var(--color-muted)]">{pending ? "Waiting for agent…" : "—"}</p>
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
      <h3 className="mb-4 text-base font-semibold">{title}</h3>
      <ul className="space-y-3">
        {checks.map((c, i) => (
          <li
            key={i}
            className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface2)] p-4"
          >
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <StatusBadge status={c.status} />
              <strong className="text-sm">{c.rule}</strong>
            </div>
            <p className="text-sm text-[var(--color-muted)]">{c.detail}</p>
            <p className="mono mt-2 text-xs text-[var(--color-muted)]">{c.citation}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
