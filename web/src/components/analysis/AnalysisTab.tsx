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
      toast.success(`Analysis complete - ${result.case_summary?.readiness_score ?? "done"}`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Analysis failed";
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
      setLocalError(e instanceof Error ? e.message : "Failed to load analysis");
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
  const canRunAnything = runnableModules.length > 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Analysis</h2>
          <p className="text-sm text-[var(--color-muted)]">
            Run permitting pre-screen against jurisdiction rules and your custom rules.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => handleRun(runnableModules)} disabled={loading || !canRunAnything}>
            <Play size={16} />
            {loading ? "Analyzing..." : "Run All Available"}
          </Button>
          {data && !loading && (
            <Button variant="secondary" onClick={() => downloadAnalysisReport(project, data)}>
              <Download size={16} /> Download Report
            </Button>
          )}
        </div>
      </div>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {ANALYSIS_MODULES.map((module) => {
          const req = projectRequirements[module.value] ?? data?.module_requirements?.[module.value] ?? {
            requiredMissing: [],
            recommendedMissing: [],
            requiredAnyOf: [],
            canRun: false,
            hasMappedFiles: false,
            summary: "",
          };
          return (
            <div key={module.value} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
              <div className="mb-3 flex items-center justify-between gap-2">
                <div>
                  <h3 className="font-semibold">{module.label}</h3>
                  <p className="text-xs text-[var(--color-muted)]">Run this section independently.</p>
                </div>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => handleRun([module.value])}
                  disabled={loading || !req.canRun}
                >
                  <Play size={14} /> Run
                </Button>
              </div>
              {req.summary ? <p className="mb-2 text-xs text-[var(--color-muted)]">{req.summary}</p> : null}
              {req.requiredMissing?.length ? (
                <p className="text-xs text-amber-200">
                  Upload at least one of: {req.requiredMissing.join(", ")}
                </p>
              ) : (
                <p className="text-xs text-emerald-300">
                  Ready to run{req.hasMappedFiles ? " from mapped files" : ""}.
                </p>
              )}
              {req.recommendedMissing?.length ? (
                <p className="mt-2 text-xs text-[var(--color-muted)]">
                  Recommended files: {req.recommendedMissing.join(", ")}
                </p>
              ) : null}
            </div>
          );
        })}
      </section>

      {displayError && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {displayError}
        </div>
      )}

      {!canRunAnything && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
          Upload at least one relevant file before analysis. Each module will unlock as soon as it
          has enough supporting material.
        </div>
      )}

      {data?.stalled && data.stall_reason && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm">
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
          <h3 className="mb-2 text-sm font-medium text-[var(--color-muted)]">Analysis history</h3>
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
        <div className="grid gap-4 lg:grid-cols-2">
          <CheckList
            checks={jurisdictionChecks}
            title="Jurisdiction & zoning"
            pending={analyzing && jurisdictionChecks.length === 0}
            visible={showAgentPanels}
          />
          <CheckList
            checks={buildingOnlyChecks}
            title="Building"
            pending={analyzing && buildingOnlyChecks.length === 0}
            visible={showAgentPanels}
          />
          <CheckList
            checks={fireChecks}
            title="Fire / Life Safety"
            pending={analyzing && fireChecks.length === 0}
            visible={showAgentPanels}
          />
          <CheckList
            checks={siteChecks}
            title="Site & environmental"
            pending={analyzing && siteChecks.length === 0}
            visible={showAgentPanels}
          />
          {customChecks.length > 0 && <CheckList checks={customChecks} title="Custom rules" visible />}
        </div>
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
