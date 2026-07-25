import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight, Play, Plus, Save, Sparkles } from "lucide-react";
import type { AnalysisModuleKey, BuiltinRuleGroup, CustomRule } from "../../types";
import { getProjectRules, suggestRules } from "../../api";
import { toast } from "../../stores/toastStore";
import { useAnalysisStore } from "../../stores/projectStore";
import { Button } from "../common/Button";
import { RuleItem } from "./RuleItem";
import { Badge } from "../common/Badge";

type RulesEditorProps = {
  projectId: string;
  rules: CustomRule[];
  onSave: (rules: CustomRule[]) => Promise<void>;
  area?: string;
};

function newRule(): CustomRule {
  return {
    id: crypto.randomUUID(),
    category: "custom",
    rule: "",
    condition: "",
    severity: "warning",
    enabled: true,
  };
}

export function RulesEditor({ projectId, rules: initialRules, onSave, area }: RulesEditorProps) {
  const [rules, setRules] = useState<CustomRule[]>(initialRules);
  const [builtinGroups, setBuiltinGroups] = useState<BuiltinRuleGroup[]>([]);
  const [saving, setSaving] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
  const [bulkRulesText, setBulkRulesText] = useState("");
  const { runAnalysis } = useAnalysisStore();

  useEffect(() => {
    setRules(initialRules);
  }, [initialRules]);

  useEffect(() => {
    getProjectRules(projectId)
      .then((r) => {
        setBuiltinGroups(r.builtinGroups);
        setCollapsedGroups(
          Object.fromEntries(r.builtinGroups.map((group) => [group.key, true]))
        );
      })
      .catch(() => {});
  }, [projectId]);

  async function handleRunGroup(group: AnalysisModuleKey) {
    try {
      await runAnalysis(projectId, [group]);
      toast.success(`${group} analysis started`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to run analysis");
    }
  }

  function toggleGroup(groupKey: string) {
    setCollapsedGroups((prev) => ({ ...prev, [groupKey]: !prev[groupKey] }));
  }

  function handleBulkAdd() {
    const lines = bulkRulesText
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);

    if (!lines.length) {
      toast.error("Enter at least one rule");
      return;
    }

    const nextRules = lines.map((line) => ({
      id: crypto.randomUUID(),
      category: "custom" as const,
      rule: line,
      condition: line,
      severity: "warning" as const,
      enabled: true,
      area: area || "",
    }));

    setRules([...rules, ...nextRules]);
    setBulkRulesText("");
    setDirty(true);
    toast.success(`Added ${nextRules.length} rule${nextRules.length !== 1 ? "s" : ""}`);
  }

  async function handleSave() {
    setSaving(true);
    try {
      await onSave(rules);
      setDirty(false);
      toast.success("Rules saved");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to save rules");
    } finally {
      setSaving(false);
    }
  }

  async function handleSuggest() {
    setSuggesting(true);
    try {
      const suggested = await suggestRules(projectId);
      setRules([...rules, ...suggested]);
      setDirty(true);
      toast.success(`Added ${suggested.length} suggested rule${suggested.length !== 1 ? "s" : ""}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to suggest rules");
    } finally {
      setSuggesting(false);
    }
  }

  return (
    <div className="space-y-8">
      <section>
        <h3 className="mb-3 text-sm font-medium uppercase tracking-wider text-[var(--color-muted)]">
          Built-in checks (read-only)
        </h3>
        <p className="mb-4 text-sm text-[var(--color-muted)]">
          EstatePermit automatically runs these checks from the jurisdiction knowledge base.
        </p>
        <div className="grid gap-4">
          {builtinGroups.map((group) => (
            <section key={group.key} className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <button
                  type="button"
                  className="flex items-center gap-2 text-left"
                  onClick={() => toggleGroup(group.key)}
                >
                  {collapsedGroups[group.key] ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
                  <div>
                    <h4 className="font-medium">{group.label}</h4>
                    <p className="text-xs text-[var(--color-muted)]">
                      {group.rules.length} built-in rule{group.rules.length !== 1 ? "s" : ""}
                      {area ? ` · area ${area}` : ""}
                    </p>
                  </div>
                </button>
                <div className="flex items-center gap-2">
                  <Badge>{group.rules.length}</Badge>
                  {group.key !== "permits" && (
                    <Button size="sm" variant="secondary" onClick={() => handleRunGroup(group.key as AnalysisModuleKey)}>
                      <Play size={16} /> Run
                    </Button>
                  )}
                </div>
              </div>
              {!collapsedGroups[group.key] && (
                <ul className="grid gap-2 sm:grid-cols-2">
                  {group.rules.map((r, i) => (
                    <li
                      key={i}
                      className="flex items-center justify-between rounded-lg border border-[var(--color-border)] bg-[var(--color-surface2)] px-3 py-2 text-sm"
                    >
                      <span>{r.rule}</span>
                      <Badge>{r.category}</Badge>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}
        </div>
      </section>

      <section>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-base font-semibold">Custom rules</h3>
            <p className="text-sm text-[var(--color-muted)]">
              Add your own rules — evaluated by AI alongside built-in checks.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={handleSuggest} disabled={suggesting}>
              <Sparkles size={16} /> {suggesting ? "Suggesting…" : "Suggest rules"}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setRules([...rules, newRule()]);
                setDirty(true);
              }}
            >
              <Plus size={16} /> Add rule
            </Button>
            {dirty && (
              <Button size="sm" onClick={handleSave} disabled={saving}>
                <Save size={16} /> {saving ? "Saving…" : "Save rules"}
              </Button>
            )}
          </div>
        </div>

        <div className="mb-4 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
          <h4 className="mb-2 font-medium">Add multiple rules</h4>
          <p className="mb-3 text-sm text-[var(--color-muted)]">
            Add one rule per line. Each line will be created as a separate custom rule.
          </p>
          <label className="block">
            <textarea
              value={bulkRulesText}
              onChange={(e) => setBulkRulesText(e.target.value)}
              rows={6}
              placeholder={`Building height must not exceed district maximum\nParking spaces must meet minimum ratio\nAccessory structure setbacks must comply with area rules`}
              className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface2)] px-3 py-2 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-accent)]"
            />
          </label>
          <div className="mt-3 flex justify-end">
            <Button variant="secondary" size="sm" onClick={handleBulkAdd}>
              <Plus size={16} /> Add All
            </Button>
          </div>
        </div>

        {rules.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[var(--color-border)] p-8 text-center text-sm text-[var(--color-muted)]">
            No custom rules yet. Add rules like parking ratios, height limits, or project-specific requirements.
          </div>
        ) : (
          <div className="space-y-3">
            {rules.map((rule, idx) => (
              <RuleItem
                key={rule.id}
                rule={rule}
                onChange={(updated) => {
                  const next = [...rules];
                  next[idx] = updated;
                  setRules(next);
                  setDirty(true);
                }}
                onDelete={() => {
                  setRules(rules.filter((_, i) => i !== idx));
                  setDirty(true);
                }}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
