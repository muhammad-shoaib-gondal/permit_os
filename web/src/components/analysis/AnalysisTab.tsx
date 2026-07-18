import { useEffect, useState } from "react";
import { Download, Play } from "lucide-react";
import { ANALYSIS_MODULES } from "../../types";
import type { AnalysisModuleKey, CaseResults, Project } from "../../types";
import { approveCase, simulateRfi } from "../../api";
import { useAnalysisStore } from "../../stores/projectStore";
import { toast } from "../../stores/toastStore";
import { Button } from "../common/Button";
import { CheckList } from "./CheckList";
import { PermitPackage } from "./PermitPackage";
import { StatusBadge } from "./StatusBadge";
import { downloadAnalysisReport } from "../../lib/pdfExport";
import { formatDate } from "../../lib/utils";

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

type AnalysisTabProps = {
  project: Project;
  onAnalysisComplete?: () => void;
};

export function AnalysisTab({ project, onAnalysisComplete }: AnalysisTabProps) {
  const { activeCase, loading, progress, error, runAnalysis, pollCase, clearAnalysis } =
    useAnalysisStore();
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [approved, setApproved] = useState(false);
  const [auditHash, setAuditHash] = useState<string | null>(null);
  const [rfiDraft, setRfiDraft] = useState<string | null>(null);
  const [elapsedSec, setElapsedSec] = useState(0);
  const [localError, setLocalError] = useState<string | null>(null);

  const data = activeCase;
  const projectRequirements = project.moduleRequirements ?? {};
  const completedCount = data?.completed_agents?.length ?? 0;
  const analyzing = loading;
  const jurisdictionChecks = data?.jurisdiction_report?.checks ?? [];
  const buildingChecks = data?.building_report?.checks ?? [];
  const fireChecks = buildingChecks.filter((check) => check.category === "fire");
  const buildingOnlyChecks = buildingChecks.filter((check) => check.category !== "fire");
  const siteChecks = [
    ...(data?.site_report?.environmental_checks ?? []),
    ...(data?.site_report?.utility_checks ?? []),
  ];
  const customChecks = data?.custom_rules_report?.checks ?? [];
  const reviewChecks = [
    ...jurisdictionChecks,
    ...buildingOnlyChecks,
    ...fireChecks,
    ...siteChecks,
    ...customChecks,
  ];
  const showAgentPanels = analyzing || !!data;

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

  async function handleRun(modules?: AnalysisModuleKey[]) {
    setLocalError(null);
    setApproved(false);
    setRfiDraft(null);
    clearAnalysis();
    try {
      const result = await runAnalysis(project.id, modules, () => {});
      onAnalysisComplete?.();
      toast.success(`Review complete - ${result.case_summary?.readiness_score ?? "done"}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Review failed";
      setLocalError(msg);
      toast.error(msg);
    }
  }

  async function loadHistoryCase(caseId: string) {
    setSelectedCaseId(caseId);
    setLocalError(null);
    try {
      await pollCase(caseId);
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "Failed to load review");
    }
  }

  async function handleApprove() {
    if (!data?.case_id) return;
    try {
      const res = await approveCase(data.case_id);
      setApproved(true);
      setAuditHash((res.audit_hash as string) ?? auditHash);
      toast.success("Approved for filing");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Approval failed";
      setLocalError(msg);
      toast.error(msg);
    }
  }

  async function handleRfi() {
    if (!data?.case_id) return;
    try {
      const res = await simulateRfi(data.case_id);
      setRfiDraft(res.draft);
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "RFI failed");
    }
  }

  const remainingSec = estimateRemainingSec(elapsedSec, completedCount);
  const displayError = localError || error;
  const runnableModules = ANALYSIS_MODULES.filter(
    (module) => projectRequirements[module.value]?.canRun
  ).map((module) => module.value);
  const isKcmo = project.jurisdiction === "kansas_city_mo";
  const canRunAnything = isKcmo || runnableModules.length > 0;
  const reviewPermits = (project.permits ?? []).filter(
    (permit) => permit.requirementStatus !== "not_required"
  );
  const likelyPermits =
    (data as CaseResults & { likely_permits?: Array<{ permit_name: string; reason?: string; requirement_status?: string }> })
      ?.likely_permits ?? reviewPermits.map((p) => ({
      permit_name: p.permitName,
      reason: p.reason ?? undefined,
      requirement_status: p.requirementStatus,
    }));
  const dataGaps: string[] =
    data?.data_gaps ??
    (data?.case_summary?.human_actions_required ?? []).map((item) =>
      typeof item === "string" ? item : (item as { description?: string }).description ?? String(item)
    );
  const feeEstimate = (data as CaseResults & { fee_estimate?: { estimate_status?: string; warnings?: string[] } })
    ?.fee_estimate;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Permit review</h2>
          <p className="text-sm text-[var(--color-muted)]">
            {isKcmo
              ? "KCMO deterministic pre-screen from structured intake, zoning GIS, and Information Bulletins."
              : "Run AI checks against uploaded documents. These review areas support the permit bundle."}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => handleRun(isKcmo ? runnableModules.length ? runnableModules : ["zoning", "building", "fire", "site"] : runnableModules)}
            disabled={loading || !canRunAnything}
          >
            <Play size={16} />
            {loading ? "Reviewing..." : isKcmo ? "Run KCMO Pre-screen" : "Review All Available"}
          </Button>
          {data && !loading && (
            <Button variant="secondary" onClick={() => downloadAnalysisReport(project, data)}>
              <Download size={16} /> Download Report
            </Button>
          )}
        </div>
      </div>

      {!!data && (
        <section className="space-y-4">
          <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
            <h3 className="mb-3 font-semibold">Likely required permits</h3>
            {likelyPermits.length === 0 ? (
              <p className="text-sm text-[var(--color-muted)]">No permit recommendations in this run.</p>
            ) : (
              <ul className="space-y-3 text-sm">
                {likelyPermits.map((permit, index) => (
                  <li key={`${permit.permit_name}-${index}`} className="rounded-lg border border-[var(--color-border)] p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <strong>{permit.permit_name}</strong>
                      {permit.requirement_status && (
                        <StatusBadge status={permit.requirement_status} />
                      )}
                    </div>
                    {permit.reason && (
                      <p className="mt-1 text-[var(--color-muted)]">{permit.reason}</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-5">
            <h3 className="mb-3 font-semibold">Data gaps</h3>
            {dataGaps.length === 0 ? (
              <p className="text-sm text-[var(--color-muted)]">No open data gaps from this pre-screen.</p>
            ) : (
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {dataGaps.map((gap) => (
                  <li key={gap}>{gap}</li>
                ))}
              </ul>
            )}
          </div>

          {feeEstimate && (
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
              <h3 className="mb-2 font-semibold">Fee estimate</h3>
              <p className="text-sm text-[var(--color-muted)]">
                Status: {feeEstimate.estimate_status ?? "unknown"}. Preliminary only — confirm in CompassKC.
              </p>
              {!!feeEstimate.warnings?.length && (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[var(--color-muted)]">
                  {feeEstimate.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </section>
      )}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {reviewPermits.length > 0 ? (
          reviewPermits.map((permit) => (
            <div
              key={permit.id}
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4"
            >
              <div className="mb-3 flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold">{permit.permitName}</h3>
                  <p className="text-xs text-[var(--color-muted)]">{permit.issuingAuthority}</p>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => handleRun(runnableModules)}
                  disabled={loading || !canRunAnything}
                >
                  <Play size={14} /> Review
                </Button>
              </div>
              {permit.requiredDocuments.length ? (
                <p className="text-xs text-[var(--color-muted)]">
                  Expected docs: {permit.requiredDocuments.slice(0, 4).join(", ")}
                  {permit.requiredDocuments.length > 4 ? "..." : ""}
                </p>
              ) : (
                <p className="text-xs text-[var(--color-muted)]">No document checklist is configured yet.</p>
              )}
              {!canRunAnything && (
                <p className="mt-2 rounded border border-amber-500/70 bg-amber-950 px-2 py-1 text-xs font-medium text-amber-50">
                  Upload at least one relevant document before running review.
                </p>
              )}
            </div>
          ))
        ) : (
          <div className="rounded-xl border border-amber-500/70 bg-amber-950 p-4 text-sm font-medium text-amber-50">
            No permits are in the bundle yet. Confirm project scope in Overview or add a permit from the Permits tab.
          </div>
        )}
      </section>

      {displayError && (
        <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-[var(--color-text)]">
          {displayError}
        </div>
      )}

      {!canRunAnything && (
        <div className="rounded-lg border border-amber-500/70 bg-amber-950 px-4 py-3 text-sm font-medium text-amber-50">
          Upload at least one relevant file before review. Each area will unlock as soon as it
          has enough supporting material.
        </div>
      )}

      {data?.stalled && data.stall_reason && (
        <div className="rounded-lg border border-amber-500/70 bg-amber-950 px-4 py-3 text-sm font-medium text-amber-50">
          {data.stall_reason}
        </div>
      )}

      {loading && progress && (
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <div className="mb-2 flex justify-between text-sm">
            <span>{progress}</span>
            <span className="mono text-[var(--color-muted)]">
              {formatDuration(elapsedSec)} elapsed
              {remainingSec > 0 && ` | ~${formatDuration(remainingSec)} left`}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-[var(--color-surface2)]">
            <div
              className="h-full bg-[var(--color-accent)] transition-all"
              style={{
                width: `${Math.min(100, (completedCount / TOTAL_AGENTS) * 100 + ((elapsedSec % SEC_PER_AGENT) / SEC_PER_AGENT / TOTAL_AGENTS) * 100)}%`,
              }}
            />
          </div>
        </div>
      )}

      {project.analyses.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-medium text-[var(--color-muted)]">Review history</h3>
          <div className="flex flex-wrap gap-2">
            {project.analyses.map((a) => (
              <button
                key={a.caseId}
                type="button"
                onClick={() => loadHistoryCase(a.caseId)}
                className={`rounded-lg border px-3 py-2 text-left text-sm transition ${
                  selectedCaseId === a.caseId || data?.case_id === a.caseId
                    ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10"
                    : "border-[var(--color-border)] hover:bg-[var(--color-surface2)]"
                }`}
              >
                <span className="mono block text-xs text-[var(--color-muted)]">
                  {a.caseId.slice(0, 8)}...
                </span>
                <span className="flex items-center gap-2">
                  {formatDate(a.createdAt)}
                  {a.readiness && <StatusBadge status={a.readiness} />}
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

      {data && (
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-wider text-[var(--color-muted)]">Project</p>
              <h3 className="text-xl font-semibold">{data.brief?.project_name as string}</h3>
              <p className="text-sm text-[var(--color-muted)]">{data.brief?.address as string}</p>
            </div>
            {data.case_summary?.readiness_score && (
              <div className="text-right">
                <p className="text-xs text-[var(--color-muted)]">Readiness</p>
                <StatusBadge status={data.case_summary.readiness_score} />
              </div>
            )}
          </div>

          {data.case_summary?.executive_summary && (
            <p className="mb-4 text-sm text-[var(--color-muted)]">{data.case_summary.executive_summary}</p>
          )}

          {data.permit_package && (
            <div className="mb-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div>
                <p className="text-xs text-[var(--color-muted)]">Est. fees</p>
                <strong>${data.permit_package.total_fees_estimate_usd.toLocaleString()}</strong>
              </div>
              <div>
                <p className="text-xs text-[var(--color-muted)]">Timeline</p>
                <strong>{data.permit_package.estimated_timeline_days} days</strong>
              </div>
              <div>
                <p className="text-xs text-[var(--color-muted)]">Permits</p>
                <strong>{data.permit_package.permits_required.length}</strong>
              </div>
              {data.case_id && (
                <div>
                  <p className="text-xs text-[var(--color-muted)]">Case ID</p>
                  <span className="mono text-sm">{data.case_id.slice(0, 8)}...</span>
                </div>
              )}
            </div>
          )}

          {data.case_summary?.conflicts?.map((c, i) => (
            <div key={i} className="mb-3 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-sm">
              <strong>{c.issue}</strong>
              <p className="text-[var(--color-muted)]">{c.suggested_fix}</p>
            </div>
          ))}

          {data.case_summary && (
            <div className="flex flex-wrap gap-2">
              <Button onClick={handleApprove} disabled={approved}>
                {approved ? "Approved for Filing" : "Approve for Filing"}
              </Button>
              <Button variant="secondary" onClick={handleRfi}>
                Simulate City RFI
              </Button>
            </div>
          )}

          {approved && (
            <p className="mt-3 text-sm text-[var(--color-pass)]">
              Status updated to <strong>APPROVED_FOR_FILING</strong>.
            </p>
          )}
          {auditHash && (
            <p className="mono mt-2 text-xs text-[var(--color-muted)]">
              Audit hash: <code>{auditHash}</code>
            </p>
          )}
        </section>
      )}

      {showAgentPanels && (
        <CheckList
          checks={reviewChecks}
          title="Permit review findings"
          pending={analyzing && reviewChecks.length === 0}
          visible={showAgentPanels}
        />
      )}

      <PermitPackage data={data ?? ({} as CaseResults)} pending={analyzing && !data?.permit_package} />

      {rfiDraft && (
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h3 className="mb-2 font-semibold">Draft RFI response</h3>
          <pre className="mono overflow-x-auto rounded-lg bg-[var(--color-surface2)] p-4 text-xs">{rfiDraft}</pre>
        </section>
      )}
    </div>
  );
}
