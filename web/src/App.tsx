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
import { isAuthenticated, logout } from "./auth";
import LoginPage from "./LoginPage";
import SignupPage from "./SignupPage";
import "./App.css";

// ---------------------------------------------------------------------------
// Routing helpers (no library needed for this simple case)
// ---------------------------------------------------------------------------
function getRoute(): "login" | "signup" | "app" {
  const p = window.location.pathname;
  if (p.includes("/signup")) return "signup";
  return isAuthenticated() ? "app" : "login";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pass: "badge-pass",
    READY: "badge-pass",
    fail: "badge-fail",
    BLOCKED: "badge-fail",
    warn: "badge-warn",
    NEEDS_CHANGES: "badge-warn",
  };
  const cls = map[status] ?? "badge-warn";
  return <span className={`badge ${cls}`}>{status.replace(/_/g, " ")}</span>;
}

function CheckCard({ check }: { check: Check }) {
  const icon = check.status === "pass" ? "✓" : check.status === "fail" ? "✕" : "⚠";
  return (
    <div className={`check-card check-${check.status}`}>
      <div className="check-card-header">
        <span className={`check-icon check-icon-${check.status}`}>{icon}</span>
        <span className="check-rule">{check.rule}</span>
        <StatusBadge status={check.status} />
      </div>
      <p className="check-detail">{check.detail}</p>
      <p className="check-citation">{check.citation}</p>
    </div>
  );
}

function SectionPanel({
  title,
  icon,
  checks,
  pending,
  empty,
}: {
  title: string;
  icon: string;
  checks: Check[];
  pending?: boolean;
  empty?: boolean;
}) {
  return (
    <div className="section-panel">
      <div className="section-panel-header">
        <span className="section-icon">{icon}</span>
        <h3>{title}</h3>
        {pending && <span className="badge badge-warn">Analyzing…</span>}
        {!pending && !empty && checks.length > 0 && (
          <span className="badge badge-pass">{checks.length} checks</span>
        )}
      </div>
      <div className="section-panel-body">
        {pending ? (
          <div className="section-pending">
            <div className="mini-spinner" />
            <span>Waiting for results…</span>
          </div>
        ) : empty || checks.length === 0 ? (
          <p className="muted-note">No data yet.</p>
        ) : (
          checks.map((c, i) => <CheckCard key={i} check={c} />)
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
      {sub && <span className="stat-sub">{sub}</span>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main dashboard
// ---------------------------------------------------------------------------

export default function App() {
  const route = getRoute();

  function handleLoginSuccess() {
    window.location.reload();
  }

  if (route === "signup") return <SignupPage />;
  if (route === "login") return <LoginPage onSuccess={handleLoginSuccess} />;

  return <Dashboard />;
}

function Dashboard() {
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
  const [activeTab, setActiveTab] = useState<"overview" | "jurisdiction" | "building" | "site" | "package">("overview");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const completedCount = data?.completed_agents?.length ?? 0;
  const analyzing = loading && !stallReason;

  useEffect(() => {
    getDisclaimer().then(setDisclaimer).catch(() => {});
  }, []);

  useEffect(() => {
    if (!loading) { setElapsedSec(0); return; }
    const started = Date.now();
    const id = window.setInterval(() => setElapsedSec(Math.floor((Date.now() - started) / 1000)), 1000);
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
    if (!projectFile) { setError("Select a project brief (.json) or package (.zip)."); return; }
    setLoading(true);
    setError(null);
    setApproved(false);
    setRfiDraft(null);
    setData(null);
    setStallReason(null);
    setProgress("Initializing analysis pipeline…");
    setActiveTab("overview");
    try {
      const result = await analyzeProject(projectFile, projectType, jurisdiction, (partial) => {
        setData(partial as CaseResults);
        const n = partial.completed_agents?.length ?? 0;
        if (n === 0) setProgress("Running jurisdiction & zoning analysis…");
        else if (n === 1) setProgress("Running building safety checks…");
        else if (n === 2) setProgress("Running site & environmental review…");
        else setProgress("Assembling permit package…");
      });
      setData(result);
      setAuditHash(result.permit_package?.audit_hash ?? null);
      if (result.stalled) setStallReason(result.stall_reason || "Analysis could not complete.");
      setProgress(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setData(null); setProjectFile(null); setError(null);
    setStallReason(null); setProgress(null); setApproved(false);
    setRfiDraft(null); setAuditHash(null); setActiveTab("overview");
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
      setActiveTab("overview");
    } catch (e) {
      setError(e instanceof Error ? e.message : "RFI failed");
    }
  }

  function formatTime(s: number) {
    return `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;
  }

  const jurisdictionChecks = data?.jurisdiction_report?.checks ?? [];
  const buildingChecks = data?.building_report?.checks ?? [];
  const siteChecks = [...(data?.site_report?.environmental_checks ?? []), ...(data?.site_report?.utility_checks ?? [])];
  const permits = data?.permit_package?.permits_required ?? [];
  const filingSequence = data?.permit_package?.filing_sequence ?? [];
  const documents = data?.permit_package?.documents_required ?? [];

  const tabs = [
    { id: "overview" as const, label: "Overview", icon: "◎" },
    { id: "jurisdiction" as const, label: "Jurisdiction", icon: "⚖" },
    { id: "building" as const, label: "Building", icon: "🏗" },
    { id: "site" as const, label: "Site", icon: "🌿" },
    { id: "package" as const, label: "Package", icon: "📋" },
  ];

  return (
    <div className="dashboard">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="sidebar-logo">⚡</span>
          <div>
            <div className="sidebar-title">PermitOS</div>
            <div className="sidebar-tagline">Permitting Intelligence</div>
          </div>
        </div>

        <nav className="sidebar-nav">
          <a href="/" className="sidebar-home-link">
            <span>←</span> Home
          </a>
        </nav>

        {data && (
          <nav className="sidebar-tabs">
            {tabs.map((t) => (
              <button
                key={t.id}
                className={`sidebar-tab ${activeTab === t.id ? "active" : ""}`}
                onClick={() => setActiveTab(t.id)}
              >
                <span className="tab-icon">{t.icon}</span>
                {t.label}
              </button>
            ))}
          </nav>
        )}

        <div className="sidebar-footer">
          <button
            className="sidebar-logout"
            onClick={() => { logout(); window.location.reload(); }}
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="main-content">
        {/* Top bar */}
        <div className="topbar">
          <div className="topbar-left">
            <h1 className="topbar-title">
              {data ? (data.brief?.project_name as string) || "Analysis" : "New Analysis"}
            </h1>
            {data?.case_summary?.readiness_score && (
              <StatusBadge status={data.case_summary.readiness_score} />
            )}
            {loading && <div className="topbar-spinner" />}
          </div>
          <div className="topbar-right">
            {data && !loading && (
              <button className="btn btn-ghost" onClick={handleReset}>+ New Analysis</button>
            )}
          </div>
        </div>

        {/* Banners */}
        {stallReason && <div className="banner banner-warn">{stallReason}</div>}
        {error && <div className="banner banner-error">{error}</div>}

        {/* Progress bar */}
        {loading && progress && (
          <div className="progress-wrapper">
            <div className="progress-info">
              <span>{progress}</span>
              <span className="muted">{formatTime(elapsedSec)} elapsed</span>
            </div>
            <div className="progress-track">
              <div
                className="progress-fill"
                style={{ width: `${Math.min(90, (completedCount / 4) * 100 + (elapsedSec % 30) / 30 * 25)}%` }}
              />
            </div>
            <div className="progress-steps">
              {["Jurisdiction", "Building", "Site", "Package"].map((step, i) => (
                <div key={step} className={`progress-step ${i < completedCount ? "done" : i === completedCount ? "active" : ""}`}>
                  <div className="progress-dot" />
                  <span>{step}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Intake form */}
        {!data && !loading && (
          <div className="intake-wrapper">
            <div className="intake-card">
              <h2>Project intake</h2>
              <p className="intake-desc">Upload a project brief to run the permit pre-screen analysis.</p>

              <div className="intake-selects">
                <div className="form-field">
                  <label>Jurisdiction</label>
                  <select value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value)}>
                    {JURISDICTIONS.map((j) => (
                      <option key={j.value} value={j.value}>{j.label}</option>
                    ))}
                  </select>
                </div>
                <div className="form-field">
                  <label>Project type</label>
                  <select value={projectType} onChange={(e) => setProjectType(e.target.value as ProjectTypeValue)}>
                    {PROJECT_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div
                className={`drop-zone ${dragOver ? "dz-hover" : ""} ${projectFile ? "dz-filled" : ""}`}
                onClick={() => fileInputRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => { e.preventDefault(); setDragOver(false); acceptFile(e.dataTransfer.files[0]); }}
                role="button" tabIndex={0}
                onKeyDown={(e) => e.key === "Enter" && fileInputRef.current?.click()}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".json,.zip"
                  className="hidden-input"
                  onChange={(e) => acceptFile(e.target.files?.[0] ?? null)}
                />
                {projectFile ? (
                  <div className="dz-file">
                    <span className="dz-file-icon">📄</span>
                    <div>
                      <strong>{projectFile.name}</strong>
                      <span className="muted">{(projectFile.size / 1024).toFixed(1)} KB</span>
                    </div>
                  </div>
                ) : (
                  <div className="dz-empty">
                    <span className="dz-upload-icon">↑</span>
                    <strong>Drop file here or click to browse</strong>
                    <span className="muted">.json or .zip project brief</span>
                  </div>
                )}
              </div>

              <div className="intake-actions">
                <button
                  className="btn btn-primary"
                  onClick={handleAnalyze}
                  disabled={!projectFile || loading}
                >
                  Run Analysis
                </button>
                {!projectFile && (
                  <a className="link-subtle" href="/sample-project-brief.json" download>
                    Download sample brief
                  </a>
                )}
              </div>
            </div>

            <div className="feature-grid">
              {[
                { icon: "⚖", title: "Jurisdiction & Zoning", desc: "Setbacks, use, density, and parking requirements" },
                { icon: "🏗", title: "Building & Safety", desc: "Egress, fire suppression, and accessibility codes" },
                { icon: "🌿", title: "Site & Environmental", desc: "Flood zone, stormwater, and utility capacity" },
                { icon: "📋", title: "Permit Package", desc: "Checklist, fee estimates, and filing sequence" },
              ].map((f) => (
                <div key={f.title} className="feature-card">
                  <span className="feature-icon">{f.icon}</span>
                  <div>
                    <strong>{f.title}</strong>
                    <p>{f.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Results */}
        {(data || (loading && completedCount > 0)) && (
          <div className="results-layout">
            {/* Stats row */}
            {data?.permit_package && (
              <div className="stats-row">
                <StatCard
                  label="Est. fees"
                  value={`$${data.permit_package.total_fees_estimate_usd.toLocaleString()}`}
                  sub="total permit costs"
                />
                <StatCard
                  label="Timeline"
                  value={`${data.permit_package.estimated_timeline_days}d`}
                  sub="estimated review"
                />
                <StatCard
                  label="Permits"
                  value={`${permits.length}`}
                  sub="required filings"
                />
                <StatCard
                  label="Readiness"
                  value={data.case_summary?.readiness_score?.replace(/_/g, " ") ?? "—"}
                  sub="overall status"
                />
              </div>
            )}

            {/* Executive summary + actions */}
            {activeTab === "overview" && (
              <div className="overview-section">
                {data?.case_summary?.executive_summary && (
                  <div className="exec-summary">
                    <div className="exec-summary-label">Executive Summary</div>
                    <p>{data.case_summary.executive_summary}</p>
                  </div>
                )}

                {data?.case_summary?.conflicts?.map((c, i) => (
                  <div key={i} className="conflict-card">
                    <div className="conflict-header">
                      <span className="conflict-icon">⚠</span>
                      <strong>{c.issue}</strong>
                      <span className={`badge badge-${c.severity === "high" ? "fail" : "warn"}`}>{c.severity}</span>
                    </div>
                    <p>{c.suggested_fix}</p>
                  </div>
                ))}

                {data?.case_summary && !approved && (
                  <div className="action-bar">
                    <button className="btn btn-primary" onClick={handleApprove}>
                      ✓ Approve for Filing
                    </button>
                    <button className="btn btn-outline" onClick={handleRfi}>
                      Simulate City RFI
                    </button>
                  </div>
                )}

                {approved && (
                  <div className="approval-card">
                    <span className="approval-icon">✓</span>
                    <div>
                      <strong>Approved for Filing</strong>
                      <p>Package is locked with a tamper-evident audit hash.</p>
                      {auditHash && <code className="audit-hash">{auditHash}</code>}
                    </div>
                  </div>
                )}

                {rfiDraft && (
                  <div className="rfi-card">
                    <h4>Draft RFI Response</h4>
                    <p className="muted rfi-hint">Auto-generated response — review before sending.</p>
                    <pre>{rfiDraft}</pre>
                  </div>
                )}

                {/* Show agent summary cards while loading */}
                {analyzing && (
                  <div className="agent-status-grid">
                    {[
                      { key: "jurisdiction", label: "Jurisdiction", icon: "⚖", checks: jurisdictionChecks },
                      { key: "building", label: "Building", icon: "🏗", checks: buildingChecks },
                      { key: "site", label: "Site & Env", icon: "🌿", checks: siteChecks },
                    ].map(({ key, label, icon, checks }) => {
                      const done = (data?.completed_agents ?? []).includes(key);
                      return (
                        <div key={key} className={`agent-status-card ${done ? "agent-done" : "agent-pending"}`}>
                          <span>{icon}</span>
                          <div>
                            <strong>{label}</strong>
                            <span>{done ? `${checks.length} checks complete` : "Analyzing…"}</span>
                          </div>
                          {done ? <span className="agent-check">✓</span> : <div className="mini-spinner" />}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {activeTab === "jurisdiction" && (
              <SectionPanel
                title="Jurisdiction & Zoning"
                icon="⚖"
                checks={jurisdictionChecks}
                pending={analyzing && jurisdictionChecks.length === 0}
              />
            )}

            {activeTab === "building" && (
              <SectionPanel
                title="Building & Safety"
                icon="🏗"
                checks={buildingChecks}
                pending={analyzing && buildingChecks.length === 0}
              />
            )}

            {activeTab === "site" && (
              <SectionPanel
                title="Site & Environmental"
                icon="🌿"
                checks={siteChecks}
                pending={analyzing && siteChecks.length === 0}
              />
            )}

            {activeTab === "package" && data?.permit_package && (
              <div className="package-section">
                <div className="package-grid">
                  <div className="package-col">
                    <h4>Required Permits</h4>
                    <div className="permit-list">
                      {permits.map((p, i) => (
                        <div key={i} className="permit-item">
                          <div className="permit-item-main">
                            <strong>{p.permit_name}</strong>
                            <span className="permit-agency">{p.agency}</span>
                          </div>
                          <div className="permit-item-meta">
                            <span>${p.fee_usd.toLocaleString()}</span>
                            <span>{p.timeline_days}d</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="package-col">
                    <h4>Required Documents</h4>
                    <ul className="doc-list">
                      {documents.map((d, i) => <li key={i}>{d.name}</li>)}
                    </ul>

                    <h4 style={{ marginTop: "1.5rem" }}>Filing Sequence</h4>
                    <ol className="filing-list">
                      {filingSequence.map((s, i) => <li key={i}>{s}</li>)}
                    </ol>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <footer className="dash-footer">
          <p>{disclaimer}</p>
        </footer>
      </main>
    </div>
  );
}
