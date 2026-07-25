import { cn } from "../../lib/utils";

type TabsProps = {
  tabs: { id: string; label: string }[];
  active: string;
  onChange: (id: string) => void;
  className?: string;
};

export function Tabs({ tabs, active, onChange, className }: TabsProps) {
  return (
    <div className={cn("flex gap-1 border-b border-[var(--color-border)]", className)}>
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={cn(
            "cursor-pointer px-4 py-2.5 text-sm font-medium transition border-b-2 -mb-px",
            active === tab.id
              ? "border-[var(--color-accent)] text-[var(--color-text)]"
              : "border-transparent text-[var(--color-muted)] hover:text-[var(--color-text)]"
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
