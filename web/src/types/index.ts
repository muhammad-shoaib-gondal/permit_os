export type Check = {
  rule: string;
  status: "pass" | "fail" | "warn";
  citation: string;
  detail: string;
  category?: string;
};

export type ProjectTypeValue =
  | "multifamily_residential"
  | "single_family"
  | "commercial"
  | "commercial_tenant_improvement"
  | "mixed_use"
  | "industrial";

export type FileType =
  | "brief_json"
  | "site_plan"
  | "floor_plan"
  | "code_analysis"
  | "fire_plan"
  | "mechanical_plan"
  | "plumbing_plan"
  | "electrical_plan"
  | "elevation"
  | "survey"
  | "other";

export type AnalysisModuleKey = "zoning" | "building" | "fire" | "site";

export type CustomRule = {
  id: string;
  category: "zoning" | "building" | "site" | "environmental" | "custom" | "permit";
  rule: string;
  condition: string;
  severity: "blocker" | "warning" | "info";
  enabled: boolean;
  area?: string;
};

export type ProjectFile = {
  id: string;
  name: string;
  type: FileType;
  label?: string;
  size: number;
  sections?: AnalysisModuleKey[];
  uploadedAt: string;
  isPrimaryBrief?: boolean;
};

export type AnalysisRun = {
  caseId: string;
  status: string;
  createdAt: string;
  readiness?: string;
};

export type Project = {
  id: string;
  name: string;
  address: string;
  projectType: ProjectTypeValue;
  jurisdiction: string;
  area?: string | null;
  files: ProjectFile[];
  customRules: CustomRule[];
  moduleRequirements?: Record<
    string,
    {
      label: string;
      requiredAnyOf: FileType[];
      recommendedFileTypes: FileType[];
      requiredMissing: FileType[];
      recommendedMissing: FileType[];
      canRun: boolean;
      hasMappedFiles: boolean;
      summary?: string;
    }
  >;
  analyses: AnalysisRun[];
  lastAnalysisStatus?: string;
  readinessScore?: string;
  createdAt: string;
  updatedAt: string;
};

export type Jurisdiction = {
  id: string;
  label: string;
  state: string;
  city: string;
  coverage_status: string;
};

export type BuiltinRule = {
  category: string;
  group?: string;
  rule: string;
  source: string;
};

export type BuiltinRuleGroup = {
  key: AnalysisModuleKey | "permits";
  label: string;
  sourceSummary?: string;
  rules: BuiltinRule[];
};

export type ActivityEvent = {
  timestamp: string;
  agent: string;
  event_type: string;
  detail: string;
  payload?: Record<string, unknown>;
};

export type CaseResults = {
  case_id: string;
  band_room_id?: string;
  brief?: Record<string, unknown>;
  jurisdiction_report?: {
    summary: string;
    checks: Check[];
    blockers: string[];
    zoning?: { district: string; by_right: boolean };
  };
  building_report?: { summary: string; checks: Check[] };
  site_report?: {
    summary: string;
    environmental_checks: Check[];
    utility_checks: Check[];
  };
  custom_rules_report?: {
    summary: string;
    checks: Check[];
  };
  case_summary?: {
    readiness_score: string;
    conflicts: { issue: string; suggested_fix: string; severity: string }[];
    executive_summary?: string;
    status: string;
  };
  permit_package?: {
    permits_required: { permit_name: string; agency: string; fee_usd: number; timeline_days: number }[];
    documents_required: { name: string; source_agent: string }[];
    total_fees_estimate_usd: number;
    estimated_timeline_days: number;
    filing_sequence: string[];
    audit_hash?: string;
  };
  activity?: ActivityEvent[];
  selected_modules?: AnalysisModuleKey[];
  module_requirements?: Record<
    string,
    {
      label: string;
      requiredAnyOf: FileType[];
      recommendedFileTypes: FileType[];
      requiredMissing: FileType[];
      recommendedMissing: FileType[];
      canRun: boolean;
      hasMappedFiles: boolean;
      summary?: string;
    }
  >;
  rule_groups?: {
    key: string;
    label: string;
    checks: Check[];
  }[];
  stalled?: boolean;
  stall_reason?: string;
  phase?: string;
  completed_agents?: string[];
};

export const PROJECT_TYPES = [
  { value: "multifamily_residential", label: "Multifamily residential" },
  { value: "single_family", label: "Single family" },
  { value: "commercial", label: "Commercial" },
  { value: "commercial_tenant_improvement", label: "Commercial tenant improvement" },
  { value: "mixed_use", label: "Mixed use" },
  { value: "industrial", label: "Industrial" },
] as const;

export const FILE_TYPES = [
  { value: "brief_json", label: "Project brief" },
  { value: "site_plan", label: "Site plan" },
  { value: "floor_plan", label: "Floor plan" },
  { value: "code_analysis", label: "Code analysis" },
  { value: "fire_plan", label: "Fire / life safety plan" },
  { value: "mechanical_plan", label: "Mechanical plan" },
  { value: "plumbing_plan", label: "Plumbing plan" },
  { value: "electrical_plan", label: "Electrical plan" },
  { value: "elevation", label: "Elevation" },
  { value: "survey", label: "Survey" },
  { value: "other", label: "Other" },
] as const;

export const ANALYSIS_MODULES = [
  { value: "zoning", label: "Zoning" },
  { value: "building", label: "Building" },
  { value: "fire", label: "Fire / Life Safety" },
  { value: "site", label: "Site / Utilities" },
] as const;

export const RULE_CATEGORIES = [
  { value: "zoning", label: "Zoning" },
  { value: "building", label: "Building" },
  { value: "site", label: "Site" },
  { value: "environmental", label: "Environmental" },
  { value: "custom", label: "Custom" },
] as const;
