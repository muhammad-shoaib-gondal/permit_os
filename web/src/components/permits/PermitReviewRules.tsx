import { useEffect, useState } from "react";
import { Plus, Save, Trash2 } from "lucide-react";
import { getProjectRules } from "../../api";
import { useProjectStore } from "../../stores/projectStore";
import { toast } from "../../stores/toastStore";
import type { BuiltinRule, BuiltinRuleGroup, CustomRule, Project, ProjectPermit } from "../../types";
import { RULE_CATEGORIES } from "../../types";
import { Button } from "../common/Button";
import { Input, Select } from "../common/Input";

type PermitReviewRulesProps = {
  project: Project;
  permit: ProjectPermit;
};

function relevantGroups(permit: ProjectPermit): BuiltinRuleGroup["key"][] {
  const value = `${permit.permitType} ${permit.permitName}`.toLowerCase();
  if (/zoning|land.use|variance|rezon|conditional|plat/.test(value)) return ["zoning", "site"];
  if (/certificate|occupancy/.test(value)) return ["zoning", "building", "fire"];
  if (/fire|sprinkler|alarm|suppression/.test(value)) return ["fire", "building"];
  if (/flood|land|grading|right.of.way|street|utility|water|sewer/.test(value)) return ["site"];
  if (/sign/.test(value)) return ["zoning", "site"];
  if (/building|construction/.test(value)) return ["zoning", "building", "fire"];
  if (/electrical|plumbing|mechanical|hvac/.test(value)) return ["building"];
  return ["building"];
}

function conditionForRule(project: Project, rule: BuiltinRule): { condition: string; actionable: boolean } {
  const title = rule.rule.trim();
  if (rule.condition?.trim()) {
    return { condition: rule.condition.trim(), actionable: true };
  }
  const height = title.match(/max(?:imum)? height\s+(\d+(?:\.\d+)?)\s*ft/i);
  if (height) {
    return { condition: `Proposed building height must not exceed ${height[1]} ft.`, actionable: true };
  }

  const coverage = title.match(/max(?:imum)? building coverage\s+(\d+(?:\.\d+)?)\s*%/i);
  if (coverage) {
    return { condition: `Building coverage must not exceed ${coverage[1]}% of the lot area.`, actionable: true };
  }

  const setback = title.match(/(front|rear|interior side|street side) setback minimum\s+([^\s]+)\s*ft/i);
  if (setback) {
    return {
      condition: `The ${setback[1].toLowerCase()} setback shown on the site plan must be at least ${setback[2]} ft.`,
      actionable: true,
    };
  }

  if (/side setback minimum/i.test(title)) {
    return project.area
      ? {
          condition: `The system does not have an authoritative numeric side-setback for district ${project.area}; this check is deferred automatically.`,
          actionable: false,
        }
      : {
          condition: "This check is deferred until the system detects a zoning district.",
          actionable: false,
        };
  }

  if (/height limit/i.test(title)) {
    return {
      condition: project.area
        ? `The system does not have an authoritative numeric height limit for district ${project.area}; this check is deferred automatically.`
        : "This check is deferred until the system detects a zoning district.",
      actionable: false,
    };
  }

  if (/parking ratio/i.test(title)) {
    return {
      condition: "This parking check is deferred until an authoritative use-and-district requirement is available to the system.",
      actionable: false,
    };
  }

  if (/flood zone determination/i.test(title)) {
    return {
      condition: "Confirm the parcel's FEMA flood-zone designation and flag whether floodplain development requirements apply.",
      actionable: true,
    };
  }

  return {
    condition: `No authoritative measurable requirement is stored for "${title}." The system will defer this check automatically.`,
    actionable: false,
  };
}

function draftRule(project: Project, permit: ProjectPermit, group: BuiltinRuleGroup, rule: BuiltinRule): CustomRule {
  const category = group.key === "permits" ? "permit" : group.key;
  const { condition, actionable } = conditionForRule(project, rule);
  return {
    id: crypto.randomUUID(),
    category,
    rule: rule.rule,
    condition,
    severity: rule.severity === "critical" || rule.severity === "major" ? "warning" : rule.severity ?? "warning",
    enabled: actionable,
    permitType: permit.permitType,
    source: rule.source,
  };
}

function newRule(permit: ProjectPermit): CustomRule {
  return {
    id: crypto.randomUUID(),
    category: "custom",
    rule: "",
    condition: "",
    severity: "warning",
    enabled: true,
    permitType: permit.permitType,
    source: "User-defined",
  };
}

export function PermitReviewRules({ project, permit }: PermitReviewRulesProps) {
  const { saveRules } = useProjectStore();
  const [rules, setRules] = useState<CustomRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState("");
  const [visibleCount, setVisibleCount] = useState(20);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getProjectRules(project.id)
      .then(({ customRules, builtinGroups }) => {
        if (cancelled) return;
        const saved = customRules.filter((rule) => rule.permitType === permit.permitType);
        if (saved.length) {
          const builtinByTitle = new Map(
            builtinGroups.flatMap((group) => group.rules).map((rule) => [rule.rule, rule])
          );
          setRules(
            saved.map((savedRule) => {
              if (!savedRule.condition.startsWith("Verify the available project information against:")) {
                return savedRule;
              }
              const builtin = builtinByTitle.get(savedRule.rule);
              if (!builtin) return savedRule;
              const resolved = conditionForRule(project, builtin);
              return { ...savedRule, condition: resolved.condition, enabled: resolved.actionable };
            })
          );
          return;
        }

        const keys = new Set(relevantGroups(permit));
        const drafts = builtinGroups
          .filter((group) => keys.has(group.key))
          .flatMap((group) => group.rules.map((rule) => draftRule(project, permit, group, rule)));
        setRules(drafts);
      })
      .catch((error) => {
        if (!cancelled) toast.error(error instanceof Error ? error.message : "Failed to load review checks");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [project.id, permit.id, permit.permitType]);

  function updateRule(index: number, next: CustomRule) {
    setRules((current) => current.map((rule, i) => (i === index ? next : rule)));
  }

  async function handleSave() {
    const invalid = rules.some((rule) => !rule.rule.trim() || !rule.condition.trim());
    if (invalid) {
      toast.error("Each review check needs a name and a clear condition.");
      return;
    }
    setSaving(true);
    try {
      const otherRules = project.customRules.filter((rule) => rule.permitType !== permit.permitType);
      await saveRules(project.id, [...otherRules, ...rules]);
      toast.success(`Review checks saved for ${permit.permitName}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to save review checks");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="text-sm text-[var(--color-muted)]">Loading review checks...</p>;

  const normalizedSearch = search.trim().toLowerCase();
  const filteredRules = normalizedSearch
    ? rules.filter((rule) =>
        `${rule.rule} ${rule.condition} ${rule.source ?? ""}`.toLowerCase().includes(normalizedSearch)
      )
    : rules;
  const visibleRules = filteredRules.slice(0, visibleCount);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <Input
          label="Search checks"
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setVisibleCount(20);
          }}
          placeholder="Height, setback, egress..."
          className="min-w-64"
        />
        <p className="pb-2 text-xs text-[var(--color-muted)]">
          Showing {Math.min(visibleCount, filteredRules.length)} of {filteredRules.length} checks
        </p>
      </div>

      {visibleRules.map((rule) => {
        const index = rules.findIndex((candidate) => candidate.id === rule.id);
        return (
        <div key={rule.id} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3">
          <div className="mb-3 flex items-center justify-between gap-3">
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={rule.enabled}
                onChange={(event) => updateRule(index, { ...rule, enabled: event.target.checked })}
                className="cursor-pointer accent-[var(--color-accent)]"
              />
              Include in review
            </label>
            <Button
              size="sm"
              variant="ghost"
              aria-label="Delete review check"
              onClick={() => setRules((current) => current.filter((_, i) => i !== index))}
            >
              <Trash2 size={15} />
            </Button>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <Input
              label="Check name"
              value={rule.rule}
              onChange={(event) => updateRule(index, { ...rule, rule: event.target.value })}
            />
            <Select
              label="Review area"
              value={rule.category}
              options={RULE_CATEGORIES.map((category) => ({ value: category.value, label: category.label }))}
              onChange={(event) =>
                updateRule(index, { ...rule, category: event.target.value as CustomRule["category"] })
              }
            />
            <label className="flex flex-col gap-1.5 text-sm md:col-span-2">
              <span className="text-[var(--color-muted)]">Exactly what should be verified</span>
              <textarea
                className="min-h-20 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface2)] px-3 py-2 text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
                value={rule.condition}
                onChange={(event) => updateRule(index, { ...rule, condition: event.target.value })}
              />
            </label>
            <Select
              label="Impact if it fails"
              value={rule.severity}
              options={[
                { value: "blocker", label: "Blocks submission" },
                { value: "warning", label: "Needs attention" },
                { value: "info", label: "Informational" },
              ]}
              onChange={(event) =>
                updateRule(index, { ...rule, severity: event.target.value as CustomRule["severity"] })
              }
            />
            <Input
              label="Rule source"
              value={rule.source ?? ""}
              onChange={(event) => updateRule(index, { ...rule, source: event.target.value })}
            />
          </div>
        </div>
        );
      })}

      <div className="flex flex-wrap gap-2">
        {visibleCount < filteredRules.length && (
          <Button variant="ghost" size="sm" onClick={() => setVisibleCount((count) => count + 20)}>
            Show 20 more
          </Button>
        )}
        <Button variant="secondary" size="sm" onClick={() => setRules((current) => [...current, newRule(permit)])}>
          <Plus size={15} /> Add check
        </Button>
        <Button size="sm" onClick={handleSave} disabled={saving}>
          <Save size={15} /> {saving ? "Saving..." : "Save review checks"}
        </Button>
      </div>
    </div>
  );
}
