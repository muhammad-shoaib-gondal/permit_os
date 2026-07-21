import { useEffect, useState } from "react";
import { CheckCircle2, CircleAlert, CircleX, Download, Play } from "lucide-react";
import { ANALYSIS_MODULES } from "../../types";
import type { AnalysisModuleKey, CaseResults, Project, ProjectFile, ProjectPermit } from "../../types";
import { approveCase, simulateRfi } from "../../api";
import { useAnalysisStore } from "../../stores/projectStore";
import { toast } from "../../stores/toastStore";
import { Button } from "../common/Button";
import { CheckList } from "./CheckList";
import { PermitPackage } from "./PermitPackage";
import { StatusBadge } from "./StatusBadge";
import { downloadAnalysisReport } from "../../lib/pdfExport";
import { formatDate } from "../../lib/utils";

const SEC_PER_REVIEW_STAGE = 120;
const TOTAL_REVIEW_STAGES = 4;

const REQUIREMENT_TYPE_HINTS: Array<[string[], string[]]> = [
  [["fire", "sprinkler", "alarm", "life safety"], ["fire_protection_plan", "fire_plan"]],
  [["mechanical", "hvac"], ["mechanical_plan"]],
  [["plumbing"], ["plumbing_plan"]],
  [["electrical", "lighting", "power"], ["electrical_plan"]],
  [["structural", "foundation", "framing"], ["structural_plan"]],
  [["survey", "plat"], ["survey"]],
  [["civil", "utility", "grading", "stormwater"], ["civil_plan", "site_plan"]],
  [["site"], ["site_plan", "civil_plan", "survey"]],
  [["elevation"], ["elevation", "architectural_plan"]],
  [["architectural", "floor", "drawing", "plan set", "building plan", "construction plan", "parent plan"], ["architectural_plan", "floor_plan"]],
  [["code analysis", "code summary"], ["code_analysis"]],
  [["energy", "comcheck"], ["energy_document"]],
  [["application", "form"], ["application_form"]],
  [["authorization", "affidavit", "supporting"], ["supporting_document"]],
];

const REQUIREMENT_STOP_WORDS = new Set([
  "and", "building", "construction", "document", "documents", "drawing", "drawings",
  "existing", "final", "permit", "plan", "plans", "project", "required", "signed", "the",
]);

function documentMatchesRequirement(file: ProjectFile, requirement: string): boolean {
  const normalized = requirement.toLowerCase();
  const expectedTypes = REQUIREMENT_TYPE_HINTS.find(([hints]) =>
    hints.some((hint) => normalized.includes(hint))
  )?.[1] ?? [];
  if (expectedTypes.includes(file.type)) return true;

  const searchable = `${file.name} ${file.label ?? ""} ${file.aiSummary ?? ""}`.toLowerCase();
  const terms = normalized
    .split(/[^a-z0-9]+/)
    .filter((term) => term.length > 3 && !REQUIREMENT_STOP_WORDS.has(term));
  return terms.some((term) => searchable.includes(term));
}

function permitDocumentState(permit: ProjectPermit, files: ProjectFile[]) {
  const requirements = permit.requiredDocuments ?? [];
  const matches = requirements.map((requirement) => ({
    requirement,
    files: files.filter((file) => documentMatchesRequirement(file, requirement)),
  }));
  const linkedFiles = files.filter((file) => file.permitTypes?.includes(permit.permitType));
  const found = matches.filter((item) => item.files.length > 0);
  const missing = matches.filter((item) => item.files.length === 0);
  return {
    requirements,
    found,
    missing,
    canRun: requirements.length > 0 ? found.length > 0 : linkedFiles.length > 0 || files.length > 0,
  };
}

function formatDuration(totalSec: number): string {
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function estimateRemainingSec(elapsed: number, completedCount: number): number {
  const stagesLeft = Math.max(0, TOTAL_REVIEW_STAGES - completedCount);
  if (stagesLeft === 0) return 0;
  const budget = stagesLeft * SEC_PER_REVIEW_STAGE;
  const spentOnCurrent = elapsed - completedCount * SEC_PER_REVIEW_STAGE;
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
  const completedCount = data?.completed_sections?.length ?? 0;
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
  const showReviewPanels = analyzing || !!data;

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

  async function handleRun(modules?: AnalysisModuleKey[], permitTypes?: string[]) {
    setLocalError(null);
    setApproved(false);
    setRfiDraft(null);
    clearAnalysis();
    try {
      const result = await runAnalysis(project.id, modules, permitTypes, () => {});
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
  const reviewPermits = (project.permits ?? []).filter(
    (permit) => permit.requirementStatus !== "not_required"
  );
  const permitStates = new Map(
    reviewPermits.map((permit) => [permit.id, permitDocumentState(permit, project.files)])
  );
  const eligiblePermitTypes = reviewPermits
    .filter((permit) => permitStates.get(permit.id)?.canRun)
    .map((permit) => permit.permitType);
  const canRunAnything = runnableModules.length > 0 && eligiblePermitTypes.length > 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Permit review</h2>
          <p className="text-sm text-[var(--color-muted)]">
            Run AI checks against the documents connected to each permit.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={() => handleRun(runnableModules, eligiblePermitTypes)}
            disabled={loading || !canRunAnything}
          >
            <Play size={16} />
            {loading ? "Reviewing..." : "Review All Available"}
          </Button>
          {data && !loading && (
            <Button variant="secondary" onClick={() => downloadAnalysisReport(project, data)}>
              <Download size={16} /> Download Report
            </Button>
          )}
        </div>
      </div>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {reviewPermits.length > 0 ? (
          reviewPermits.map((permit) => {
            const documentState = permitStates.get(permit.id)!;
            return (
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
                  onClick={() => handleRun(runnableModules, [permit.permitType])}
                  disabled={loading || !documentState.canRun || runnableModules.length === 0}
                >
                  <Play size={14} /> Review
                </Button>
              </div>
              {documentState.requirements.length ? (
                <details className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface2)]">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2 text-sm font-medium">
                    <span>Required documents</span>
                    <span className="text-xs text-[var(--color-muted)]">
                      {documentState.found.length}/{documentState.requirements.length} found
                    </span>
                  </summary>
                  <ul className="space-y-2 border-t border-[var(--color-border)] px-3 py-3">
                    {documentState.found.map((item) => (
                      <li key={item.requirement} className="flex items-start gap-2 text-xs">
                        <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-[var(--color-pass)]" />
                        <span>{item.requirement}</span>
                      </li>
                    ))}
                    {documentState.missing.map((item) => (
                      <li key={item.requirement} className="flex items-start gap-2 text-xs text-[var(--color-muted)]">
                        <CircleX size={14} className="mt-0.5 shrink-0" />
                        <span>{item.requirement} - not found</span>
                      </li>
                    ))}
                  </ul>
                </details>
              ) : (
                <p className="text-xs text-[var(--color-muted)]">No required-document checklist is configured.</p>
              )}
              {!documentState.canRun && (
                <p className="mt-3 rounded-lg bg-[#f00000] px-3 py-2 text-xs font-semibold text-white">
                  Documents not found
                </p>
              )}
            </div>
            );
          })
        ) : (
          <div className="rounded-xl border border-amber-500/70 bg-amber-950 p-4 text-sm font-medium text-amber-50">
            No permits are in the bundle yet. Confirm project scope in Overview or add a permit from the Permits tab.
          </div>
        )}
      </section>

      {displayError && (
        <div
          role="alert"
          className="flex items-start gap-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 shadow-sm"
        >
          <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-[var(--color-surface2)] text-[var(--color-accent)]">
            <CircleAlert size={18} />
          </span>
          <div className="min-w-0">
            <p className="text-sm font-semibold text-[var(--color-text)]">Review could not run</p>
            <p className="mt-1 text-sm leading-5 text-[var(--color-muted)]">{displayError}</p>
          </div>
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
                width: `${Math.min(100, (completedCount / TOTAL_REVIEW_STAGES) * 100 + ((elapsedSec % SEC_PER_REVIEW_STAGE) / SEC_PER_REVIEW_STAGE / TOTAL_REVIEW_STAGES) * 100)}%`,
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

      {showReviewPanels && (
        <CheckList
          checks={reviewChecks}
          title="Permit review findings"
          pending={analyzing && reviewChecks.length === 0}
          visible={showReviewPanels}
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
