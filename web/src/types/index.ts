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

export type ProjectCategory = "single_family" | "multifamily" | "commercial";

export type ScopeTypeValue =
  | "new_construction"
  | "addition"
  | "alteration"
  | "repair"
  | "tenant_finish"
  | "change_of_use"
  | "demolition";

export type KcmoIntake = {
  project_category: ProjectCategory;
  scope_type: ScopeTypeValue;
  parcel_lot_number?: string | null;
  existing_use?: string | null;
  proposed_use?: string | null;
  estimated_valuation_usd?: number | null;
  building_area_sqft?: number | null;
  stories?: number | null;
  floodplain_status?: "unknown" | "yes" | "no";
  includes_electrical?: boolean;
  includes_plumbing?: boolean;
  includes_mechanical?: boolean;
  includes_fire_sprinkler_alarm?: boolean;
  affects_public_row?: boolean;
  owner_occupied?: boolean | null;
  dwelling_type?: "one_family" | "two_family" | null;
  residential_work_type?: "addition" | "remodel" | "new_home" | null;
  basement_finish?: boolean;
  accessory_structure?: boolean;
  driveway_work?: boolean;
  dwelling_units?: number | null;
  multifamily_form?: "apartments" | "townhomes" | "mixed_use_residential" | null;
  fire_separation_involved?: boolean | null;
  sprinklered?: "yes" | "no" | "unknown" | null;
  change_in_unit_count?: boolean;
  multiple_buildings?: boolean;
  business_use_type?: string | null;
  tenant_finish?: boolean;
  shell_building?: boolean;
  change_of_occupancy?: "yes" | "no" | "unknown" | null;
  occupancy_group?: string | null;
  construction_type?: string | null;
  public_access?: boolean;
  notes?: string | null;
};

export type ChecklistItem = {
  id: string;
  projectId: string;
  itemKey: string;
  label: string;
  category: string;
  requiredFor: string[];
  sourceTitle?: string | null;
  sourceUrl?: string | null;
  status: "missing" | "uploaded" | "waived" | "not_applicable";
  matchedFileId?: string | null;
  notes?: string | null;
};

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
  intake?: KcmoIntake | Record<string, unknown>;
  projectCategory?: ProjectCategory | null;
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
  category: string;
  group?: string;
  rule: string;
  condition?: string;
  severity?: CustomRule["severity"] | "critical" | "major";
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
    human_actions_required?: string[];
  };
  likely_permits?: Array<{
    permit_name: string;
    reason?: string;
    requirement_status?: string;
    source?: string;
  }>;
  data_gaps?: string[];
  fee_estimate?: {
    estimate_status?: string;
    warnings?: string[];
    line_items?: Array<{ label: string; amount?: number | null; basis?: string; source?: string }>;
  };
  findings?: Array<{
    status: string;
    module: string;
    finding: string;
    explanation: string;
    citation?: string;
  }>;
  kcmo?: boolean;
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

export const PROJECT_CATEGORIES = [
  { value: "single_family", label: "Single-family / one- and two-family residential" },
  { value: "multifamily", label: "Multifamily" },
  { value: "commercial", label: "Commercial" },
] as const;

export const SCOPE_TYPE_OPTIONS = [
  { value: "new_construction", label: "New construction" },
  { value: "addition", label: "Addition" },
  { value: "alteration", label: "Alteration" },
  { value: "repair", label: "Repair" },
  { value: "tenant_finish", label: "Tenant finish" },
  { value: "change_of_use", label: "Change of use" },
  { value: "demolition", label: "Demolition" },
] as const;

export const DEFAULT_KCMO_INTAKE: KcmoIntake = {
  project_category: "commercial",
  scope_type: "alteration",
  floodplain_status: "unknown",
  includes_electrical: false,
  includes_plumbing: false,
  includes_mechanical: false,
  includes_fire_sprinkler_alarm: false,
  affects_public_row: false,
  basement_finish: false,
  accessory_structure: false,
  driveway_work: false,
  change_in_unit_count: false,
  multiple_buildings: false,
  tenant_finish: false,
  shell_building: false,
  public_access: false,
  sprinklered: "unknown",
  change_of_occupancy: "unknown",
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
