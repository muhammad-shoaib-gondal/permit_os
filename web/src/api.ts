export type Check = {
  rule: string;
  status: "pass" | "fail" | "warn";
  citation: string;
  detail: string;
  category?: string;
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
  stalled?: boolean;
  stall_reason?: string;
  phase?: string;
  completed_agents?: string[];
};

export const PROJECT_TYPES = [
  { value: "multifamily_residential", label: "Multifamily residential" },
  { value: "single_family", label: "Single family" },
  { value: "commercial", label: "Commercial" },
  { value: "mixed_use", label: "Mixed use" },
  { value: "industrial", label: "Industrial" },
] as const;

export const JURISDICTIONS = [{ value: "austin_tx", label: "Austin, TX" }] as const;

export type ProjectTypeValue = (typeof PROJECT_TYPES)[number]["value"];

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

export async function analyzeProject(
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
  if (!start.ok) throw new Error(INCOMPLETE_MSG);

  const { case_id } = (await start.json()) as { case_id: string };
  return pollCase(case_id, onProgress);
}

/** @deprecated Use analyzeProject with sample JSON instead */
export async function runDemo(
  onProgress?: (partial: CaseResults & { status?: string; completed_agents?: string[] }) => void
): Promise<CaseResults> {
  let start: Response;
  try {
    start = await fetch(`${API}/cases/demo/riverside`, { method: "POST" });
  } catch {
    throw new Error(INCOMPLETE_MSG);
  }
  if (!start.ok) throw new Error(INCOMPLETE_MSG);

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
