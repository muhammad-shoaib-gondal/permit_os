export function cn(...classes: (string | false | null | undefined)[]) {
  return classes.filter(Boolean).join(" ");
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function readinessVariant(score?: string): "pass" | "fail" | "warn" | "ready" | "default" {
  if (!score) return "default";
  if (score === "READY" || score === "pass") return "pass";
  if (score === "BLOCKED" || score === "fail") return "fail";
  if (score === "NEEDS_CHANGES") return "warn";
  return "default";
}
