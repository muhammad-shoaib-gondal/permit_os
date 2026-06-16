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

export async function runDemo(): Promise<CaseResults> {
  const res = await fetch(`${API}/cases/demo/riverside`);
  if (!res.ok) {
    let detail = await res.text();
    try {
      const body = JSON.parse(detail);
      detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      /* plain text */
    }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export async function approveCase(caseId: string): Promise<Record<string, unknown>> {
  const res = await fetch(`${API}/cases/${caseId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approved_by: "human-reviewer" }),
  });
  if (!res.ok) throw new Error(await res.text());
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
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getDisclaimer(): Promise<string> {
  const res = await fetch(`${API}/disclaimer`);
  const data = await res.json();
  return data.disclaimer;
}
