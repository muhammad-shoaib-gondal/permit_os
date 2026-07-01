import { ToggleLeft, ToggleRight, Trash2 } from "lucide-react";
import type { CustomRule } from "../../types";
import { RULE_CATEGORIES } from "../../types";
import { Button } from "../common/Button";
import { Input, Select } from "../common/Input";
import { Badge } from "../common/Badge";

type RuleItemProps = {
  rule: CustomRule;
  onChange: (rule: CustomRule) => void;
  onDelete: () => void;
};

export function RuleItem({ rule, onChange, onDelete }: RuleItemProps) {
  return (
    <div className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-4">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge>{rule.category}</Badge>
          <Badge variant={rule.severity === "blocker" ? "fail" : rule.severity === "warning" ? "warn" : "default"}>
            {rule.severity}
          </Badge>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => onChange({ ...rule, enabled: !rule.enabled })}
            className="text-[var(--color-muted)] hover:text-[var(--color-text)]"
            aria-label={rule.enabled ? "Disable rule" : "Enable rule"}
          >
            {rule.enabled ? <ToggleRight size={22} className="text-[var(--color-accent)]" /> : <ToggleLeft size={22} />}
          </button>
          <Button variant="ghost" size="sm" onClick={onDelete}>
            <Trash2 size={16} />
          </Button>
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <Input
          label="Rule"
          value={rule.rule}
          onChange={(e) => onChange({ ...rule, rule: e.target.value })}
        />
        <Select
          label="Category"
          value={rule.category}
          options={RULE_CATEGORIES.map((c) => ({ value: c.value, label: c.label }))}
          onChange={(e) => onChange({ ...rule, category: e.target.value as CustomRule["category"] })}
        />
        <Input
          label="Condition (what to check)"
          value={rule.condition}
          onChange={(e) => onChange({ ...rule, condition: e.target.value })}
          className="md:col-span-2"
        />
        <Input
          label="Area / District (optional)"
          value={rule.area ?? ""}
          onChange={(e) => onChange({ ...rule, area: e.target.value })}
        />
        <Select
          label="Severity"
          value={rule.severity}
          options={[
            { value: "blocker", label: "Blocker" },
            { value: "warning", label: "Warning" },
            { value: "info", label: "Info" },
          ]}
          onChange={(e) => onChange({ ...rule, severity: e.target.value as CustomRule["severity"] })}
        />
      </div>
    </div>
  );
}
