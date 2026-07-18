import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import type { ChecklistItem, Project } from "../../types";
import { getProjectChecklist, rebuildProjectChecklist, updateChecklistItem } from "../../api";
import { toast } from "../../stores/toastStore";
import { Badge } from "../common/Badge";
import { Button } from "../common/Button";
import { Select } from "../common/Input";

type ChecklistTabProps = {
  project: Project;
};

const STATUS_OPTIONS = [
  { value: "missing", label: "Missing" },
  { value: "uploaded", label: "Uploaded" },
  { value: "waived", label: "Waived" },
  { value: "not_applicable", label: "Not applicable" },
];

export function ChecklistTab({ project }: ChecklistTabProps) {
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const data = await getProjectChecklist(project.id);
      setItems(data.items ?? []);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load checklist");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [project.id, project.files.length]);

  async function rebuild() {
    try {
      const data = await rebuildProjectChecklist(project.id);
      setItems(data.items ?? []);
      toast.success("Checklist rebuilt from KCMO IB requirements");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Rebuild failed");
    }
  }

  async function setStatus(item: ChecklistItem, status: string) {
    setSavingId(item.id);
    try {
      const updated = await updateChecklistItem(project.id, item.id, { status });
      setItems((prev) => prev.map((row) => (row.id === updated.id ? updated : row)));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Update failed");
    } finally {
      setSavingId(null);
    }
  }

  const missing = items.filter((i) => i.status === "missing").length;
  const uploaded = items.filter((i) => i.status === "uploaded").length;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Ready-to-file checklist</h2>
          <p className="text-sm text-[var(--color-muted)]">
            Persistent KCMO document checklist from Information Bulletins. Filenames are auto-matched when possible.
          </p>
        </div>
        <Button variant="secondary" onClick={rebuild}>
          <RefreshCw size={16} /> Rebuild
        </Button>
      </div>

      <section className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <p className="text-xs uppercase text-[var(--color-muted)]">Items</p>
          <strong className="text-2xl">{items.length}</strong>
        </div>
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <p className="text-xs uppercase text-[var(--color-muted)]">Uploaded / matched</p>
          <strong className="text-2xl">{uploaded}</strong>
        </div>
        <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <p className="text-xs uppercase text-[var(--color-muted)]">Still missing</p>
          <strong className="text-2xl">{missing}</strong>
        </div>
      </section>

      {loading ? (
        <p className="text-sm text-[var(--color-muted)]">Loading checklist…</p>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm">
          No checklist items yet. Set jurisdiction to Kansas City, MO and rebuild, or create the project with a category.
        </div>
      ) : (
        <section className="space-y-3">
          {items.map((item) => (
            <article
              key={item.id}
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4"
            >
              <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h3 className="font-medium">{item.label}</h3>
                  <p className="text-xs text-[var(--color-muted)]">
                    {item.sourceTitle}
                    {item.sourceUrl ? (
                      <>
                        {" · "}
                        <a
                          href={item.sourceUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[var(--color-accent)] hover:underline"
                        >
                          Source
                        </a>
                      </>
                    ) : null}
                  </p>
                </div>
                <Badge
                  variant={
                    item.status === "uploaded"
                      ? "pass"
                      : item.status === "missing"
                        ? "fail"
                        : "warn"
                  }
                >
                  {item.status.replace(/_/g, " ")}
                </Badge>
              </div>
              <Select
                label="Status"
                value={item.status}
                options={STATUS_OPTIONS}
                disabled={savingId === item.id}
                onChange={(e) => setStatus(item, e.target.value)}
              />
            </article>
          ))}
        </section>
      )}
    </div>
  );
}
