import { Link } from "react-router-dom";
import { FileText, MapPin, Trash2 } from "lucide-react";
import type { Project } from "../../types";
import { Badge } from "../common/Badge";
import { formatDate, readinessVariant } from "../../lib/utils";

export function ProjectCard({
  project,
  onDelete,
}: {
  project: Project;
  onDelete?: (project: Project) => void;
}) {
  return (
    <div className="group relative rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] transition hover:border-[var(--color-accent)]/50 hover:bg-[var(--color-surface2)]">
      {onDelete && (
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            onDelete(project);
          }}
          className="absolute right-3 top-3 z-10 rounded-lg p-1.5 text-[var(--color-muted)] opacity-0 transition hover:bg-[var(--color-fail)]/15 hover:text-[var(--color-fail)] group-hover:opacity-100"
          aria-label={`Delete ${project.name}`}
        >
          <Trash2 size={16} />
        </button>
      )}
      <Link to={`/projects/${project.id}`} className="block p-5">
        <div className="mb-3 flex items-start justify-between gap-2 pr-8">
          <h3 className="font-semibold group-hover:text-[var(--color-accent)]">{project.name}</h3>
          {project.readinessScore && (
            <Badge variant={readinessVariant(project.readinessScore)}>{project.readinessScore}</Badge>
          )}
        </div>
        <p className="mb-3 flex items-center gap-1.5 text-sm text-[var(--color-muted)]">
          <MapPin size={14} />
          <span className="truncate">{project.address}</span>
        </p>
        <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--color-muted)]">
          <Badge>{project.jurisdiction.replace("_", ", ").toUpperCase()}</Badge>
          {project.area && <Badge>{project.area}</Badge>}
          <span className="flex items-center gap-1">
            <FileText size={12} />
            {project.files.length} file{project.files.length !== 1 ? "s" : ""}
          </span>
          <span>Updated {formatDate(project.updatedAt)}</span>
        </div>
      </Link>
    </div>
  );
}
