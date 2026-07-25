import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";
import { useProjectStore } from "../stores/projectStore";
import { ProjectWorkspace } from "../components/projects/ProjectWorkspace";
import { Button } from "../components/common/Button";

export function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const { currentProject, loading, error, fetchProject } = useProjectStore();
  const projectMatchesUrl = !!currentProject && currentProject.id === id;

  useEffect(() => {
    if (id) fetchProject(id);
  }, [id, fetchProject]);

  if (loading && !projectMatchesUrl) {
    return (
      <div className="space-y-4">
        <div className="h-10 w-64 animate-pulse rounded bg-[var(--color-surface2)]" />
        <div className="h-64 animate-pulse rounded-xl bg-[var(--color-surface2)]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-[var(--color-text)]">
        <p className="mb-3">{error}</p>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={() => id && fetchProject(id)}>
            Retry
          </Button>
          <Link to="/">
            <Button size="sm" variant="secondary">
              Back to projects
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  if (!projectMatchesUrl) {
    return (
      <div className="rounded-lg border border-amber-500/70 bg-amber-950 px-4 py-3 text-sm font-medium text-amber-50">
        <p className="mb-3">Project not found or still loading. Use the projects list to reopen it.</p>
        <Link to="/">
          <Button size="sm" variant="secondary">
            Back to projects
          </Button>
        </Link>
      </div>
    );
  }

  return <ProjectWorkspace project={currentProject} />;
}
