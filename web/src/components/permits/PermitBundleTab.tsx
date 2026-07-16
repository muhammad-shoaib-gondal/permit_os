import { useState } from "react";
import { CheckCircle2, ExternalLink, Plus, XCircle } from "lucide-react";
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
import { PermitReviewRules } from "./PermitReviewRules";

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
  const { createPermit, updatePermit } = useProjectStore();
  const [savingId, setSavingId] = useState<string | null>(null);
  const [manualOpen, setManualOpen] = useState(false);
  const [manualName, setManualName] = useState("");
  const [manualAuthority, setManualAuthority] = useState("Kansas City, Missouri");
  const [manualDocs, setManualDocs] = useState("");
  const [manualReason, setManualReason] = useState("");
  const [manualSaving, setManualSaving] = useState(false);
  const [openReviewIds, setOpenReviewIds] = useState<Set<string>>(new Set());

  const permits = project.permits ?? [];
  const activePermits = permits.filter((permit) => permit.requirementStatus !== "not_required");
  const requiredCount = permits.filter((permit) => permit.requirementStatus === "required").length;
  const submittedCount = permits.filter((permit) =>
    ["submitted", "application_accepted", "in_review", "approved", "issued", "finaled"].includes(
      permit.lifecycleStatus
    )
  ).length;
  const notApplicableCount = permits.filter((permit) => permit.requirementStatus === "not_required").length;

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
      setManualAuthority("Kansas City, Missouri");
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
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Recommended</p>
          <strong className="text-2xl">{activePermits.length}</strong>
        </div>
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Confirmed required</p>
          <strong className="text-2xl">{requiredCount}</strong>
        </div>
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Submitted or later</p>
          <strong className="text-2xl">{submittedCount}</strong>
        </div>
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <p className="text-xs uppercase tracking-wide text-[var(--color-muted)]">Not applicable</p>
          <strong className="text-2xl">{notApplicableCount}</strong>
        </div>
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
          No permit recommendations yet. For KCMO, set the jurisdiction to Kansas City, MO and select the project scope.
        </div>
      )}

      <section className="space-y-4">
        {permits.map((permit) => (
          <article
            key={permit.id}
            className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5"
          >
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <h3 className="text-base font-semibold">{permit.permitName}</h3>
                  <Badge variant={statusVariant(permit.requirementStatus)}>
                    {labelFor(requirementLabels, permit.requirementStatus)}
                  </Badge>
                  <Badge variant={statusVariant(permit.lifecycleStatus)}>
                    {labelFor(lifecycleLabels, permit.lifecycleStatus)}
                  </Badge>
                  <Badge>{permit.origin}</Badge>
                </div>
                <p className="text-sm text-[var(--color-muted)]">{permit.issuingAuthority || "Authority not set"}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={savingId === permit.id || permit.requirementStatus === "required"}
                  onClick={() =>
                    savePermit(
                      permit,
                      { requirementStatus: "required", lifecycleStatus: "gathering_documents" },
                      "Permit confirmed as required"
                    )
                  }
                >
                  <CheckCircle2 size={14} /> Confirm
                </Button>
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
              </div>
            </div>

            <details
              className="mb-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface2)]"
              onToggle={(event) => {
                const isOpen = event.currentTarget.open;
                setOpenReviewIds((current) => {
                  const next = new Set(current);
                  if (isOpen) next.add(permit.id);
                  else next.delete(permit.id);
                  return next;
                });
              }}
            >
              <summary className="cursor-pointer list-none px-4 py-3 text-sm font-medium">
                Review checks
              </summary>
              <div className="border-t border-[var(--color-border)] p-4">
                {openReviewIds.has(permit.id) && <PermitReviewRules project={project} permit={permit} />}
              </div>
            </details>

            <details className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface2)]">
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
                placeholder="CompassKC number"
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

            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface2)] p-3">
                <p className="mb-2 text-xs uppercase tracking-wide text-[var(--color-muted)]">Required documents</p>
                <pre className="whitespace-pre-wrap text-sm text-[var(--color-text)]">
                  {documentText(permit.requiredDocuments)}
                </pre>
              </div>
              <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface2)] p-3 text-sm">
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
          </article>
        ))}
      </section>
    </div>
  );
}
