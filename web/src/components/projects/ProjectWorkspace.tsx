import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, Info, LoaderCircle, MapPin, Pencil, RefreshCw, Trash2 } from "lucide-react";
import type { AnalysisModuleKey, Project, ProjectScope, ProjectTypeValue } from "../../types";
import {
  ANALYSIS_MODULES,
  DEFAULT_PROJECT_SCOPE,
  FILE_TYPES,
  PROJECT_SCOPE_OPTIONS,
  PROJECT_TYPES,
} from "../../types";
import { Tabs } from "../common/Tabs";
import { Button } from "../common/Button";
import { Input, Select } from "../common/Input";
import { Modal, ConfirmDialog } from "../common/Modal";
import { FileUploader } from "../files/FileUploader";
import { FileList } from "../files/FileList";
import { AnalysisTab } from "../analysis/AnalysisTab";
import { PermitBundleTab } from "../permits/PermitBundleTab";
import { ChecklistTab } from "../checklist/ChecklistTab";
import { Badge } from "../common/Badge";
import { formatDate } from "../../lib/utils";
import { useProjectStore } from "../../stores/projectStore";
import { toast } from "../../stores/toastStore";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "permits", label: "Permits" },
  { id: "checklist", label: "Checklist" },
  { id: "documents", label: "Documents" },
  { id: "review", label: "Review" },
  { id: "activity", label: "Activity" },
];

type ProjectWorkspaceProps = {
  project: Project;
};

export function ProjectWorkspace({ project }: ProjectWorkspaceProps) {
  const navigate = useNavigate();
  const [tab, setTab] = useState("overview");
  const [uploading, setUploading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [editName, setEditName] = useState(project.name);
  const [editAddress, setEditAddress] = useState(project.address);
  const [editType, setEditType] = useState<ProjectTypeValue>(project.projectType);
  const [editScope, setEditScope] = useState<ProjectScope>({
    ...DEFAULT_PROJECT_SCOPE,
    ...(project.scope ?? {}),
  });
  const [uploadType, setUploadType] = useState("other");
  const [uploadLabel, setUploadLabel] = useState("");
  const [uploadSections, setUploadSections] = useState<AnalysisModuleKey[]>([]);
  const [savingEdit, setSavingEdit] = useState(false);
  const [resolvingZoning, setResolvingZoning] = useState(false);
  const {
    uploadFile,
    removeFile,
    updateProject,
    resolveZoning,
    deleteProject,
    fetchProject,
    fetchProjects,
  } = useProjectStore();

  async function handleFiles(files: File[]) {
    setUploading(true);
    try {
      for (const file of files) {
        const ext = file.name.toLowerCase();
        const isBrief = ext.endsWith(".json") || ext.endsWith(".zip");
        await uploadFile(
          project.id,
          file,
          isBrief ? "brief_json" : uploadType,
          isBrief,
          uploadLabel.trim() || undefined,
          uploadSections
        );
      }
      toast.success(`Uploaded ${files.length} file${files.length !== 1 ? "s" : ""}`);
      setUploadLabel("");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleSaveEdit() {
    setSavingEdit(true);
    try {
      await updateProject(project.id, {
        name: editName.trim(),
        address: editAddress.trim(),
        projectType: editType,
        scope: editScope,
      });
      toast.success("Project updated");
      setEditing(false);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to update project");
    } finally {
      setSavingEdit(false);
    }
  }

  async function handleResolveZoning() {
    setResolvingZoning(true);
    try {
      await resolveZoning(project.id);
      toast.success("Address and zoning checked again");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to resolve zoning");
    } finally {
      setResolvingZoning(false);
    }
  }

  function toggleEditScope(key: keyof ProjectScope) {
    setEditScope((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  const permits = project.permits ?? [];
  const activePermits = permits.filter((permit) => permit.requirementStatus !== "not_required");
  const requiredPermits = permits.filter((permit) => permit.requirementStatus === "required");
  const blockedPermits = permits.filter((permit) => permit.lifecycleStatus === "blocked");

  async function handleDelete() {
    setDeleting(true);
    try {
      await deleteProject(project.id);
      toast.success(`Deleted "${project.name}"`);
      navigate("/");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to delete project");
      setDeleting(false);
    }
  }

  return (
    <div>
      <header className="mb-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">{project.name}</h1>
            <p className="text-[var(--color-muted)]">{project.address}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{project.jurisdiction.replace("_", ", ").toUpperCase()}</Badge>
            {project.area && <Badge>Zone {project.area}</Badge>}
            <Badge>{project.projectType.replace(/_/g, " ")}</Badge>
            {project.readinessScore && <Badge variant="ready">{project.readinessScore}</Badge>}
            <Button variant="ghost" size="sm" onClick={() => setEditing(true)} aria-label="Edit project">
              <Pencil size={16} />
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(true)} aria-label="Delete project">
              <Trash2 size={16} />
            </Button>
          </div>
        </div>
      </header>

      {!!project.zoningWarnings?.length && (
        <section className="mb-6 space-y-3" aria-label="Address and zoning warnings">
          {project.zoningWarnings.map((warning) => {
            const isError = warning.severity === "error";
            const WarningIcon = warning.severity === "info" ? Info : AlertTriangle;
            return (
              <div
                key={warning.code}
                className={`flex flex-col gap-3 rounded-xl border px-4 py-3 text-sm sm:flex-row sm:items-start sm:justify-between ${
                  isError
                    ? "border-red-400/40 bg-red-500/10"
                    : "border-amber-400/40 bg-amber-500/10"
                }`}
              >
                <div className="flex gap-3">
                  <WarningIcon
                    size={18}
                    className={isError ? "mt-0.5 shrink-0 text-red-300" : "mt-0.5 shrink-0 text-amber-300"}
                  />
                  <div>
                    <p className="font-medium text-[var(--color-text)]">{warning.message}</p>
                    <p className="mt-1 text-[var(--color-muted)]">{warning.action}</p>
                  </div>
                </div>
                {isError && (
                  <Button size="sm" variant="secondary" onClick={handleResolveZoning} disabled={resolvingZoning}>
                    {resolvingZoning ? (
                      <LoaderCircle size={15} className="animate-spin" />
                    ) : (
                      <RefreshCw size={15} />
                    )}
                    Retry
                  </Button>
                )}
              </div>
            );
          })}
        </section>
      )}

      <Tabs tabs={TABS} active={tab} onChange={setTab} className="mb-6" />

      {tab === "overview" && (
        <div className="grid gap-6 lg:grid-cols-2">
          <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
            <h3 className="mb-4 font-semibold">Project summary</h3>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-[var(--color-muted)]">Created</dt>
                <dd>{formatDate(project.createdAt)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-[var(--color-muted)]">Last updated</dt>
                <dd>{formatDate(project.updatedAt)}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-[var(--color-muted)]">Files</dt>
                <dd>{project.files.length}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-[var(--color-muted)]">Recommended permits</dt>
                <dd>{activePermits.length}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-[var(--color-muted)]">Confirmed required</dt>
                <dd>{requiredPermits.length}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-[var(--color-muted)]">Blocked permits</dt>
                <dd>{blockedPermits.length}</dd>
              </div>
              {project.area && (
                <div className="flex justify-between">
                  <dt className="text-[var(--color-muted)]">Detected district</dt>
                  <dd>{project.area}</dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-[var(--color-muted)]">Reviews run</dt>
                <dd>{project.analyses.length}</dd>
              </div>
            </dl>
          </section>
          <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <h3 className="flex items-center gap-2 font-semibold">
                  <MapPin size={17} /> Detected zoning
                </h3>
                <p className="mt-1 text-xs text-[var(--color-muted)]">
                  Automatically matched from the project address.
                </p>
              </div>
              <Button size="sm" variant="ghost" onClick={handleResolveZoning} disabled={resolvingZoning}>
                {resolvingZoning ? (
                  <LoaderCircle size={15} className="animate-spin" />
                ) : (
                  <RefreshCw size={15} />
                )}
                Check again
              </Button>
            </div>
            {project.zoningProfile?.district ? (
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-[var(--color-muted)]">District</dt>
                  <dd className="text-right font-semibold">{project.zoningProfile.district}</dd>
                </div>
                {project.zoningProfile.districtName && (
                  <div className="flex justify-between gap-4">
                    <dt className="text-[var(--color-muted)]">District name</dt>
                    <dd className="text-right">{project.zoningProfile.districtName}</dd>
                  </div>
                )}
                {project.zoningProfile.landUse && (
                  <div className="flex justify-between gap-4">
                    <dt className="text-[var(--color-muted)]">Mapped land use</dt>
                    <dd className="text-right">{project.zoningProfile.landUse}</dd>
                  </div>
                )}
                <div className="flex justify-between gap-4">
                  <dt className="text-[var(--color-muted)]">Matched address</dt>
                  <dd className="max-w-[70%] text-right">{project.zoningProfile.matchedAddress}</dd>
                </div>
                {project.zoningProfile.matchScore != null && (
                  <div className="flex justify-between gap-4">
                    <dt className="text-[var(--color-muted)]">Address confidence</dt>
                    <dd>{Math.round(project.zoningProfile.matchScore)}%</dd>
                  </div>
                )}
                {project.zoningProfile.ordinance && (
                  <div className="flex justify-between gap-4">
                    <dt className="text-[var(--color-muted)]">Ordinance</dt>
                    <dd>{project.zoningProfile.ordinance}</dd>
                  </div>
                )}
                {project.zoningProfile.sourceUrl && (
                  <div className="border-t border-[var(--color-border)] pt-3">
                    <a
                      href={project.zoningProfile.sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[var(--color-accent)] hover:underline"
                    >
                      {project.zoningProfile.sourceName ?? "Open city zoning source"}
                    </a>
                  </div>
                )}
              </dl>
            ) : (
              <div className="rounded-lg bg-[var(--color-surface2)] px-4 py-3 text-sm text-[var(--color-muted)]">
                No zoning district has been confirmed. Correct the address if needed, then check again.
              </div>
            )}
          </section>
          <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
            <h3 className="mb-4 font-semibold">Timeline</h3>
            <ul className="space-y-3 text-sm">
              <li className="flex gap-3">
                <span className="text-[var(--color-muted)]">Created</span>
                <span>{formatDate(project.createdAt)}</span>
              </li>
              {project.analyses.slice(0, 5).map((a) => (
                <li key={a.caseId} className="flex gap-3">
                  <span className="text-[var(--color-muted)]">Review</span>
                  <span>
                    {formatDate(a.createdAt)} — {a.readiness ?? a.status}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}

      {tab === "permits" && <PermitBundleTab project={project} />}

      {tab === "documents" && (
        <div className="space-y-6">
          <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
            <div className="mb-4 grid gap-4 md:grid-cols-3">
              <Select
                label="File type"
                value={uploadType}
                options={FILE_TYPES.map((t) => ({ value: t.value, label: t.label }))}
                onChange={(e) => setUploadType(e.target.value)}
              />
              <Input
                label="Document label (optional)"
                value={uploadLabel}
                onChange={(e) => setUploadLabel(e.target.value)}
                placeholder="Example: Existing floor plan"
              />
              <div className="text-sm">
                <span className="mb-1.5 block text-[var(--color-muted)]">Supports review areas</span>
                <div className="flex flex-wrap gap-2">
                  {ANALYSIS_MODULES.map((module) => {
                    const active = uploadSections.includes(module.value);
                    return (
                      <button
                        key={module.value}
                        type="button"
                        className={`rounded-lg border px-3 py-2 text-sm ${
                          active
                            ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10"
                            : "border-[var(--color-border)] hover:bg-[var(--color-surface2)]"
                        }`}
                        onClick={() =>
                          setUploadSections((prev) =>
                            active ? prev.filter((m) => m !== module.value) : [...prev, module.value]
                          )
                        }
                      >
                        {module.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>
          <FileUploader onFiles={handleFiles} disabled={uploading} />
          </section>
          <FileList
            files={project.files}
            uploading={uploading}
            onDelete={async (fileId) => {
              try {
                await removeFile(project.id, fileId);
                toast.success("File removed");
              } catch (e) {
                toast.error(e instanceof Error ? e.message : "Failed to remove file");
              }
            }}
          />
        </div>
      )}

      {tab === "checklist" && <ChecklistTab project={project} />}

      {tab === "review" && (
        <AnalysisTab
          project={project}
          onAnalysisComplete={() => {
            fetchProject(project.id);
            fetchProjects();
          }}
        />
      )}

      {tab === "activity" && (
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h3 className="mb-4 font-semibold">Activity</h3>
          <ul className="space-y-3 text-sm">
            <li className="flex gap-3">
              <span className="text-[var(--color-muted)]">Created</span>
              <span>{formatDate(project.createdAt)}</span>
            </li>
            {project.analyses.map((analysis) => (
              <li key={analysis.caseId} className="flex gap-3">
                <span className="text-[var(--color-muted)]">Review</span>
                <span>
                  {formatDate(analysis.createdAt)} - {analysis.readiness ?? analysis.status}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <Modal
        open={editing}
        onClose={() => setEditing(false)}
        title="Edit project"
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditing(false)} disabled={savingEdit}>
              Cancel
            </Button>
            <Button onClick={handleSaveEdit} disabled={savingEdit || !editName.trim() || !editAddress.trim()}>
              {savingEdit ? (
                <>
                  <LoaderCircle size={16} className="animate-spin" />
                  Resolving address and zoning...
                </>
              ) : (
                "Save"
              )}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input label="Project name" value={editName} onChange={(e) => setEditName(e.target.value)} />
          <Input
            label="Full project address"
            value={editAddress}
            onChange={(e) => setEditAddress(e.target.value)}
            placeholder="Street number, city, state, and ZIP code"
          />
          <p className="-mt-2 text-xs text-[var(--color-muted)]">
            Changing the address automatically rechecks the parcel, zoning district, rules, and permit bundle.
          </p>
          <Select
            label="Development type"
            value={editType}
            options={PROJECT_TYPES.map((t) => ({ value: t.value, label: t.label }))}
            onChange={(e) => setEditType(e.target.value as ProjectTypeValue)}
          />
          <div>
            <p className="mb-2 text-sm text-[var(--color-muted)]">Project scope</p>
            <div className="grid max-h-64 gap-2 overflow-y-auto pr-1 sm:grid-cols-2">
              {PROJECT_SCOPE_OPTIONS.map((option) => {
                const key = option.value as keyof ProjectScope;
                return (
                  <label
                    key={option.value}
                    className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-xs transition ${
                      editScope[key]
                        ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-text)]"
                        : "border-[var(--color-border)] text-[var(--color-muted)] hover:bg-[var(--color-surface2)]"
                    }`}
                  >
                    <input
                      type="checkbox"
                      className="accent-[var(--color-accent)]"
                      checked={editScope[key]}
                      onChange={() => toggleEditScope(key)}
                    />
                    {option.label}
                  </label>
                );
              })}
            </div>
          </div>
        </div>
      </Modal>

      <ConfirmDialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={handleDelete}
        title="Delete project"
        message={`Delete "${project.name}"? This removes all files and review history and cannot be undone.`}
        confirmLabel="Delete"
        danger
        loading={deleting}
      />
    </div>
  );
}
