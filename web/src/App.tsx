import { useEffect, useState } from "react";
import {
  approveCase,
  CaseResults,
  Check,
  getDisclaimer,
  runDemo,
  simulateRfi,
} from "./api";
import "./App.css";

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "pass" || status === "READY"
      ? "badge pass"
      : status === "fail" || status === "BLOCKED"
        ? "badge fail"
        : "badge warn";
  return <span className={cls}>{status}</span>;
}

function CheckList({ checks, title }: { checks: Check[]; title: string }) {
  if (!checks.length) return null;
  return (
    <div className="panel">
      <h3>{title}</h3>
      <ul className="check-list">
        {checks.map((c, i) => (
          <li key={i} className={`check-item ${c.status}`}>
            <div className="check-header">
              <StatusBadge status={c.status} />
              <strong>{c.rule}</strong>
            </div>
            <p>{c.detail}</p>
            <p className="citation mono">{c.citation}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function App() {
  const [data, setData] = useState<CaseResults | null>(null);
  const [loading, setLoading] = useState(false);
  const [approved, setApproved] = useState(false);
  const [auditHash, setAuditHash] = useState<string | null>(null);
  const [rfiDraft, setRfiDraft] = useState<string | null>(null);
  const [disclaimer, setDisclaimer] = useState("");
  const [progress, setProgress] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDisclaimer().then(setDisclaimer).catch(() => {});
  }, []);

  async function handleStart() {
    setLoading(true);
    setError(null);
    setApproved(false);
    setRfiDraft(null);
    setData(null);
    setProgress("Starting Band agents…");
    try {
      const result = await runDemo((partial) => {
        setData(partial as CaseResults);
        const done = partial.completed_agents?.join(", ") ?? "agents";
        setProgress(`Band analysis in progress — completed: ${done}`);
      });
      setData(result);
      setAuditHash(result.permit_package.audit_hash ?? null);
      setProgress(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start analysis");
    } finally {
      setLoading(false);
    }
  }

  async function handleApprove() {
    if (!data?.case_id) return;
    try {
      const res = await approveCase(data.case_id);
      setApproved(true);
      setAuditHash((res.audit_hash as string) ?? auditHash);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approval failed");
    }
  }

  async function handleRfi() {
    if (!data?.case_id) return;
    try {
      const res = await simulateRfi(data.case_id);
      setRfiDraft(res.draft);
    } catch (e) {
      setError(e instanceof Error ? e.message : "RFI failed");
    }
  }

  const allChecks: Check[] = data
    ? [
        ...(data.jurisdiction_report?.checks ?? []),
        ...(data.building_report?.checks ?? []),
        ...(data.site_report?.environmental_checks ?? []),
        ...(data.site_report?.utility_checks ?? []),
      ]
    : [];

  const permits = data?.permit_package.permits_required ?? [];
  const filingSequence = data?.permit_package.filing_sequence ?? [];
  const documents = data?.permit_package.documents_required ?? [];

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <h1>PermitOS</h1>
          <p className="tagline">AI-powered permitting intelligence for real estate development</p>
        </div>
        <button className="btn primary" onClick={handleStart} disabled={loading}>
          {loading ? "Running analysis…" : "Run Riverside Residences Demo"}
        </button>
      </header>

      {error && <div className="error-banner">{error}</div>}
      {loading && progress && <div className="panel">{progress}</div>}

      {!data && !loading && (
        <section className="hero">
          <h2>Pre-screen permits before you file</h2>
          <p>
            PermitOS coordinates zoning, building code, and environmental review for multifamily
            projects — surfacing blockers, fee estimates, and filing order with a full audit trail.
          </p>
          <div className="value-props">
            <div className="value-card">
              <strong>Zoning &amp; jurisdiction</strong>
              <span>Setbacks, use, density, parking</span>
            </div>
            <div className="value-card">
              <strong>Building &amp; safety</strong>
              <span>Egress, fire, accessibility</span>
            </div>
            <div className="value-card">
              <strong>Site &amp; environmental</strong>
              <span>Flood, stormwater, utilities</span>
            </div>
            <div className="value-card">
              <strong>Permit package</strong>
              <span>Checklist, fees, filing sequence</span>
            </div>
          </div>
        </section>
      )}

      {loading && (
        <section className="loading-panel">
          <div className="spinner" />
          <p>Analyzing Riverside Residences — Band agents run one at a time (about 3–10 minutes on free LLM tiers)…</p>
        </section>
      )}

      {data && (
        <div className="results">
          {data.brief && (
            <section className="panel summary-panel">
              <div className="summary-top">
                <div>
                  <p className="project-label">Project</p>
                  <h2>{data.brief.project_name as string}</h2>
                  <p className="address">{data.brief.address as string}</p>
                </div>
                {data.case_summary?.readiness_score && (
                  <div className="readiness-block">
                    <span className="label">Readiness</span>
                    <StatusBadge status={data.case_summary.readiness_score} />
                  </div>
                )}
              </div>

              {data.case_summary?.executive_summary && (
                <p className="executive-summary">{data.case_summary.executive_summary}</p>
              )}

              {data.permit_package && (
                <div className="stats">
                  <div>
                    <span className="label">Est. fees</span>
                    <strong>${data.permit_package.total_fees_estimate_usd.toLocaleString()}</strong>
                  </div>
                  <div>
                    <span className="label">Timeline</span>
                    <strong>{data.permit_package.estimated_timeline_days} days</strong>
                  </div>
                  <div>
                    <span className="label">Permits</span>
                    <strong>{permits.length}</strong>
                  </div>
                  <div>
                    <span className="label">Case ID</span>
                    <span className="mono case-id">{data.case_id.slice(0, 8)}…</span>
                  </div>
                </div>
              )}

              {data.case_summary?.conflicts?.map((c, i) => (
                <div key={i} className="conflict">
                  <strong>{c.issue}</strong>
                  <p>{c.suggested_fix}</p>
                </div>
              ))}

              {data.case_summary && (
                <div className="actions">
                  <button className="btn primary" onClick={handleApprove} disabled={approved}>
                    {approved ? "Approved for Filing" : "Approve for Filing"}
                  </button>
                  <button className="btn secondary" onClick={handleRfi}>
                    Simulate City RFI
                  </button>
                </div>
              )}

              {approved && (
                <p className="approval-note">
                  Status updated to <strong>APPROVED_FOR_FILING</strong>. Package locked with audit hash below.
                </p>
              )}

              {auditHash && (
                <p className="audit-hash mono">
                  Audit hash: <code>{auditHash}</code>
                </p>
              )}
            </section>
          )}

          <div className="two-col">
            <CheckList checks={allChecks} title="Compliance findings" />

            {data.permit_package && (
              <section className="panel">
                <h3>Permit package</h3>
                {permits.length === 0 ? (
                  <p className="empty-note">No permits listed — re-run analysis or check API logs.</p>
                ) : (
                  <ul className="permit-list">
                    {permits.map((p, i) => (
                      <li key={i}>
                        <strong>{p.permit_name}</strong>
                        <span>{p.agency}</span>
                        <span className="mono">
                          ${p.fee_usd.toLocaleString()} · {p.timeline_days}d
                        </span>
                      </li>
                    ))}
                  </ul>
                )}

                {documents.length > 0 && (
                  <>
                    <h4>Required documents</h4>
                    <ul className="doc-list">
                      {documents.map((d, i) => (
                        <li key={i}>{d.name}</li>
                      ))}
                    </ul>
                  </>
                )}

                <h4>Filing sequence</h4>
                {filingSequence.length === 0 ? (
                  <p className="empty-note">Filing sequence not generated.</p>
                ) : (
                  <ol className="filing-sequence">
                    {filingSequence.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ol>
                )}
              </section>
            )}
          </div>

          {rfiDraft && (
            <section className="panel rfi-panel">
              <h3>Draft RFI response</h3>
              <p className="rfi-hint">
                Simulated city request for clarification — auto-drafted response for reviewer edit.
              </p>
              <pre className="mono">{rfiDraft}</pre>
            </section>
          )}
        </div>
      )}

      <footer className="footer">
        <p className="disclaimer">{disclaimer}</p>
      </footer>
    </div>
  );
}
