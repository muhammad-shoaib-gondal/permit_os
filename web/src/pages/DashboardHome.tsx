import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { FolderOpen, Plus, BarChart3, AlertTriangle, CheckCircle2, Search } from "lucide-react";
import { useProjectStore } from "../stores/projectStore";
import { toast } from "../stores/toastStore";
import { ProjectCard } from "../components/projects/ProjectCard";
import { Button } from "../components/common/Button";
import { ConfirmDialog } from "../components/common/Modal";
import type { Project } from "../types";

const STATUS_FILTERS = [
  { value: "all", label: "All" },
  { value: "READY", label: "Ready" },
  { value: "NEEDS_CHANGES", label: "Needs changes" },
  { value: "BLOCKED", label: "Blocked" },
];

export function DashboardHome() {
  const { projects, loading, error, fetchProjects, deleteProject } = useProjectStore();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [jurisdiction, setJurisdiction] = useState("all");
  const [toDelete, setToDelete] = useState<Project | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const jurisdictions = useMemo(
    () => Array.from(new Set(projects.map((p) => p.jurisdiction))),
    [projects]
  );

  const filtered = useMemo(() => {
    return projects.filter((p) => {
      const matchesQuery =
        !query ||
        p.name.toLowerCase().includes(query.toLowerCase()) ||
        p.address.toLowerCase().includes(query.toLowerCase());
      const matchesStatus = status === "all" || p.readinessScore === status;
      const matchesJurisdiction = jurisdiction === "all" || p.jurisdiction === jurisdiction;
      return matchesQuery && matchesStatus && matchesJurisdiction;
    });
  }, [projects, query, status, jurisdiction]);

  const totalAnalyses = projects.reduce((n, p) => n + p.analyses.length, 0);
  const readyCount = projects.filter((p) => p.readinessScore === "READY").length;
  const blockedCount = projects.filter((p) => p.readinessScore === "BLOCKED").length;

  async function handleDelete() {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await deleteProject(toDelete.id);
      toast.success(`Deleted "${toDelete.name}"`);
      setToDelete(null);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to delete project");
    } finally {
      setDeleting(false);
    }
  }

  if (loading && !projects.length) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded bg-[var(--color-surface2)]" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-24 animate-pulse rounded-xl bg-[var(--color-surface2)]" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div>
      <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Your Projects</h1>
          <p className="text-[var(--color-muted)]">Manage permitting pre-screens across jurisdictions</p>
        </div>
        <Link to="/projects/new">
          <Button>
            <Plus size={18} /> New Project
          </Button>
        </Link>
      </header>

      {error && (
        <div className="mb-6 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
          {error}
        </div>
      )}

      <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={<FolderOpen size={20} />} label="Projects" value={projects.length} />
        <StatCard icon={<BarChart3 size={20} />} label="Analyses run" value={totalAnalyses} />
        <StatCard icon={<CheckCircle2 size={20} />} label="Ready" value={readyCount} variant="pass" />
        <StatCard icon={<AlertTriangle size={20} />} label="Blocked" value={blockedCount} variant="fail" />
      </div>

      {projects.length === 0 ? (
        <div className="rounded-xl border border-dashed border-[var(--color-border)] bg-[var(--color-surface)] p-12 text-center">
          <FolderOpen className="mx-auto mb-4 text-[var(--color-muted)]" size={48} />
          <h2 className="mb-2 text-lg font-semibold">Create your first project</h2>
          <p className="mb-6 text-sm text-[var(--color-muted)]">
            Upload your project brief, select a jurisdiction, and run AI-powered permitting pre-screen.
          </p>
          <Link to="/projects/new">
            <Button>
              <Plus size={18} /> New Project
            </Button>
          </Link>
        </div>
      ) : (
        <>
          <div className="mb-6 flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-muted)]"
              />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search projects…"
                className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] py-2 pl-9 pr-3 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
              />
            </div>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
            >
              {STATUS_FILTERS.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
            {jurisdictions.length > 1 && (
              <select
                value={jurisdiction}
                onChange={(e) => setJurisdiction(e.target.value)}
                className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
              >
                <option value="all">All jurisdictions</option>
                {jurisdictions.map((j) => (
                  <option key={j} value={j}>
                    {j.replace("_", ", ").toUpperCase()}
                  </option>
                ))}
              </select>
            )}
          </div>

          {filtered.length === 0 ? (
            <p className="rounded-xl border border-dashed border-[var(--color-border)] p-8 text-center text-sm text-[var(--color-muted)]">
              No projects match your filters.
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {filtered.map((p) => (
                <ProjectCard key={p.id} project={p} onDelete={setToDelete} />
              ))}
            </div>
          )}
        </>
      )}

      <ConfirmDialog
        open={!!toDelete}
        onClose={() => setToDelete(null)}
        onConfirm={handleDelete}
        title="Delete project"
        message={`Delete "${toDelete?.name}"? This removes all files and analysis history and cannot be undone.`}
        confirmLabel="Delete"
        danger
        loading={deleting}
      />
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
  variant,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  variant?: "pass" | "fail";
}) {
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <div className="mb-2 flex items-center gap-2 text-[var(--color-muted)]">
        {icon}
        <span className="text-sm">{label}</span>
      </div>
      <p
        className={`text-2xl font-bold ${
          variant === "pass" ? "text-[var(--color-pass)]" : variant === "fail" ? "text-[var(--color-fail)]" : ""
        }`}
      >
        {value}
      </p>
    </div>
  );
}
