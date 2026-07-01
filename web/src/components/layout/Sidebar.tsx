import { Link, useLocation } from "react-router-dom";
import {
  ChevronLeft,
  ChevronRight,
  FolderKanban,
  LayoutDashboard,
  Moon,
  Plus,
  Settings,
  Sun,
} from "lucide-react";
import { useState } from "react";
import { useProjectStore } from "../../stores/projectStore";
import { useThemeStore } from "../../stores/themeStore";
import { Button } from "../common/Button";
import { cn, readinessVariant } from "../../lib/utils";
import { Badge } from "../common/Badge";

export function Sidebar() {
  const location = useLocation();
  const { projects } = useProjectStore();
  const { theme, toggleTheme } = useThemeStore();
  const [collapsed, setCollapsed] = useState(false);
  const recent = projects.slice(0, 8);

  return (
    <aside
      className={cn(
        "flex h-screen flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)] transition-all",
        collapsed ? "w-16" : "w-64"
      )}
    >
      <div className="flex items-center justify-between border-b border-[var(--color-border)] p-4">
        {!collapsed && (
          <div>
            <h1 className="text-lg font-bold tracking-tight">EstatePermit</h1>
            <p className="text-xs text-[var(--color-muted)]">Permitting intelligence</p>
          </div>
        )}
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          className="rounded-lg p-1.5 text-[var(--color-muted)] hover:bg-[var(--color-surface2)]"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      <div className="p-3">
        <Link to="/projects/new">
          <Button className="w-full" size="sm">
            <Plus size={16} />
            {!collapsed && "New Project"}
          </Button>
        </Link>
      </div>

      <nav className="flex-1 overflow-y-auto px-2">
        <Link
          to="/"
          className={cn(
            "mb-1 flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition",
            location.pathname === "/" || location.pathname === ""
              ? "bg-[var(--color-surface2)] text-[var(--color-text)]"
              : "text-[var(--color-muted)] hover:bg-[var(--color-surface2)] hover:text-[var(--color-text)]"
          )}
        >
          <LayoutDashboard size={18} />
          {!collapsed && "Dashboard"}
        </Link>

        {!collapsed && (
          <p className="mb-2 mt-4 px-3 text-xs font-medium uppercase tracking-wider text-[var(--color-muted)]">
            Projects
          </p>
        )}
        {recent.length === 0 && !collapsed && (
          <p className="px-3 text-xs text-[var(--color-muted)]">No projects yet</p>
        )}
        {recent.map((p) => (
          <Link
            key={p.id}
            to={`/projects/${p.id}`}
            className={cn(
              "mb-0.5 flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition",
              location.pathname.includes(p.id)
                ? "bg-[var(--color-surface2)] text-[var(--color-text)]"
                : "text-[var(--color-muted)] hover:bg-[var(--color-surface2)] hover:text-[var(--color-text)]"
            )}
            title={p.name}
          >
            <FolderKanban size={16} className="shrink-0" />
            {!collapsed && (
              <span className="flex-1 truncate">{p.name}</span>
            )}
            {!collapsed && p.readinessScore && (
              <Badge variant={readinessVariant(p.readinessScore)} className="shrink-0 text-[10px]">
                {p.readinessScore.slice(0, 4)}
              </Badge>
            )}
          </Link>
        ))}

        <Link
          to="/settings"
          className={cn(
            "mt-4 flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition",
            location.pathname === "/settings"
              ? "bg-[var(--color-surface2)] text-[var(--color-text)]"
              : "text-[var(--color-muted)] hover:bg-[var(--color-surface2)] hover:text-[var(--color-text)]"
          )}
        >
          <Settings size={18} />
          {!collapsed && "Settings"}
        </Link>
      </nav>

      <div className="border-t border-[var(--color-border)] p-3">
        <button
          type="button"
          onClick={toggleTheme}
          className={cn(
            "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-[var(--color-muted)] transition hover:bg-[var(--color-surface2)] hover:text-[var(--color-text)]",
            collapsed && "justify-center"
          )}
          aria-label="Toggle theme"
          title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
          {!collapsed && (theme === "dark" ? "Light mode" : "Dark mode")}
        </button>
      </div>
    </aside>
  );
}
