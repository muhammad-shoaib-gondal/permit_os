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
        <p className="text-sm text-[var(--color-muted)]">{pending ? "Reviewing uploaded files…" : "—"}</p>
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
            {!!c.missing_inputs?.length && (
              <div className="mt-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2">
                <p className="text-xs font-medium">Not verified because</p>
                <p className="mt-1 text-xs text-[var(--color-muted)]">{c.missing_inputs.join(", ")}</p>
              </div>
            )}
            {!!c.evidence?.length && (
              <details className="mt-3 cursor-pointer rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2">
                <summary className="text-xs font-medium">Evidence used ({c.evidence.length})</summary>
                <div className="mt-2 space-y-2">
                  {c.evidence.map((evidence, evidenceIndex) => (
                    <div key={`${evidence.document}-${evidenceIndex}`} className="text-xs text-[var(--color-muted)]">
                      <p className="font-medium text-[var(--color-text)]">{evidence.document}</p>
                      <p>{evidence.detail}</p>
                      <p>
                        {evidence.sourceType.split("_").join(" ")}
                        {evidence.page ? `, page ${evidence.page}` : ""}
                      </p>
                      {evidence.url && (
                        <a
                          className="text-[var(--color-accent)] underline"
                          href={evidence.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Open official record
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              </details>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
