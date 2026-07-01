import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Pencil, Trash2 } from "lucide-react";
import type { AnalysisModuleKey, Project, ProjectTypeValue } from "../../types";
import { ANALYSIS_MODULES, FILE_TYPES, PROJECT_TYPES } from "../../types";
import { Tabs } from "../common/Tabs";
import { Button } from "../common/Button";
import { Input, Select } from "../common/Input";
import { Modal, ConfirmDialog } from "../common/Modal";
import { FileUploader } from "../files/FileUploader";
import { FileList } from "../files/FileList";
import { RulesEditor } from "../rules/RulesEditor";
import { AnalysisTab } from "../analysis/AnalysisTab";
import { Badge } from "../common/Badge";
import { formatDate } from "../../lib/utils";
import { useProjectStore } from "../../stores/projectStore";
import { toast } from "../../stores/toastStore";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "files", label: "Files" },
  { id: "rules", label: "Rules" },
  { id: "analysis", label: "Analysis" },
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
  const [editArea, setEditArea] = useState(project.area ?? "");
  const [editType, setEditType] = useState<ProjectTypeValue>(project.projectType);
  const [uploadType, setUploadType] = useState("other");
  const [uploadLabel, setUploadLabel] = useState("");
  const [uploadSections, setUploadSections] = useState<AnalysisModuleKey[]>([]);
  const [savingEdit, setSavingEdit] = useState(false);
  const { uploadFile, removeFile, saveRules, updateProject, deleteProject, fetchProject, fetchProjects } =
    useProjectStore();

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
        area: editArea.trim() || undefined,
        projectType: editType,
      });
      toast.success("Project updated");
      setEditing(false);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to update project");
    } finally {
      setSavingEdit(false);
    }
  }

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
            {project.area && <Badge>{project.area}</Badge>}
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
              {project.area && (
                <div className="flex justify-between">
                  <dt className="text-[var(--color-muted)]">Area / District</dt>
                  <dd>{project.area}</dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-[var(--color-muted)]">Custom rules</dt>
                <dd>{project.customRules.length}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-[var(--color-muted)]">Analyses run</dt>
                <dd>{project.analyses.length}</dd>
              </div>
            </dl>
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
                  <span className="text-[var(--color-muted)]">Analysis</span>
                  <span>
                    {formatDate(a.createdAt)} — {a.readiness ?? a.status}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}

      {tab === "files" && (
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
                <span className="mb-1.5 block text-[var(--color-muted)]">Applies to sections</span>
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
                            : "border-[var(--color-border)]"
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

      {tab === "rules" && (
        <RulesEditor
          projectId={project.id}
          rules={project.customRules}
          onSave={async (rules) => {
            await saveRules(project.id, rules);
          }}
          area={project.area ?? ""}
        />
      )}

      {tab === "analysis" && (
        <AnalysisTab
          project={project}
          onAnalysisComplete={() => {
            fetchProject(project.id);
            fetchProjects();
          }}
        />
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
              {savingEdit ? "Saving…" : "Save"}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <Input label="Project name" value={editName} onChange={(e) => setEditName(e.target.value)} />
          <Input label="Address" value={editAddress} onChange={(e) => setEditAddress(e.target.value)} />
          <Input label="Area / District" value={editArea} onChange={(e) => setEditArea(e.target.value)} />
          <Select
            label="Project type"
            value={editType}
            options={PROJECT_TYPES.map((t) => ({ value: t.value, label: t.label }))}
            onChange={(e) => setEditType(e.target.value as ProjectTypeValue)}
          />
        </div>
      </Modal>

      <ConfirmDialog
        open={confirmDelete}
        onClose={() => setConfirmDelete(false)}
        onConfirm={handleDelete}
        title="Delete project"
        message={`Delete "${project.name}"? This removes all files and analysis history and cannot be undone.`}
        confirmLabel="Delete"
        danger
        loading={deleting}
      />
    </div>
  );
}
