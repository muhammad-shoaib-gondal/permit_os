import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";
import { useToastStore, type ToastVariant } from "../../stores/toastStore";

const ICONS: Record<ToastVariant, React.ReactNode> = {
  success: <CheckCircle2 size={18} className="text-[var(--color-pass)]" />,
  error: <AlertCircle size={18} className="text-[var(--color-fail)]" />,
  info: <Info size={18} className="text-[var(--color-accent)]" />,
};

const TOAST_STYLES: Record<ToastVariant, string> = {
  success: "border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]",
  info: "border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]",
  error: "border-red-500/40 bg-red-500/10 text-[var(--color-text)]",
};

export function Toaster() {
  const { toasts, dismiss } = useToastStore();

  if (!toasts.length) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          role="status"
          className={`flex items-start gap-3 rounded-lg border px-4 py-3 text-sm shadow-lg ${TOAST_STYLES[t.variant]}`}
          style={{ boxShadow: "var(--shadow-card)" }}
        >
          <span className="mt-0.5 shrink-0">{ICONS[t.variant]}</span>
          <span className="flex-1">{t.message}</span>
          <button
            type="button"
            onClick={() => dismiss(t.id)}
            className="shrink-0 cursor-pointer opacity-80 hover:opacity-100"
            aria-label="Dismiss"
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
