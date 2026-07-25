import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload } from "lucide-react";
import { cn } from "../../lib/utils";

type FileUploaderProps = {
  onFiles: (files: File[]) => void;
  accept?: Record<string, string[]>;
  multiple?: boolean;
  disabled?: boolean;
  label?: string;
};

export function FileUploader({
  onFiles,
  accept = {
    "application/pdf": [".pdf"],
    "application/msword": [".doc"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    "image/*": [".png", ".jpg", ".jpeg"],
  },
  multiple = true,
  disabled,
  label = "Drop files here or click to browse",
}: FileUploaderProps) {
  const [dragOver, setDragOver] = useState(false);

  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted.length) onFiles(accepted);
      setDragOver(false);
    },
    [onFiles]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept,
    multiple,
    disabled,
    onDragEnter: () => setDragOver(true),
    onDragLeave: () => setDragOver(false),
  });

  return (
    <div
      {...getRootProps()}
      className={cn(
        "cursor-pointer rounded-xl border-2 border-dashed border-[var(--color-border)] bg-[var(--color-surface)] p-8 text-center transition",
        (isDragActive || dragOver) && "border-[var(--color-accent)] bg-[var(--color-accent)]/5",
        disabled && "cursor-not-allowed opacity-50"
      )}
    >
      <input {...getInputProps()} />
      <Upload className="mx-auto mb-3 text-[var(--color-muted)]" size={32} />
      <p className="font-medium">{label}</p>
      <p className="mt-1 text-sm text-[var(--color-muted)]">
        PDF, DOC, DOCX, PNG, JPG supported
      </p>
    </div>
  );
}
