import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listJurisdictions } from "../api";
import { PROJECT_TYPES } from "../types";
import type { Jurisdiction, ProjectTypeValue } from "../types";
import { useProjectStore } from "../stores/projectStore";
import { toast } from "../stores/toastStore";
import { Button } from "../components/common/Button";
import { Input, Select } from "../components/common/Input";
import { FileUploader } from "../components/files/FileUploader";

export function NewProjectPage() {
  const navigate = useNavigate();
  const { createProject, uploadFile } = useProjectStore();
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [area, setArea] = useState("");
  const [projectType, setProjectType] = useState<ProjectTypeValue>("multifamily_residential");
  const [jurisdiction, setJurisdiction] = useState("austin_tx");
  const [jurisdictions, setJurisdictions] = useState<Jurisdiction[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listJurisdictions()
      .then(setJurisdictions)
      .catch(() =>
        setJurisdictions([
          { id: "austin_tx", label: "Austin, TX", state: "TX", city: "Austin", coverage_status: "active" },
        ])
      );
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !address.trim()) {
      setError("Name and address are required.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const project = await createProject({
        name: name.trim(),
        address: address.trim(),
        projectType,
        jurisdiction,
        area: area.trim() || undefined,
      });
      for (const file of files) {
        const ext = file.name.toLowerCase();
        const isBrief = ext.endsWith(".json") || ext.endsWith(".zip");
        await uploadFile(project.id, file, undefined, isBrief);
      }
      toast.success(`Created "${project.name}"`);
      navigate(`/projects/${project.id}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to create project";
      setError(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <header className="mb-8">
        <h1 className="text-2xl font-bold">New Project</h1>
        <p className="text-[var(--color-muted)]">Set up your project and upload initial files</p>
      </header>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 space-y-4">
          <h2 className="font-semibold">Project basics</h2>
          <Input label="Project name" value={name} onChange={(e) => setName(e.target.value)} required />
          <Input label="Address" value={address} onChange={(e) => setAddress(e.target.value)} required />
          <Input
            label="Area / District (optional)"
            value={area}
            onChange={(e) => setArea(e.target.value)}
            placeholder="Example: RM, RH, RC, downtown core"
          />
          <Select
            label="Project type"
            value={projectType}
            options={PROJECT_TYPES.map((t) => ({ value: t.value, label: t.label }))}
            onChange={(e) => setProjectType(e.target.value as ProjectTypeValue)}
          />
        </section>

        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h2 className="mb-4 font-semibold">Jurisdiction</h2>
          <Select
            label="City"
            value={jurisdiction}
            options={jurisdictions.map((j) => ({ value: j.id, label: j.label }))}
            onChange={(e) => setJurisdiction(e.target.value)}
          />
        </section>

        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h2 className="mb-4 font-semibold">Files (optional)</h2>
          <FileUploader onFiles={(f) => setFiles((prev) => [...prev, ...f])} />
          {files.length > 0 && (
            <ul className="mt-4 space-y-1 text-sm text-[var(--color-muted)]">
              {files.map((f, i) => (
                <li key={i}>{f.name}</li>
              ))}
            </ul>
          )}
        </section>

        <div className="flex gap-3">
          <Button type="submit" disabled={submitting}>
            {submitting ? "Creating…" : "Create Project"}
          </Button>
          <Button type="button" variant="secondary" onClick={() => navigate("/")}>
            Cancel
          </Button>
        </div>
      </form>
    </div>
  );
}
