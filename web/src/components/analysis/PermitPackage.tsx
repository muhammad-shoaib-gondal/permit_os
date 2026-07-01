import type { CaseResults } from "../../types";

type PermitPackageProps = {
  data: CaseResults;
  pending?: boolean;
};

export function PermitPackage({ data, pending }: PermitPackageProps) {
  const permits = data.permit_package?.permits_required ?? [];
  const documents = data.permit_package?.documents_required ?? [];
  const filingSequence = data.permit_package?.filing_sequence ?? [];

  if (!data.permit_package && pending) {
    return (
      <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
        <h3 className="mb-2 text-base font-semibold">Permit package</h3>
        <p className="text-sm text-[var(--color-muted)]">Waiting for agent…</p>
      </div>
    );
  }

  if (!data.permit_package) return null;

  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
      <h3 className="mb-4 text-base font-semibold">Permit package</h3>
      {permits.length === 0 ? (
        <p className="text-sm text-[var(--color-muted)]">No permits listed.</p>
      ) : (
        <ul className="mb-6 space-y-2">
          {permits.map((p, i) => (
            <li
              key={i}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-[var(--color-surface2)] px-3 py-2 text-sm"
            >
              <div>
                <strong>{p.permit_name}</strong>
                <span className="ml-2 text-[var(--color-muted)]">{p.agency}</span>
              </div>
              <span className="mono text-[var(--color-muted)]">
                ${p.fee_usd.toLocaleString()} · {p.timeline_days}d
              </span>
            </li>
          ))}
        </ul>
      )}

      {documents.length > 0 && (
        <>
          <h4 className="mb-2 text-sm font-medium">Required documents</h4>
          <ul className="mb-6 list-disc pl-5 text-sm text-[var(--color-muted)]">
            {documents.map((d, i) => (
              <li key={i}>{d.name}</li>
            ))}
          </ul>
        </>
      )}

      <h4 className="mb-2 text-sm font-medium">Filing sequence</h4>
      {filingSequence.length === 0 ? (
        <p className="text-sm text-[var(--color-muted)]">Not generated.</p>
      ) : (
        <ol className="list-decimal pl-5 text-sm text-[var(--color-muted)]">
          {filingSequence.map((s, i) => (
            <li key={i} className="mb-1">
              {s}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
