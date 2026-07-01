import { cn } from "../../lib/utils";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
};

export function Button({
  className,
  variant = "primary",
  size = "md",
  children,
  ...props
}: ButtonProps) {
  const variants = {
    primary: "bg-[var(--color-accent)] hover:bg-[#2d8ae0] text-white",
    secondary: "bg-[var(--color-surface2)] hover:bg-[#243040] border border-[var(--color-border)] text-[var(--color-text)]",
    ghost: "bg-transparent hover:bg-[var(--color-surface2)] text-[var(--color-muted)] hover:text-[var(--color-text)]",
    danger: "bg-red-600/20 hover:bg-red-600/30 text-[var(--color-fail)] border border-red-500/30",
  };
  const sizes = {
    sm: "px-3 py-1.5 text-sm",
    md: "px-4 py-2 text-sm",
    lg: "px-5 py-2.5 text-base",
  };
  return (
    <button
      className={cn(
        "inline-flex cursor-pointer items-center justify-center gap-2 rounded-lg font-medium transition disabled:opacity-50 disabled:cursor-not-allowed",
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}
