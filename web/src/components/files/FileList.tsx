import { Trash2 } from "lucide-react";
import type { ProjectFile } from "../../types";
import { FILE_TYPES } from "../../types";
import { Button } from "../common/Button";
import { Badge } from "../common/Badge";
import { formatBytes, formatDate } from "../../lib/utils";

type FileListProps = {
  files: ProjectFile[];
  onDelete?: (fileId: string) => void;
  onUpdateType?: (fileId: string, fileType: string) => void;
  uploading?: boolean;
};

export function FileList({ files, onDelete, onUpdateType, uploading }: FileListProps) {
  if (!files.length) {
    return (
      <div className="rounded-xl border border-dashed border-[var(--color-border)] p-8 text-center text-sm text-[var(--color-muted)]">
        No documents uploaded yet.
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {files.map((file) => {
        const knownType = FILE_TYPES.some((type) => type.value === file.type);
        const typeLabel = FILE_TYPES.find((type) => type.value === file.type)?.label ?? "Other";
        return (
          <li
            key={file.id}
            className="flex flex-col gap-4 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="truncate font-medium">{file.name}</span>
                {file.label && <Badge>{file.label}</Badge>}
              </div>
              <p className="mt-1 text-xs text-[var(--color-muted)]">
                {formatBytes(file.size)} - {formatDate(file.uploadedAt)}
              </p>
              {file.aiSummary && (
                <p className="mt-2 line-clamp-2 text-sm text-[var(--color-muted)]">{file.aiSummary}</p>
              )}
              {!!file.permitTypes?.length && (
                <p className="mt-1 text-xs text-[var(--color-muted)]">
                  Matched to {file.permitTypes.length} permit{file.permitTypes.length === 1 ? "" : "s"}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              {onUpdateType ? (
                <select
                  aria-label={`Document type for ${file.name}`}
                  className="min-w-48 cursor-pointer rounded-lg border border-[var(--color-border)] bg-[var(--color-surface2)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
                  value={knownType ? file.type : "other"}
                  disabled={uploading}
                  onChange={(event) => onUpdateType(file.id, event.target.value)}
                >
                  {FILE_TYPES.map((type) => (
                    <option key={type.value} value={type.value}>{type.label}</option>
                  ))}
                </select>
              ) : (
                <Badge>{typeLabel}</Badge>
              )}
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
            </div>
          </li>
        );
      })}
    </ul>
  );
}
