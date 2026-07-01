import { Trash2, Star } from "lucide-react";
import type { ProjectFile } from "../../types";
import { FILE_TYPES } from "../../types";
import { Button } from "../common/Button";
import { Badge } from "../common/Badge";
import { formatBytes, formatDate } from "../../lib/utils";

type FileListProps = {
  files: ProjectFile[];
  onDelete?: (fileId: string) => void;
  uploading?: boolean;
};

export function FileList({ files, onDelete, uploading }: FileListProps) {
  if (!files.length) {
    return (
      <div className="rounded-xl border border-dashed border-[var(--color-border)] p-8 text-center text-sm text-[var(--color-muted)]">
        No files uploaded yet. Add your project brief and supporting documents.
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {files.map((file) => {
        const typeLabel = FILE_TYPES.find((t) => t.value === file.type)?.label ?? file.type;
        return (
          <li
            key={file.id}
            className="flex items-center justify-between gap-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3"
          >
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="truncate font-medium">{file.name}</span>
                {file.isPrimaryBrief && (
                  <Badge variant="ready" className="flex items-center gap-1">
                    <Star size={10} /> Primary brief
                  </Badge>
                )}
                <Badge>{typeLabel}</Badge>
                {file.label && <Badge variant="default">{file.label}</Badge>}
                {(file.sections ?? []).map((section) => (
                  <Badge key={section} variant="warn">
                    {section}
                  </Badge>
                ))}
              </div>
              <p className="mt-1 text-xs text-[var(--color-muted)]">
                {formatBytes(file.size)} · {formatDate(file.uploadedAt)}
              </p>
            </div>
            {onDelete && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onDelete(file.id)}
                disabled={uploading}
                aria-label={`Delete ${file.name}`}
              >
                <Trash2 size={16} />
              </Button>
            )}
          </li>
        );
      })}
    </ul>
  );
}
