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
  brief: Record<string, unknown>;
  jurisdiction_report: {
    summary: string;
    checks: Check[];
    blockers: string[];
    zoning?: { district: string; by_right: boolean };
  };
  building_report: { summary: string; checks: Check[] };
  site_report: {
    summary: string;
    environmental_checks: Check[];
    utility_checks: Check[];
  };
  case_summary: {
    readiness_score: string;
    conflicts: { issue: string; suggested_fix: string; severity: string }[];
    executive_summary?: string;
    status: string;
  };
  permit_package: {
    permits_required: { permit_name: string; agency: string; fee_usd: number; timeline_days: number }[];
    documents_required: { name: string; source_agent: string }[];
    total_fees_estimate_usd: number;
    estimated_timeline_days: number;
    filing_sequence: string[];
    audit_hash?: string;
  };
  activity?: ActivityEvent[];
};

const API = import.meta.env.VITE_API_URL || "";

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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

export async function runDemo(
  onProgress?: (partial: CaseResults & { status?: string; completed_agents?: string[] }) => void
): Promise<CaseResults> {
  let start: Response;
  try {
    start = await fetch(`${API}/cases/demo/riverside`, { method: "POST" });
  } catch {
    throw new Error(
      "Cannot reach the API. Ensure uvicorn is running on port 8000 and the Vite dev server is on port 5173."
    );
  }
  if (!start.ok) throw new Error(await parseError(start));

  const { case_id } = (await start.json()) as { case_id: string };

  const deadline = Date.now() + 11 * 60 * 1000;
  while (Date.now() < deadline) {
    await sleep(3000);
    let poll: Response;
    try {
      poll = await fetch(`${API}/cases/${case_id}`);
    } catch {
      throw new Error("Lost connection while waiting for Band agents. Check API and agent terminals.");
    }
    if (!poll.ok) throw new Error(await parseError(poll));

    const data = await poll.json();
    if (data.status === "FAILED") {
      const hint = data.results?.hint ? `\n\n${data.results.hint}` : "";
      throw new Error((data.error || data.results?.error || "Band analysis failed") + hint);
    }
    if (data.results?.jurisdiction_report) {
      onProgress?.({
        case_id,
        status: data.status,
        completed_agents: data.results.completed_agents,
        ...data.results,
      } as CaseResults & { status?: string; completed_agents?: string[] });
    }
    if (data.results?.jurisdiction_report && data.results?.permit_package) {
      return { case_id, ...data.results };
    }
  }

  throw new Error(
    "Timed out waiting for Band agents (11 min). " +
      "Agents may be rate-limited — wait 1–2 minutes and retry, or check agent terminal logs."
  );
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
