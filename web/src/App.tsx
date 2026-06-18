import { useEffect, useRef, useState } from "react";
import {
  analyzeProject,
  approveCase,
  CaseResults,
  Check,
  getDisclaimer,
  JURISDICTIONS,
  PROJECT_TYPES,
  ProjectTypeValue,
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

function CheckList({
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
      <div className="panel agent-panel panel-pending">
        <h3>{title}</h3>
        <p className="pending-note">{pending ? "Waiting for agent…" : "—"}</p>
      </div>
    );
  }
  return (
    <div className="panel agent-panel">
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

const SEC_PER_AGENT = 120;
const TOTAL_AGENTS = 4;

function formatDuration(totalSec: number): string {
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function estimateRemainingSec(elapsed: number, completedCount: number): number {
  const agentsLeft = Math.max(0, TOTAL_AGENTS - completedCount);
  if (agentsLeft === 0) return 0;
  const budget = agentsLeft * SEC_PER_AGENT;
  const spentOnCurrent = elapsed - completedCount * SEC_PER_AGENT;
  return Math.max(30, budget - Math.max(0, spentOnCurrent));
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

  const [stallReason, setStallReason] = useState<string | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [projectFile, setProjectFile] = useState<File | null>(null);
  const [projectType, setProjectType] = useState<ProjectTypeValue>("multifamily_residential");
  const [jurisdiction, setJurisdiction] = useState("austin_tx");
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const completedCount = data?.completed_agents?.length ?? 0;

  useEffect(() => {
    getDisclaimer().then(setDisclaimer).catch(() => {});
  }, []);

  useEffect(() => {
    if (!loading) {
      setElapsedSec(0);
      return;
    }
    const started = Date.now();
    const tick = () => setElapsedSec(Math.floor((Date.now() - started) / 1000));
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [loading]);

  function acceptFile(file: File | null) {
    if (!file) return;
    const name = file.name.toLowerCase();
    if (!name.endsWith(".json") && !name.endsWith(".zip")) {
      setError("Upload a .json project brief or a .zip package.");
      return;
    }
    setError(null);
    setProjectFile(file);
  }

  async function handleAnalyze() {
    if (!projectFile) {
      setError("Select or drop a project brief (.json) or package (.zip).");
      return;
    }
    setLoading(true);
    setError(null);
    setApproved(false);
    setRfiDraft(null);
    setData(null);
    setStallReason(null);
    setProgress("Agents are analyzing your project…");
    try {
      const result = await analyzeProject(projectFile, projectType, jurisdiction, (partial) => {
        setData(partial as CaseResults);
        const n = partial.completed_agents?.length ?? 0;
        if (n === 0) {
          setProgress("Agents are analyzing your project…");
        } else if (n >= 3) {
          setProgress("Agents are assembling the permit package…");
        } else {
          setProgress(`Agent analysis in progress — ${n} of 3 reviews complete`);
        }
      });
      setData(result);
      setAuditHash(result.permit_package?.audit_hash ?? null);
      if (result.stalled) {
        setStallReason(result.stall_reason || "Something went wrong — we couldn't complete the analysis.");
      }
      setProgress(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start analysis");
    } finally {
      setLoading(false);
    }
  }

  function handleNewAnalysis() {
    setData(null);
    setProjectFile(null);
    setError(null);
    setStallReason(null);
    setProgress(null);
    setApproved(false);
    setRfiDraft(null);
    setAuditHash(null);
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

  const permits = data?.permit_package?.permits_required ?? [];
  const filingSequence = data?.permit_package?.filing_sequence ?? [];
  const documents = data?.permit_package?.documents_required ?? [];
  const remainingSec = estimateRemainingSec(elapsedSec, completedCount);
  const analyzing = loading && !stallReason;
  const jurisdictionChecks = data?.jurisdiction_report?.checks ?? [];
  const buildingChecks = data?.building_report?.checks ?? [];
  const siteChecks = [
    ...(data?.site_report?.environmental_checks ?? []),
    ...(data?.site_report?.utility_checks ?? []),
  ];
  const showAgentPanels = analyzing || !!data;

  function renderAgentPanels() {
    return (
      <div className="findings-layout">
        <div className="findings-row findings-row-top">
          <CheckList
            checks={jurisdictionChecks}
            title="Jurisdiction & zoning"
            pending={analyzing && jurisdictionChecks.length === 0}
            visible={showAgentPanels}
          />
          <CheckList
            checks={buildingChecks}
            title="Building & safety"
            pending={analyzing && buildingChecks.length === 0}
            visible={showAgentPanels}
          />
        </div>
        <CheckList
          checks={siteChecks}
          title="Site & environmental"
          pending={analyzing && siteChecks.length === 0}
          visible={showAgentPanels}
        />
      </div>
    );
  }

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <h1>PermitOS</h1>
          <p className="tagline">AI-powered permitting intelligence for real estate development</p>
        </div>
        {data && !loading && (
          <button className="btn secondary" type="button" onClick={handleNewAnalysis}>
            New analysis
          </button>
        )}
      </header>

      {!data && !loading && (
        <section className="panel intake-panel">
          <h2>Project intake</h2>

          <div className="intake-controls">
            <label className="intake-field">
              <span>Jurisdiction</span>
              <select
                value={jurisdiction}
                onChange={(e) => setJurisdiction(e.target.value)}
                disabled={loading}
              >
                {JURISDICTIONS.map((j) => (
                  <option key={j.value} value={j.value}>
                    {j.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="intake-field">
              <span>Project type</span>
              <select
                value={projectType}
                onChange={(e) => setProjectType(e.target.value as ProjectTypeValue)}
                disabled={loading}
              >
                {PROJECT_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div
            className={`drop-zone ${dragOver ? "drag-over" : ""} ${projectFile ? "has-file" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              acceptFile(e.dataTransfer.files[0] ?? null);
            }}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(e) => e.key === "Enter" && fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".json,.zip,application/json,application/zip"
              className="file-input-hidden"
              onChange={(e) => acceptFile(e.target.files?.[0] ?? null)}
            />
            {projectFile ? (
              <>
                <strong>{projectFile.name}</strong>
                <span>{(projectFile.size / 1024).toFixed(1)} KB</span>
              </>
            ) : (
              <>
                <strong>Drop file here</strong>
                <span>or click to browse — .json or .zip</span>
              </>
            )}
          </div>

          <div className="intake-actions">
            <button
              className="btn primary"
              type="button"
              onClick={handleAnalyze}
              disabled={loading || !projectFile}
            >
              {loading ? "Analyzing…" : "Analyze"}
            </button>
            {!projectFile && (
              <a className="sample-link" href="/sample-project-brief.json" download>
                Download sample brief
              </a>
            )}
          </div>
        </section>
      )}

      {stallReason && <div className="stall-banner">{stallReason}</div>}
      {error && <div className="error-banner">{error}</div>}
      {loading && progress && (
        <div className="panel progress-panel">
          <div className="progress-row">
            <span>{progress}</span>
            <span className="timer mono">
              {formatDuration(elapsedSec)} elapsed
              {remainingSec > 0 && ` · ~${formatDuration(remainingSec)} left`}
            </span>
          </div>
          <div className="progress-bar-track">
            <div
              className="progress-bar-fill"
              style={{
                width: `${Math.min(100, ((completedCount / TOTAL_AGENTS) * 100 + (elapsedSec % SEC_PER_AGENT) / SEC_PER_AGENT / TOTAL_AGENTS * 100))}%`,
              }}
            />
          </div>
        </div>
      )}

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

      {loading && !data && (
        <section className="loading-panel loading-panel-compact">
          <div className="spinner" />
          <p className="timer mono">
            {formatDuration(elapsedSec)} elapsed
            {remainingSec > 0 && ` · ~${formatDuration(remainingSec)} remaining`}
          </p>
        </section>
      )}

      {showAgentPanels && !data && renderAgentPanels()}

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
                  {data.case_id && (
                    <div>
                      <span className="label">Case ID</span>
                      <span className="mono case-id">{data.case_id.slice(0, 8)}…</span>
                    </div>
                  )}
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

          {renderAgentPanels()}

          {data.permit_package && (
            <section className="panel permit-package-panel">
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

          {analyzing && !data.permit_package && (
            <section className="panel panel-pending permit-package-panel">
              <h3>Permit package</h3>
              <p className="pending-note">Waiting for agent…</p>
            </section>
          )}

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
