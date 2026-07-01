import type {
  AnalysisModuleKey,
  BuiltinRule,
  BuiltinRuleGroup,
  CaseResults,
  CustomRule,
  Jurisdiction,
  Project,
  ProjectTypeValue,
} from "./types";

export type { Check, CaseResults, Project, CustomRule, Jurisdiction } from "./types";
export { PROJECT_TYPES, FILE_TYPES, RULE_CATEGORIES } from "./types";
export { ANALYSIS_MODULES } from "./types";

const API = import.meta.env.VITE_API_URL || "";

const INCOMPLETE_MSG = "Something went wrong — we couldn't complete the analysis.";

const STALL_WITH_REPORTS_MS = 3 * 60 * 1000;
const STALL_EMPTY_MS = 2 * 60 * 1000;

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function hasSpecialistReports(r: Record<string, unknown> | undefined): boolean {
  return !!(
    r?.jurisdiction_report ||
    r?.building_report ||
    r?.site_report ||
    r?.case_summary
  );
}

function specialistsDone(r: Record<string, unknown> | undefined): boolean {
  return !!(r?.jurisdiction_report && r?.building_report && r?.site_report);
}

function hasPermitPackage(r: Record<string, unknown> | undefined): boolean {
  const pkg = r?.permit_package as { permits_required?: unknown[] } | undefined;
  return Array.isArray(pkg?.permits_required) && pkg.permits_required.length > 0;
}

function progressFingerprint(data: {
  status?: string;
  is_stale?: boolean;
  results?: Record<string, unknown>;
}): string {
  const r = data.results;
  return JSON.stringify({
    status: data.status,
    phase: r?.phase,
    completed: r?.completed_agents,
    last: r?.last_progress_at,
    stale: data.is_stale,
  });
}

async function parseError(res: Response): Promise<string> {
  let detail = await res.text();
  try {
    const body = JSON.parse(detail);
    detail = typeof body.detail === "string" ? body.detail : detail;
  } catch {
    /* plain text */
  }
  return detail || `Request failed (${res.status})`;
}

function partialFromPoll(
  case_id: string,
  data: Record<string, unknown>
): CaseResults & { status?: string } {
  const r = (data.results ?? {}) as Record<string, unknown>;
  return {
    case_id,
    status: data.status as string | undefined,
    stalled: Boolean(data.stalled || r.stalled || data.is_stale),
    stall_reason: (data.stall_reason || r.stall_reason || r.error || INCOMPLETE_MSG) as string,
    ...r,
  } as CaseResults & { status?: string };
}

export async function pollCase(
  case_id: string,
  onProgress?: (partial: CaseResults & { status?: string; completed_agents?: string[] }) => void
): Promise<CaseResults> {
  const deadline = Date.now() + 11 * 60 * 1000;
  let lastFp = "";
  let lastChangeAt = Date.now();

  while (Date.now() < deadline) {
    await sleep(3000);
    let poll: Response;
    try {
      poll = await fetch(`${API}/cases/${case_id}`);
    } catch {
      throw new Error(INCOMPLETE_MSG);
    }
    if (!poll.ok) throw new Error(await parseError(poll));

    const data = await poll.json();
    const r = data.results as Record<string, unknown> | undefined;

    const fp = progressFingerprint(data);
    if (fp !== lastFp) {
      lastFp = fp;
      lastChangeAt = Date.now();
    }

    if (hasSpecialistReports(r)) {
      onProgress?.(partialFromPoll(case_id, data));
    }

    if (data.status === "AWAITING_APPROVAL" || data.status === "APPROVED_FOR_FILING") {
      return partialFromPoll(case_id, data);
    }

    if (specialistsDone(r) && hasPermitPackage(r)) {
      return partialFromPoll(case_id, data);
    }

    if (data.status === "FAILED" || data.stalled || r?.stalled) {
      if (hasSpecialistReports(r)) {
        return partialFromPoll(case_id, data);
      }
      throw new Error(INCOMPLETE_MSG);
    }

    if (data.status === "ANALYZING" && data.is_stale && hasSpecialistReports(r)) {
      return {
        ...partialFromPoll(case_id, data),
        stalled: true,
        stall_reason: INCOMPLETE_MSG,
      };
    }

    const stallLimit = hasSpecialistReports(r) ? STALL_WITH_REPORTS_MS : STALL_EMPTY_MS;
    if (data.status === "ANALYZING" && Date.now() - lastChangeAt > stallLimit) {
      if (hasSpecialistReports(r)) {
        return {
          ...partialFromPoll(case_id, data),
          stalled: true,
          stall_reason: INCOMPLETE_MSG,
        };
      }
      throw new Error(INCOMPLETE_MSG);
    }
  }

  throw new Error(INCOMPLETE_MSG);
}

export async function analyzeUpload(
  file: File,
  projectType: ProjectTypeValue,
  jurisdiction: string,
  onProgress?: (partial: CaseResults & { status?: string; completed_agents?: string[] }) => void
): Promise<CaseResults> {
  const form = new FormData();
  form.append("file", file);
  form.append("project_type", projectType);
  form.append("jurisdiction", jurisdiction);

  let start: Response;
  try {
    start = await fetch(`${API}/cases/analyze`, { method: "POST", body: form });
  } catch {
    throw new Error(INCOMPLETE_MSG);
  }
  if (!start.ok) throw new Error(await parseError(start));

  const { case_id } = (await start.json()) as { case_id: string };
  return pollCase(case_id, onProgress);
}

export async function approveCase(caseId: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${API}/cases/${caseId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved_by: "human-reviewer" }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function simulateRfi(caseId: string): Promise<{ draft: string }> {
  const res = await fetch(`${API}/cases/${caseId}/rfi`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      rfi_text: "Provide fire apparatus access diagram for Block B east setback area.",
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function getDisclaimer(): Promise<string> {
  const res = await fetch(`${API}/disclaimer`);
  const data = await res.json();
  return data.disclaimer;
}

// --- Projects API ---

export async function listProjects(): Promise<Project[]> {
  const res = await fetch(`${API}/projects`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function getProject(id: string): Promise<Project> {
  const res = await fetch(`${API}/projects/${id}`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function createProject(data: Partial<Project>): Promise<Project> {
  const res = await fetch(`${API}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: data.name,
      address: data.address,
      projectType: data.projectType ?? "multifamily_residential",
      jurisdiction: data.jurisdiction ?? "austin_tx",
      area: data.area ?? null,
      customRules: data.customRules ?? [],
    }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function updateProject(id: string, data: Partial<Project>): Promise<Project> {
  const res = await fetch(`${API}/projects/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function deleteProject(id: string): Promise<void> {
  const res = await fetch(`${API}/projects/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function uploadProjectFile(
  projectId: string,
  file: File,
  fileType?: string,
  isPrimaryBrief?: boolean,
  documentLabel?: string,
  fileSections?: AnalysisModuleKey[]
): Promise<void> {
  const form = new FormData();
  form.append("file", file);
  if (fileType) form.append("file_type", fileType);
  if (isPrimaryBrief) form.append("is_primary_brief", "true");
  if (documentLabel) form.append("document_label", documentLabel);
  if (fileSections?.length) form.append("file_sections", JSON.stringify(fileSections));
  const res = await fetch(`${API}/projects/${projectId}/files`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function deleteProjectFile(projectId: string, fileId: string): Promise<void> {
  const res = await fetch(`${API}/projects/${projectId}/files/${fileId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function getProjectRules(
  projectId: string
): Promise<{ customRules: CustomRule[]; builtinRules: BuiltinRule[]; builtinGroups: BuiltinRuleGroup[] }> {
  const res = await fetch(`${API}/projects/${projectId}/rules`);
  if (!res.ok) throw new Error(await parseError(res));
  const data = await res.json();
  const groupsMap = new Map<string, BuiltinRuleGroup>();
  for (const rule of (data.builtinRules as BuiltinRule[])) {
    const key = (rule.group || rule.category || "permits") as BuiltinRuleGroup["key"];
    if (!groupsMap.has(key)) {
      groupsMap.set(key, { key, label: groupLabel(key), rules: [] });
    }
    groupsMap.get(key)!.rules.push(rule);
  }
  return { ...data, builtinGroups: Array.from(groupsMap.values()) };
}

export async function saveProjectRules(projectId: string, rules: CustomRule[]): Promise<void> {
  const res = await fetch(`${API}/projects/${projectId}/rules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(rules),
  });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function analyzeProjectById(
  projectId: string,
  modules?: AnalysisModuleKey[]
): Promise<{ case_id: string }> {
  const res = await fetch(`${API}/projects/${projectId}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ modules: modules ?? [] }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function analyzeProject(
  projectId: string,
  modules?: AnalysisModuleKey[],
  onProgress?: (partial: CaseResults) => void
): Promise<CaseResults> {
  const { case_id } = await analyzeProjectById(projectId, modules);
  return pollCase(case_id, onProgress);
}

function groupLabel(key: string): string {
  switch (key) {
    case "zoning":
      return "Zoning";
    case "building":
      return "Building";
    case "fire":
      return "Fire / Life Safety";
    case "site":
      return "Site / Utilities";
    case "permits":
      return "Permits";
    default:
      return key;
  }
}

export async function suggestRules(projectId: string): Promise<CustomRule[]> {
  const res = await fetch(`${API}/projects/${projectId}/suggest-rules`, { method: "POST" });
  if (!res.ok) throw new Error(await parseError(res));
  const data = await res.json();
  return data.rules as CustomRule[];
}

export async function listJurisdictions(): Promise<Jurisdiction[]> {
  const res = await fetch(`${API}/jurisdictions`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}
