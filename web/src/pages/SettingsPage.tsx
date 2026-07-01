import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { getDisclaimer } from "../api";
import { useThemeStore } from "../stores/themeStore";

export function SettingsPage() {
  const [disclaimer, setDisclaimer] = useState("");
  const { theme, setTheme } = useThemeStore();

  useEffect(() => {
    getDisclaimer().then(setDisclaimer).catch(() => {});
  }, []);

  return (
    <div className="max-w-2xl">
      <h1 className="mb-2 text-2xl font-bold">Settings</h1>
      <p className="mb-8 text-[var(--color-muted)]">Application preferences and legal notices</p>

      <section className="mb-6 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
        <h2 className="mb-4 font-semibold">Appearance</h2>
        <p className="mb-4 text-sm text-[var(--color-muted)]">Choose how EstatePermit looks.</p>
        <div className="flex gap-3">
          {(["dark", "light"] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => setTheme(mode)}
              className={`flex flex-1 items-center justify-center gap-2 rounded-lg border px-4 py-3 text-sm transition ${
                theme === mode
                  ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-text)]"
                  : "border-[var(--color-border)] text-[var(--color-muted)] hover:bg-[var(--color-surface2)]"
              }`}
            >
              {mode === "dark" ? <Moon size={16} /> : <Sun size={16} />}
              {mode === "dark" ? "Dark" : "Light"}
            </button>
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
        <h2 className="mb-4 font-semibold">About EstatePermit</h2>
        <p className="mb-4 text-sm text-[var(--color-muted)]">
          AI-powered permitting intelligence for real estate development. Pre-screen permits before
          you file — zoning, building code, environmental review, and permit packaging.
        </p>
        <h3 className="mb-2 text-sm font-medium">Disclaimer</h3>
        <p className="text-sm text-[var(--color-muted)]">{disclaimer}</p>
      </section>

      <section className="mt-6 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
        <h2 className="mb-2 font-semibold">Coming soon</h2>
        <ul className="list-disc pl-5 text-sm text-[var(--color-muted)]">
          <li>Authentication & organization-based collaboration</li>
          <li>PDF plan parsing from architectural drawings</li>
          <li>Document checklist & email notifications</li>
        </ul>
      </section>
    </div>
  );
}
