import { useEffect } from "react";
import { useParams } from "react-router-dom";
import { useProjectStore } from "../stores/projectStore";
import { ProjectWorkspace } from "../components/projects/ProjectWorkspace";

export function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const { currentProject, loading, error, fetchProject } = useProjectStore();

  useEffect(() => {
    if (id) fetchProject(id);
  }, [id, fetchProject]);

  if (loading && !currentProject) {
    return (
      <div className="space-y-4">
        <div className="h-10 w-64 animate-pulse rounded bg-[var(--color-surface2)]" />
        <div className="h-64 animate-pulse rounded-xl bg-[var(--color-surface2)]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">
        {error}
      </div>
    );
  }

  if (!currentProject) {
    return <p className="text-[var(--color-muted)]">Project not found.</p>;
  }

  return <ProjectWorkspace project={currentProject} />;
}
