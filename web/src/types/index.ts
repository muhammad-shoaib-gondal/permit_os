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
  | "new_commercial_construction"
  | "mixed_use"
  | "industrial";

export type ProjectScope = {
  new_construction: boolean;
  addition: boolean;
  alteration: boolean;
  repair: boolean;
  demolition: boolean;
  structural_work: boolean;
  electrical_work: boolean;
  plumbing_work: boolean;
  mechanical_hvac_work: boolean;
  fire_alarm_sprinkler_work: boolean;
  signs: boolean;
  change_use_occupancy: boolean;
  grading_land_disturbance: boolean;
  driveway_sidewalk_row: boolean;
  solar_battery_generator_ev: boolean;
  water_sewer_connections: boolean;
};

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
  category: "zoning" | "building" | "fire" | "site" | "environmental" | "custom" | "permit";
  rule: string;
  condition: string;
  severity: "blocker" | "warning" | "info";
  enabled: boolean;
  area?: string;
  permitType?: string;
  source?: string;
  builtinRuleId?: string;
  systemManaged?: boolean;
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

export type ProjectPermit = {
  id: string;
  projectId: string;
  permitType: string;
  permitName: string;
  issuingAuthority: string;
  jurisdiction: string;
  requirementStatus: string;
  lifecycleStatus: string;
  origin: "system" | "manual";
  reason?: string | null;
  recommendationEvidence?: {
    catalogRule?: {
      permitId?: string;
      permitName?: string;
      supportedDevelopmentTypes?: string[];
      defaultForDevelopmentTypes?: string[];
      appliesWhenAny?: string[];
      ruleFamilyId?: string;
      applicationId?: string;
      category?: string;
      ruleIds?: string[];
      sourceIds?: string[];
    };
    projectFacts?: {
      jurisdiction?: string;
      projectType?: string;
      projectTypeMatchedAs?: string[];
      selectedScope?: string[];
      activeScopeAliases?: string[];
    };
    matchResult?: {
      triggeredBy?: string[];
      defaultMatch?: boolean;
      developmentTypeMatch?: boolean;
      classification?: string;
      policy?: string;
      usesVectorOrLlm?: boolean;
    };
  };
  source?: string | null;
  portalUrl?: string | null;
  coverageStatus?: string | null;
  parentPermitId?: string | null;
  dependencies: string[];
  requiredDocuments: string[];
  missingDocumentCount: number;
  assignedEmployee?: string | null;
  assignedContractor?: string | null;
  estimatedFeeUsd?: number | null;
  actualFeeUsd?: number | null;
  applicationNumber?: string | null;
  issuedNumber?: string | null;
  currentBlocker?: string | null;
  nextAction?: string | null;
  createdAt: string;
  updatedAt: string;
};

export type Project = {
  id: string;
  name: string;
  address: string;
  projectType: ProjectTypeValue;
  jurisdiction: string;
  area?: string | null;
  zoningStatus?:
    | "pending"
    | "resolved"
    | "resolved_with_warnings"
    | "invalid_address"
    | "zoning_not_found"
    | "service_unavailable"
    | "unsupported";
  zoningProfile?: {
    inputAddress?: string;
    matchedAddress?: string;
    matchScore?: number;
    addressType?: string;
    city?: string;
    region?: string;
    postalCode?: string;
    latitude?: number;
    longitude?: number;
    district?: string;
    districts?: string[];
    districtName?: string;
    landUse?: string;
    ordinance?: string;
    attributes?: Record<string, string>;
    sourceName?: string;
    sourceUrl?: string;
    resolvedAt?: string;
  };
  zoningWarnings?: Array<{
    code: string;
    message: string;
    action: string;
    severity: "error" | "warning" | "info";
  }>;
  scope?: ProjectScope;
  files: ProjectFile[];
  permits?: ProjectPermit[];
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
  id?: string;
  category: string;
  group?: string;
  rule: string;
  condition?: string;
  severity?: CustomRule["severity"] | "critical" | "major";
  source: string;
  permitTypes?: string[];
  ruleFamilyIds?: string[];
};

export type BuiltinRuleGroup = {
  key: AnalysisModuleKey | "permits";
  label: string;
  sourceSummary?: string;
  rules: BuiltinRule[];
};

export type ActivityEvent = {
  timestamp: string;
  source: string;
  event_type: string;
  detail: string;
  payload?: Record<string, unknown>;
};

export type CaseResults = {
  case_id: string;
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
    documents_required: { name: string; source_section: string }[];
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
  completed_sections?: string[];
};

export const PROJECT_TYPES = [
  { value: "multifamily_residential", label: "Multifamily residential" },
  { value: "single_family", label: "Single family" },
  { value: "commercial", label: "Commercial" },
  { value: "commercial_tenant_improvement", label: "Commercial tenant improvement" },
  { value: "new_commercial_construction", label: "New commercial construction" },
  { value: "mixed_use", label: "Mixed use" },
  { value: "industrial", label: "Industrial" },
] as const;

export const PROJECT_SCOPE_OPTIONS = [
  { value: "new_construction", label: "New construction" },
  { value: "addition", label: "Addition" },
  { value: "alteration", label: "Alteration" },
  { value: "repair", label: "Repair" },
  { value: "demolition", label: "Demolition" },
  { value: "structural_work", label: "Structural work" },
  { value: "electrical_work", label: "Electrical work" },
  { value: "plumbing_work", label: "Plumbing work" },
  { value: "mechanical_hvac_work", label: "Mechanical / HVAC work" },
  { value: "fire_alarm_sprinkler_work", label: "Fire alarm or sprinkler work" },
  { value: "signs", label: "Signs" },
  { value: "change_use_occupancy", label: "Change of use or occupancy" },
  { value: "grading_land_disturbance", label: "Grading / land disturbance" },
  { value: "driveway_sidewalk_row", label: "Driveway, sidewalk, or right-of-way impact" },
  { value: "solar_battery_generator_ev", label: "Solar, battery, generator, or EV charger" },
  { value: "water_sewer_connections", label: "Water or sewer connections" },
] as const;

export const DEFAULT_PROJECT_SCOPE: ProjectScope = {
  new_construction: false,
  addition: false,
  alteration: false,
  repair: false,
  demolition: false,
  structural_work: false,
  electrical_work: false,
  plumbing_work: false,
  mechanical_hvac_work: false,
  fire_alarm_sprinkler_work: false,
  signs: false,
  change_use_occupancy: false,
  grading_land_disturbance: false,
  driveway_sidewalk_row: false,
  solar_battery_generator_ev: false,
  water_sewer_connections: false,
};

export const PERMIT_REQUIREMENT_STATUS_OPTIONS = [
  { value: "suggested", label: "Suggested" },
  { value: "required", label: "Required" },
  { value: "likely_required", label: "Likely required" },
  { value: "optional", label: "Optional" },
  { value: "needs_confirmation", label: "Needs confirmation" },
  { value: "not_required", label: "Not required" },
  { value: "removed_by_user", label: "Removed by user" },
  { value: "manual", label: "Manually added" },
] as const;

export const PERMIT_LIFECYCLE_STATUS_OPTIONS = [
  { value: "not_started", label: "Not started" },
  { value: "gathering_documents", label: "Gathering documents" },
  { value: "blocked", label: "Blocked" },
  { value: "ready_for_human_review", label: "Ready for human review" },
  { value: "ready_to_submit", label: "Ready to submit" },
  { value: "submitted", label: "Submitted" },
  { value: "application_accepted", label: "Application accepted" },
  { value: "in_review", label: "In review" },
  { value: "corrections_requested", label: "Corrections requested" },
  { value: "resubmitted", label: "Resubmitted" },
  { value: "approved", label: "Approved" },
  { value: "ready_for_issuance", label: "Ready for issuance" },
  { value: "issued", label: "Issued" },
  { value: "inspection_phase", label: "Inspection phase" },
  { value: "finaled", label: "Finaled" },
  { value: "cancelled", label: "Cancelled" },
  { value: "expired", label: "Expired" },
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
  { value: "fire", label: "Fire / Life Safety" },
  { value: "site", label: "Site" },
  { value: "environmental", label: "Environmental" },
  { value: "custom", label: "Custom" },
  { value: "permit", label: "Permit administration" },
] as const;
