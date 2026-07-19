import { useEffect } from "react";
import { X } from "lucide-react";
import { Button } from "./Button";

type ModalProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: "default" | "wide" | "full";
};

export function Modal({ open, onClose, title, children, footer, size = "default" }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className={`flex max-h-[calc(100vh-2rem)] w-full flex-col overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] ${
          size === "full" ? "max-w-[min(96vw,90rem)]" : size === "wide" ? "max-w-5xl" : "max-w-2xl"
        }`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <div className="flex shrink-0 items-center justify-between border-b border-[var(--color-border)] px-5 py-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="cursor-pointer text-[var(--color-muted)] hover:text-[var(--color-text)]"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 text-sm text-[var(--color-muted)]">
          {children}
        </div>
        {footer && (
          <div className="flex shrink-0 justify-end gap-2 border-t border-[var(--color-border)] bg-[var(--color-surface)] px-5 py-4">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

type ConfirmDialogProps = {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  loading?: boolean;
};

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = "Confirm",
  danger,
  loading,
}: ConfirmDialogProps) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button variant={danger ? "danger" : "primary"} onClick={onConfirm} disabled={loading}>
            {loading ? "Working…" : confirmLabel}
          </Button>
        </>
      }
    >
      {message}
    </Modal>
  );
}
