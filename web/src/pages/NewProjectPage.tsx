import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LoaderCircle } from "lucide-react";
import { listJurisdictions } from "../api";
import { DEFAULT_PROJECT_SCOPE, PROJECT_SCOPE_OPTIONS, PROJECT_TYPES } from "../types";
import type { Jurisdiction, ProjectScope, ProjectTypeValue } from "../types";
import { useProjectStore } from "../stores/projectStore";
import { toast } from "../stores/toastStore";
import { Button } from "../components/common/Button";
import { Input, Select } from "../components/common/Input";
import { FileUploader } from "../components/files/FileUploader";

export function NewProjectPage() {
  const navigate = useNavigate();
  const { createProject, uploadFile } = useProjectStore();
  const [name, setName] = useState("");
  const [streetAddress, setStreetAddress] = useState("");
  const [zipCode, setZipCode] = useState("");
  const [projectType, setProjectType] = useState<ProjectTypeValue>("new_commercial_construction");
  const [jurisdiction, setJurisdiction] = useState("kansas_city_mo");
  const [scope, setScope] = useState<ProjectScope>({ ...DEFAULT_PROJECT_SCOPE, new_construction: true });
  const [jurisdictions, setJurisdictions] = useState<Jurisdiction[]>([]);
  const [files, setFiles] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listJurisdictions()
      .then((items) => {
        setJurisdictions(items);
        setJurisdiction((current) =>
          items.some((item) => item.id === current) || !items[0] ? current : items[0].id
        );
      })
      .catch(() =>
        setJurisdictions([
          {
            id: "kansas_city_mo",
            label: "Kansas City, Missouri",
            state: "MO",
            city: "Kansas City",
            coverage_status: "active",
          },
          {
            id: "kansas_city_ks",
            label: "Kansas City, Kansas",
            state: "KS",
            city: "Kansas City",
            coverage_status: "active",
          },
        ])
      );
  }, []);

  function toggleScope(key: keyof ProjectScope) {
    setScope((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !streetAddress.trim() || !zipCode.trim()) {
      setError("Project name, street address, and ZIP code are required.");
      return;
    }
    if (!/^\d{5}(?:-\d{4})?$/.test(zipCode.trim())) {
      setError("Enter a valid 5-digit ZIP code.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const selectedCity = jurisdictions.find((item) => item.id === jurisdiction);
      const fallbackLocation = jurisdiction === "kansas_city_ks"
        ? { city: "Kansas City", state: "KS" }
        : jurisdiction === "manhattan_ks"
          ? { city: "Manhattan", state: "KS" }
          : { city: "Kansas City", state: "MO" };
      const location = selectedCity ?? fallbackLocation;
      const fullAddress = `${streetAddress.trim()}, ${location.city}, ${location.state} ${zipCode.trim()}`;
      const project = await createProject({
        name: name.trim(),
        address: fullAddress,
        projectType,
        jurisdiction,
        scope,
      });
      for (const file of files) {
        await uploadFile(project.id, file);
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
        <p className="text-[var(--color-muted)]">
          Enter the site address and EstatePermit will detect zoning, load local rules, and build the permit bundle.
        </p>
      </header>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-[var(--color-text)]">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5 space-y-4">
          <h2 className="font-semibold">Project basics</h2>
          <Input
            label="Project name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="off"
            required
          />
          <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_10rem]">
            <Input
              label="Street address"
              value={streetAddress}
              onChange={(e) => setStreetAddress(e.target.value)}
              autoComplete="street-address"
              required
            />
            <Input
              label="ZIP code"
              value={zipCode}
              onChange={(e) => setZipCode(e.target.value.replace(/[^0-9-]/g, "").slice(0, 10))}
              inputMode="numeric"
              autoComplete="postal-code"
              maxLength={10}
              required
            />
          </div>
          <p className="-mt-2 text-xs text-[var(--color-muted)]">
            City and state are added automatically from the selected jurisdiction.
          </p>
          <Select
            label="Development type"
            value={projectType}
            options={PROJECT_TYPES.map((t) => ({ value: t.value, label: t.label }))}
            onChange={(e) => setProjectType(e.target.value as ProjectTypeValue)}
          />
        </section>

        <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <div className="mb-4">
            <h2 className="font-semibold">Project scope</h2>
            <p className="text-sm text-[var(--color-muted)]">
              Select the work involved so EstatePermit can recommend the correct permit bundle.
            </p>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {PROJECT_SCOPE_OPTIONS.map((option) => {
              const key = option.value as keyof ProjectScope;
              return (
                <label
                  key={option.value}
                  className={`flex cursor-pointer items-center gap-3 rounded-lg border px-3 py-2 text-sm transition ${
                    scope[key]
                      ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-text)]"
                      : "border-[var(--color-border)] text-[var(--color-muted)] hover:bg-[var(--color-surface2)]"
                  }`}
                >
                  <input
                    type="checkbox"
                    className="accent-[var(--color-accent)]"
                    checked={scope[key]}
                    onChange={() => toggleScope(key)}
                  />
                  {option.label}
                </label>
              );
            })}
          </div>
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
            {submitting ? (
              <>
                <LoaderCircle size={16} className="animate-spin" />
                Resolving address and zoning...
              </>
            ) : (
              "Create Project"
            )}
          </Button>
          <Button type="button" variant="secondary" onClick={() => navigate("/")}>
            Cancel
          </Button>
        </div>
        {submitting && (
          <div className="rounded-xl border border-sky-500/30 bg-sky-500/10 px-4 py-3 text-sm">
            <p className="font-medium text-[var(--color-text)]">Setting up the project</p>
            <p className="mt-1 text-[var(--color-muted)]">
              Matching the address, querying city zoning, loading district rules, and building the initial permit bundle.
            </p>
          </div>
        )}
      </form>
    </div>
  );
}
