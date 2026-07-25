import { useState } from "react";
import { CheckCircle2, ChevronRight, CircleAlert, ExternalLink, Minimize2, Plus, XCircle } from "lucide-react";
import type { Project, ProjectPermit } from "../../types";
import {
  PERMIT_LIFECYCLE_STATUS_OPTIONS,
  PERMIT_REQUIREMENT_STATUS_OPTIONS,
} from "../../types";
import { useProjectStore } from "../../stores/projectStore";
import { toast } from "../../stores/toastStore";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";
import { Input, Select } from "../common/Input";
import { Modal } from "../common/Modal";
import { PermitReviewRules } from "./PermitReviewRules";
import { jurisdictionAuthority, jurisdictionLabel } from "../../lib/jurisdictions";

type PermitBundleTabProps = {
  project: Project;
};

const requirementLabels = Object.fromEntries(
  PERMIT_REQUIREMENT_STATUS_OPTIONS.map((option) => [option.value, option.label])
);
const lifecycleLabels = Object.fromEntries(
  PERMIT_LIFECYCLE_STATUS_OPTIONS.map((option) => [option.value, option.label])
);

function statusVariant(status: string): "default" | "pass" | "fail" | "warn" | "ready" {
  if (["required", "approved", "issued", "finaled", "ready_to_submit"].includes(status)) {
    return "pass";
  }
  if (["blocked", "corrections_requested", "expired"].includes(status)) {
    return "fail";
  }
  if (["suggested", "likely_required", "needs_confirmation", "gathering_documents"].includes(status)) {
    return "warn";
  }
  if (["submitted", "in_review", "ready_for_human_review"].includes(status)) {
    return "ready";
  }
  return "default";
}

function labelFor(map: Record<string, string>, value: string) {
  return map[value] ?? value.replace(/_/g, " ");
}

function documentText(documents: string[]) {
  if (!documents.length) return "No required documents listed yet.";
  return documents.join("\n");
}

export function PermitBundleTab({ project }: PermitBundleTabProps) {
  const { createPermit, updatePermit, updateProject } = useProjectStore();
  const [savingId, setSavingId] = useState<string | null>(null);
  const [manualOpen, setManualOpen] = useState(false);
  const [manualName, setManualName] = useState("");
  const [manualAuthority, setManualAuthority] = useState(jurisdictionAuthority(project.jurisdiction));
  const [manualDocs, setManualDocs] = useState("");
  const [manualReason, setManualReason] = useState("");
  const [manualSaving, setManualSaving] = useState(false);
  const [expandedPermitId, setExpandedPermitId] = useState<string | null>(null);
  const [reviewPermit, setReviewPermit] = useState<ProjectPermit | null>(null);
  const [answeringKey, setAnsweringKey] = useState<string | null>(null);

  const permits = project.permits ?? [];
  const activePermits = permits.filter((permit) => permit.requirementStatus !== "not_required");
  const requiredPermits = activePermits.filter((permit) => permit.requirementStatus === "required");
  const recommendedPermits = activePermits.filter((permit) => permit.requirementStatus !== "required");
  const notRequiredPermits = permits.filter((permit) => permit.requirementStatus === "not_required");
  const submittedCount = permits.filter((permit) =>
    ["submitted", "application_accepted", "in_review", "approved", "issued", "finaled"].includes(
      permit.lifecycleStatus
    )
  ).length;
  const notApplicableCount = permits.filter((permit) => permit.requirementStatus === "not_required").length;

  function scrollToPermitGroup(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function savePermit(permit: ProjectPermit, data: Partial<ProjectPermit>, success: string) {
    setSavingId(permit.id);
    try {
      await updatePermit(project.id, permit.id, data);
      toast.success(success);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to update permit");
    } finally {
      setSavingId(null);
    }
  }

  async function addManualPermit() {
    if (!manualName.trim()) return;
    setManualSaving(true);
    try {
      await createPermit(project.id, {
        permitName: manualName.trim(),
        issuingAuthority: manualAuthority.trim(),
        requirementStatus: "required",
        lifecycleStatus: "gathering_documents",
        reason: manualReason.trim() || "Manually added by user.",
        requiredDocuments: manualDocs
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean),
      });
      setManualName("");
      setManualAuthority(jurisdictionAuthority(project.jurisdiction));
      setManualDocs("");
      setManualReason("");
      setManualOpen(false);
      toast.success("Permit added");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to add permit");
    } finally {
      setManualSaving(false);
    }
  }

  async function answerPermitQuestion(key: string, value: boolean | number | string) {
    setAnsweringKey(key);
    try {
      await updateProject(project.id, {
        permitAnswers: { ...(project.permitAnswers ?? {}), [key]: value },
      });
      toast.success("Permit information saved");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to save permit information");
    } finally {
      setAnsweringKey(null);
    }
  }

  const permitGroups = [
    {
      id: "required-permits",
      title: "Required permits",
      description: "Confirmed permits to prepare and track for this project.",
      permits: requiredPermits,
      emptyMessage: "No permits have been confirmed as required yet.",
    },
    {
      id: "recommended-permits",
      title: "Needs information",
      description: "Potential approvals that need a project-specific answer before classification.",
      permits: recommendedPermits,
      emptyMessage: "No permit questions are waiting for an answer.",
    },
    {
      id: "not-required-permits",
      title: "Not required",
      description: "Approvals reviewed and excluded using confirmed project information.",
      permits: notRequiredPermits,
      emptyMessage: "No approvals have been excluded yet.",
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Permit bundle</h2>
          <p className="text-sm text-[var(--color-muted)]">
            Work permit-by-permit. EstatePermit recommends the bundle from jurisdiction, development type, and scope.
          </p>
        </div>
        <Button variant="secondary" onClick={() => setManualOpen((open) => !open)}>
          <Plus size={16} /> Add permit
        </Button>
      </div>

      <section className="grid gap-4 md:grid-cols-4">
        <button
          type="button"
          onClick={() => scrollToPermitGroup("required-permits")}
          className="group cursor-pointer rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-left transition hover:border-[var(--color-accent)]/60 hover:bg-[var(--color-surface2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
        >
          <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Required</p>
          <div className="mt-1 flex items-center justify-between">
            <strong className="text-2xl">{requiredPermits.length}</strong>
            <ChevronRight size={18} className="text-[var(--color-muted)] transition group-hover:translate-y-0.5 group-hover:rotate-90" />
          </div>
        </button>
        <button
          type="button"
          onClick={() => scrollToPermitGroup("recommended-permits")}
          className="group cursor-pointer rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-left transition hover:border-[var(--color-accent)]/60 hover:bg-[var(--color-surface2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
        >
          <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Needs information</p>
          <div className="mt-1 flex items-center justify-between">
            <strong className="text-2xl">{recommendedPermits.length}</strong>
            <ChevronRight size={18} className="text-[var(--color-muted)] transition group-hover:translate-y-0.5 group-hover:rotate-90" />
          </div>
        </button>
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Submitted or later</p>
          <strong className="text-2xl">{submittedCount}</strong>
        </div>
        <button
          type="button"
          onClick={() => scrollToPermitGroup("not-required-permits")}
          className="group cursor-pointer rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 text-left transition hover:border-[var(--color-accent)]/60 hover:bg-[var(--color-surface2)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent)]"
        >
          <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Not applicable</p>
          <div className="mt-1 flex items-center justify-between">
            <strong className="text-2xl">{notApplicableCount}</strong>
            <ChevronRight size={18} className="text-[var(--color-muted)] transition group-hover:translate-y-0.5 group-hover:rotate-90" />
          </div>
        </button>
      </section>

      {manualOpen && (
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h3 className="mb-4 font-semibold">Add missing permit</h3>
          <div className="grid gap-4 md:grid-cols-2">
            <Input
              label="Permit name"
              value={manualName}
              onChange={(event) => setManualName(event.target.value)}
              placeholder="Example: Elevator permit"
            />
            <Input
              label="Issuing authority"
              value={manualAuthority}
              onChange={(event) => setManualAuthority(event.target.value)}
            />
          </div>
          <label className="mt-4 flex flex-col gap-1.5 text-sm">
            <span className="text-[var(--color-muted)]">Why this permit is needed</span>
            <textarea
              className="min-h-20 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
              value={manualReason}
              onChange={(event) => setManualReason(event.target.value)}
              placeholder="Short explanation or source."
            />
          </label>
          <label className="mt-4 flex flex-col gap-1.5 text-sm">
            <span className="text-[var(--color-muted)]">Required documents, one per line</span>
            <textarea
              className="min-h-24 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
              value={manualDocs}
              onChange={(event) => setManualDocs(event.target.value)}
              placeholder="Plan set&#10;Site plan&#10;Owner authorization"
            />
          </label>
          <div className="mt-4 flex gap-2">
            <Button onClick={addManualPermit} disabled={manualSaving || !manualName.trim()}>
              {manualSaving ? "Adding..." : "Add permit"}
            </Button>
            <Button variant="ghost" onClick={() => setManualOpen(false)} disabled={manualSaving}>
              Cancel
            </Button>
          </div>
        </section>
      )}

      {permits.length === 0 && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-[var(--color-text)]">
          No permit recommendations yet. Confirm {jurisdictionLabel(project.jurisdiction)} and select the project scope.
        </div>
      )}

      {permitGroups.map((group) => (
        <section
          key={group.id}
          id={group.id}
          className="scroll-mt-6 rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4 sm:p-5"
        >
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold">{group.title}</h2>
              <p className="mt-1 text-sm text-[var(--color-muted)]">{group.description}</p>
            </div>
            <Badge>{group.permits.length}</Badge>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {group.permits.length === 0 && (
              <p className="rounded-xl border border-dashed border-[var(--color-border)] px-4 py-6 text-sm text-[var(--color-muted)] sm:col-span-2 xl:col-span-3">
                {group.emptyMessage}
              </p>
            )}
            {group.permits.map((permit) => {
          const expanded = expandedPermitId === permit.id;
          const matchedDocuments = project.files.filter((file) =>
            file.permitTypes?.includes(permit.permitType)
          );
          if (!expanded) {
            const RequiredIcon = permit.requirementStatus === "required" ? CheckCircle2 : CircleAlert;
            return (
              <article
                key={permit.id}
                className="flex min-h-28 flex-col rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] transition hover:border-[var(--color-accent)]/60 hover:bg-[var(--color-surface2)]"
              >
                <button
                  type="button"
                  onClick={() => setExpandedPermitId(permit.id)}
                  className="group flex flex-1 cursor-pointer items-start justify-between gap-4 rounded-xl p-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--color-accent)]"
                  aria-label={`Open ${permit.permitName}`}
                >
                  <div className="flex min-w-0 items-start gap-3">
                    <RequiredIcon
                      size={19}
                      className={
                        permit.requirementStatus === "required"
                          ? "mt-0.5 shrink-0 text-[var(--color-pass)]"
                          : "mt-0.5 shrink-0 text-[var(--color-warn)]"
                      }
                      role="img"
                      aria-label={labelFor(requirementLabels, permit.requirementStatus)}
                    />
                    <h3 className="line-clamp-3 text-sm font-semibold leading-5 text-[var(--color-text)]">
                      {permit.permitName}
                    </h3>
                  </div>
                  <ChevronRight
                    size={17}
                    className="mt-0.5 shrink-0 text-[var(--color-muted)] transition group-hover:translate-x-0.5 group-hover:text-[var(--color-accent)]"
                    aria-hidden="true"
                  />
                </button>
              </article>
            );
          }

          return (
            <article
              key={permit.id}
              className="rounded-xl border border-[var(--color-accent)]/50 bg-[var(--color-surface)] p-5 shadow-lg shadow-black/10 sm:col-span-2 xl:col-span-3"
            >
              <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <h3 className="text-lg font-semibold">{permit.permitName}</h3>
                    <Badge variant={statusVariant(permit.requirementStatus)}>
                      {labelFor(requirementLabels, permit.requirementStatus)}
                    </Badge>
                    <Badge variant={statusVariant(permit.lifecycleStatus)}>
                      {labelFor(lifecycleLabels, permit.lifecycleStatus)}
                    </Badge>
                    <Badge>{permit.origin}</Badge>
                  </div>
                  <p className="text-sm text-[var(--color-muted)]">
                    {permit.issuingAuthority || "Authority not set"}
                  </p>
                  {permit.reason && <p className="mt-2 max-w-4xl text-sm text-[var(--color-muted)]">{permit.reason}</p>}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="secondary" onClick={() => setReviewPermit(permit)}>
                    Review checks
                  </Button>
                  {permit.origin === "manual" && permit.requirementStatus !== "required" && (
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={savingId === permit.id}
                      onClick={() =>
                        savePermit(
                          permit,
                          { requirementStatus: "required", lifecycleStatus: "gathering_documents" },
                          "Permit moved to required"
                        )
                      }
                    >
                      <CheckCircle2 size={14} /> {savingId === permit.id ? "Saving..." : "Mark required"}
                    </Button>
                  )}
                  {permit.origin === "manual" && (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={savingId === permit.id || permit.requirementStatus === "not_required"}
                      onClick={() =>
                        savePermit(
                          permit,
                          { requirementStatus: "not_required", lifecycleStatus: "not_started" },
                          "Permit marked not applicable"
                        )
                      }
                    >
                      <XCircle size={14} /> Not applicable
                    </Button>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => setExpandedPermitId(null)}>
                    <Minimize2 size={14} /> Close details
                  </Button>
                </div>
              </div>

              {!!permit.recommendationEvidence?.questions?.length && (
                <section className="mb-5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface2)] p-4">
                  <div className="mb-3">
                    <h4 className="font-semibold">Information needed for this approval</h4>
                    <p className="mt-1 text-sm text-[var(--color-muted)]">
                      EstatePermit recalculates this approval immediately after each answer.
                    </p>
                  </div>
                  <div className="space-y-4">
                    {permit.recommendationEvidence.questions.map((question) => {
                      const savedAnswer = project.permitAnswers?.[question.key] ?? question.answer;
                      if (question.type === "boolean") {
                        return (
                          <div key={question.key} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                            <p className="text-sm font-medium">{question.label}</p>
                            {question.help && <p className="mt-1 text-xs text-[var(--color-muted)]">{question.help}</p>}
                            <div className="mt-3 flex flex-wrap gap-2">
                              <Button
                                size="sm"
                                variant={savedAnswer === true ? "primary" : "secondary"}
                                disabled={answeringKey === question.key}
                                onClick={() => answerPermitQuestion(question.key, true)}
                              >
                                Yes
                              </Button>
                              <Button
                                size="sm"
                                variant={savedAnswer === false ? "primary" : "secondary"}
                                disabled={answeringKey === question.key}
                                onClick={() => answerPermitQuestion(question.key, false)}
                              >
                                No
                              </Button>
                              {savedAnswer === undefined || savedAnswer === null ? (
                                <Badge>Not answered</Badge>
                              ) : null}
                            </div>
                          </div>
                        );
                      }
                      return (
                        <div key={question.key} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
                          <Input
                            key={`${question.key}-${String(savedAnswer ?? "")}`}
                            label={`${question.label}${question.unit ? ` (${question.unit})` : ""}`}
                            type={question.type === "number" ? "number" : "text"}
                            defaultValue={String(savedAnswer ?? "")}
                            disabled={answeringKey === question.key}
                            onBlur={(event) => {
                              const raw = event.target.value.trim();
                              if (!raw || raw === String(savedAnswer ?? "")) return;
                              answerPermitQuestion(
                                question.key,
                                question.type === "number" ? Number(raw) : raw
                              );
                            }}
                          />
                          {question.help && <p className="mt-1 text-xs text-[var(--color-muted)]">{question.help}</p>}
                        </div>
                      );
                    })}
                  </div>
                </section>
              )}

              <div className="grid gap-4 lg:grid-cols-3">
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface2)] p-4">
                  <p className="mb-2 text-xs uppercase tracking-wide text-[var(--color-muted)]">Required documents</p>
                  <pre className="whitespace-pre-wrap font-sans text-sm text-[var(--color-text)]">
                    {documentText(permit.requiredDocuments)}
                  </pre>
                </div>
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface2)] p-4">
                  <p className="mb-2 text-xs uppercase tracking-wide text-[var(--color-muted)]">Matched documents</p>
                  {matchedDocuments.length ? (
                    <ul className="space-y-2 text-sm">
                      {matchedDocuments.map((file) => (
                        <li key={file.id}>
                          <span className="font-medium">{file.name}</span>
                          {file.aiSummary && (
                            <p className="mt-0.5 line-clamp-2 text-xs text-[var(--color-muted)]">{file.aiSummary}</p>
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-[var(--color-muted)]">No uploaded documents matched to this permit yet.</p>
                  )}
                </div>
                <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface2)] p-4 text-sm">
                  <p className="mb-2 text-xs uppercase tracking-wide text-[var(--color-muted)]">Filing details</p>
                  <div className="space-y-2 text-[var(--color-muted)]">
                    <p>Dependencies: {permit.dependencies.length ? permit.dependencies.join(", ") : "None listed"}</p>
                    <p>Estimated fee: {permit.estimatedFeeUsd ? `$${permit.estimatedFeeUsd.toLocaleString()}` : "Not listed"}</p>
                    {permit.portalUrl && (
                      <a
                        className="inline-flex cursor-pointer items-center gap-1 text-[var(--color-accent)] hover:underline"
                        href={permit.portalUrl}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open portal <ExternalLink size={13} />
                      </a>
                    )}
                  </div>
                </div>
              </div>

              <details className="mt-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface2)]">
                <summary className="cursor-pointer list-none px-4 py-3 text-sm font-medium">
                  Permit tracking
                </summary>
                <div className="border-t border-[var(--color-border)] p-4">
                  <p className="mb-4 text-sm text-[var(--color-muted)]">
                    These fields are maintained by your team. EstatePermit does not automatically confirm city portal status, assignments, or application numbers.
                  </p>
                  <div className="grid gap-4 lg:grid-cols-3">
                    <Select
                      label="City filing status"
                      value={permit.lifecycleStatus}
                      options={PERMIT_LIFECYCLE_STATUS_OPTIONS.map((option) => ({
                        value: option.value,
                        label: option.label,
                      }))}
                      disabled={savingId === permit.id}
                      onChange={(event) =>
                        savePermit(permit, { lifecycleStatus: event.target.value }, "Lifecycle updated")
                      }
                    />
                    <Input
                      label="Internal owner"
                      defaultValue={permit.assignedEmployee ?? ""}
                      placeholder="Internal owner"
                      onBlur={(event) =>
                        event.target.value !== (permit.assignedEmployee ?? "") &&
                        savePermit(permit, { assignedEmployee: event.target.value }, "Owner updated")
                      }
                    />
                    <Input
                      label="Responsible consultant / contractor"
                      defaultValue={permit.assignedContractor ?? ""}
                      placeholder="Architect, MEP, GC..."
                      onBlur={(event) =>
                        event.target.value !== (permit.assignedContractor ?? "") &&
                        savePermit(permit, { assignedContractor: event.target.value }, "Contractor updated")
                      }
                    />
                    <Input
                      label="Application number"
                      defaultValue={permit.applicationNumber ?? ""}
                      placeholder={project.jurisdiction === "kansas_city_mo" ? "CompassKC number" : "UG application number"}
                      onBlur={(event) =>
                        event.target.value !== (permit.applicationNumber ?? "") &&
                        savePermit(permit, { applicationNumber: event.target.value }, "Application number updated")
                      }
                    />
                    <Input
                      label="Current blocker (if any)"
                      defaultValue={permit.currentBlocker ?? ""}
                      placeholder="Missing signed/sealed drawings"
                      onBlur={(event) =>
                        event.target.value !== (permit.currentBlocker ?? "") &&
                        savePermit(permit, { currentBlocker: event.target.value }, "Blocker updated")
                      }
                    />
                    <Input
                      label="Next action"
                      defaultValue={permit.nextAction ?? ""}
                      placeholder="Collect documents, submit, respond..."
                      onBlur={(event) =>
                        event.target.value !== (permit.nextAction ?? "") &&
                        savePermit(permit, { nextAction: event.target.value }, "Next action updated")
                      }
                    />
                  </div>
                </div>
              </details>
            </article>
          );
            })}
          </div>
        </section>
      ))}

      <Modal
        open={Boolean(reviewPermit)}
        onClose={() => setReviewPermit(null)}
        title={reviewPermit ? `Review checks — ${reviewPermit.permitName}` : "Review checks"}
        size="full"
      >
        {reviewPermit && <PermitReviewRules project={project} permit={reviewPermit} />}
      </Modal>
    </div>
  );
}
