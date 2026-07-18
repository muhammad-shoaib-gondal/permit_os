import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LoaderCircle } from "lucide-react";
import { listJurisdictions } from "../api";
import {
  DEFAULT_KCMO_INTAKE,
  PROJECT_CATEGORIES,
  SCOPE_TYPE_OPTIONS,
} from "../types";
import type { Jurisdiction, KcmoIntake, ProjectCategory, ScopeTypeValue } from "../types";
import { useProjectStore } from "../stores/projectStore";
import { toast } from "../stores/toastStore";
import { Button } from "../components/common/Button";
import { Input, Select } from "../components/common/Input";
import { FileUploader } from "../components/files/FileUploader";

function YesNo({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm">
      <input
        type="checkbox"
        className="accent-[var(--color-accent)]"
        checked={value}
        onChange={(e) => onChange(e.target.checked)}
      />
      {label}
    </label>
  );
}

export function NewProjectPage() {
  const navigate = useNavigate();
  const { createProject, uploadFile } = useProjectStore();
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [jurisdiction, setJurisdiction] = useState("kansas_city_mo");
  const [intake, setIntake] = useState<KcmoIntake>({ ...DEFAULT_KCMO_INTAKE });
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
            label: "Kansas City, MO",
            state: "MO",
            city: "Kansas City",
            coverage_status: "active",
          },
        ])
      );
  }, []);

  function patchIntake(partial: Partial<KcmoIntake>) {
    setIntake((prev) => ({ ...prev, ...partial }));
  }

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
        jurisdiction,
        intake: intake as unknown as Record<string, unknown>,
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

  const category = intake.project_category;

  return (
    <div className="mx-auto max-w-3xl">
      <header className="mb-8">
        <h1 className="text-2xl font-bold">New Project</h1>
        <p className="text-[var(--color-muted)]">
          Kansas City, MO structured intake — category, scope, and trade flags drive the permit router.
        </p>
      </header>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        <section className="space-y-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h2 className="font-semibold">Project basics</h2>
          <Input label="Project name" value={name} onChange={(e) => setName(e.target.value)} required />
          <Input
            label="Full project address"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            placeholder="414 E 12th St, Kansas City, MO 64106"
            required
          />
          <Input
            label="Parcel / lot number (if known)"
            value={intake.parcel_lot_number ?? ""}
            onChange={(e) => patchIntake({ parcel_lot_number: e.target.value || null })}
          />
          <Select
            label="City"
            value={jurisdiction}
            options={jurisdictions.map((j) => ({ value: j.id, label: j.label }))}
            onChange={(e) => setJurisdiction(e.target.value)}
          />
          <Select
            label="Project category"
            value={category}
            options={PROJECT_CATEGORIES.map((c) => ({ value: c.value, label: c.label }))}
            onChange={(e) => patchIntake({ project_category: e.target.value as ProjectCategory })}
          />
          <Select
            label="Scope type"
            value={intake.scope_type}
            options={SCOPE_TYPE_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
            onChange={(e) => patchIntake({ scope_type: e.target.value as ScopeTypeValue })}
          />
        </section>

        <section className="space-y-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
          <h2 className="font-semibold">Shared project facts</h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              label="Existing use"
              value={intake.existing_use ?? ""}
              onChange={(e) => patchIntake({ existing_use: e.target.value || null })}
            />
            <Input
              label="Proposed use"
              value={intake.proposed_use ?? ""}
              onChange={(e) => patchIntake({ proposed_use: e.target.value || null })}
            />
            <Input
              label="Estimated construction valuation (USD)"
              type="number"
              value={intake.estimated_valuation_usd ?? ""}
              onChange={(e) =>
                patchIntake({
                  estimated_valuation_usd: e.target.value ? Number(e.target.value) : null,
                })
              }
            />
            <Input
              label="Building area (sq ft)"
              type="number"
              value={intake.building_area_sqft ?? ""}
              onChange={(e) =>
                patchIntake({ building_area_sqft: e.target.value ? Number(e.target.value) : null })
              }
            />
            <Input
              label="Number of stories"
              type="number"
              value={intake.stories ?? ""}
              onChange={(e) => patchIntake({ stories: e.target.value ? Number(e.target.value) : null })}
            />
            <Select
              label="Floodplain"
              value={intake.floodplain_status ?? "unknown"}
              options={[
                { value: "unknown", label: "Unknown" },
                { value: "yes", label: "Yes" },
                { value: "no", label: "No" },
              ]}
              onChange={(e) =>
                patchIntake({ floodplain_status: e.target.value as "unknown" | "yes" | "no" })
              }
            />
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            <YesNo
              label="Work includes electrical"
              value={!!intake.includes_electrical}
              onChange={(v) => patchIntake({ includes_electrical: v })}
            />
            <YesNo
              label="Work includes plumbing"
              value={!!intake.includes_plumbing}
              onChange={(v) => patchIntake({ includes_plumbing: v })}
            />
            <YesNo
              label="Work includes mechanical / HVAC"
              value={!!intake.includes_mechanical}
              onChange={(v) => patchIntake({ includes_mechanical: v })}
            />
            <YesNo
              label="Work includes fire sprinkler / fire alarm"
              value={!!intake.includes_fire_sprinkler_alarm}
              onChange={(v) => patchIntake({ includes_fire_sprinkler_alarm: v })}
            />
            <YesNo
              label="Affects public ROW / sidewalk / curb / driveway / sewer / stormwater"
              value={!!intake.affects_public_row}
              onChange={(v) => patchIntake({ affects_public_row: v })}
            />
          </div>
        </section>

        {category === "single_family" && (
          <section className="space-y-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
            <h2 className="font-semibold">Single-family details</h2>
            <div className="grid gap-2 sm:grid-cols-2">
              <YesNo
                label="Owner-occupied"
                value={!!intake.owner_occupied}
                onChange={(v) => patchIntake({ owner_occupied: v })}
              />
              <YesNo
                label="Basement finish"
                value={!!intake.basement_finish}
                onChange={(v) => patchIntake({ basement_finish: v })}
              />
              <YesNo
                label="Garage / shed / accessory structure"
                value={!!intake.accessory_structure}
                onChange={(v) => patchIntake({ accessory_structure: v })}
              />
              <YesNo
                label="Driveway work"
                value={!!intake.driveway_work}
                onChange={(v) => patchIntake({ driveway_work: v })}
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Select
                label="One-family or two-family"
                value={intake.dwelling_type ?? ""}
                options={[
                  { value: "", label: "Not specified" },
                  { value: "one_family", label: "One-family" },
                  { value: "two_family", label: "Two-family" },
                ]}
                onChange={(e) =>
                  patchIntake({
                    dwelling_type: (e.target.value || null) as KcmoIntake["dwelling_type"],
                  })
                }
              />
              <Select
                label="Addition / remodel / new home"
                value={intake.residential_work_type ?? ""}
                options={[
                  { value: "", label: "Not specified" },
                  { value: "addition", label: "Addition" },
                  { value: "remodel", label: "Remodel" },
                  { value: "new_home", label: "New home" },
                ]}
                onChange={(e) =>
                  patchIntake({
                    residential_work_type: (e.target.value || null) as KcmoIntake["residential_work_type"],
                  })
                }
              />
            </div>
          </section>
        )}

        {category === "multifamily" && (
          <section className="space-y-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
            <h2 className="font-semibold">Multifamily details</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <Input
                label="Number of dwelling units"
                type="number"
                value={intake.dwelling_units ?? ""}
                onChange={(e) =>
                  patchIntake({ dwelling_units: e.target.value ? Number(e.target.value) : null })
                }
              />
              <Select
                label="Building form"
                value={intake.multifamily_form ?? ""}
                options={[
                  { value: "", label: "Not specified" },
                  { value: "apartments", label: "Apartments" },
                  { value: "townhomes", label: "Townhomes" },
                  { value: "mixed_use_residential", label: "Mixed-use with residential" },
                ]}
                onChange={(e) =>
                  patchIntake({
                    multifamily_form: (e.target.value || null) as KcmoIntake["multifamily_form"],
                  })
                }
              />
              <Select
                label="Sprinklered"
                value={intake.sprinklered ?? "unknown"}
                options={[
                  { value: "unknown", label: "Unknown" },
                  { value: "yes", label: "Yes" },
                  { value: "no", label: "No" },
                ]}
                onChange={(e) =>
                  patchIntake({ sprinklered: e.target.value as "yes" | "no" | "unknown" })
                }
              />
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <YesNo
                label="Fire separation / firewall involved"
                value={!!intake.fire_separation_involved}
                onChange={(v) => patchIntake({ fire_separation_involved: v })}
              />
              <YesNo
                label="Change in number of units"
                value={!!intake.change_in_unit_count}
                onChange={(v) => patchIntake({ change_in_unit_count: v })}
              />
              <YesNo
                label="Multiple buildings"
                value={!!intake.multiple_buildings}
                onChange={(v) => patchIntake({ multiple_buildings: v })}
              />
            </div>
          </section>
        )}

        {category === "commercial" && (
          <section className="space-y-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
            <h2 className="font-semibold">Commercial details</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <Input
                label="Business / use type"
                value={intake.business_use_type ?? ""}
                onChange={(e) => patchIntake({ business_use_type: e.target.value || null })}
              />
              <Input
                label="Occupancy group (if known)"
                value={intake.occupancy_group ?? ""}
                onChange={(e) => patchIntake({ occupancy_group: e.target.value || null })}
              />
              <Input
                label="Construction type (if known)"
                value={intake.construction_type ?? ""}
                onChange={(e) => patchIntake({ construction_type: e.target.value || null })}
              />
              <Select
                label="Change of occupancy"
                value={intake.change_of_occupancy ?? "unknown"}
                options={[
                  { value: "unknown", label: "Unknown" },
                  { value: "yes", label: "Yes" },
                  { value: "no", label: "No" },
                ]}
                onChange={(e) =>
                  patchIntake({ change_of_occupancy: e.target.value as "yes" | "no" | "unknown" })
                }
              />
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <YesNo
                label="Tenant finish"
                value={!!intake.tenant_finish}
                onChange={(v) => patchIntake({ tenant_finish: v })}
              />
              <YesNo
                label="Shell building"
                value={!!intake.shell_building}
                onChange={(v) => patchIntake({ shell_building: v })}
              />
              <YesNo
                label="Public access / customer area"
                value={!!intake.public_access}
                onChange={(v) => patchIntake({ public_access: v })}
              />
            </div>
          </section>
        )}

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
              "Create project"
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
