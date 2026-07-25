import jsPDF from "jspdf";
import autoTable from "jspdf-autotable";
import type { CaseResults, Project } from "../types";

export function downloadAnalysisReport(project: Project, data: CaseResults) {
  const doc = new jsPDF();
  const margin = 14;
  let y = 20;

  doc.setFontSize(20);
  doc.setTextColor(61, 156, 245);
  doc.text("EstatePermit Analysis Report", margin, y);
  y += 12;

  doc.setFontSize(11);
  doc.setTextColor(60, 60, 60);
  doc.text(`Project: ${project.name}`, margin, y);
  y += 6;
  doc.text(`Address: ${project.address}`, margin, y);
  y += 6;
  doc.text(`Jurisdiction: ${project.jurisdiction}`, margin, y);
  y += 6;
  doc.text(`Type: ${project.projectType}`, margin, y);
  y += 6;
  doc.text(`Generated: ${new Date().toLocaleString()}`, margin, y);
  y += 6;
  if (data.case_id) doc.text(`Case ID: ${data.case_id}`, margin, y);
  y += 10;

  const readiness = data.case_summary?.readiness_score ?? "-";
  doc.setFontSize(14);
  doc.setTextColor(0, 0, 0);
  doc.text(`Readiness: ${readiness}`, margin, y);
  y += 8;

  if (data.case_summary?.executive_summary) {
    doc.setFontSize(10);
    const lines = doc.splitTextToSize(data.case_summary.executive_summary, 180);
    doc.text(lines, margin, y);
    y += lines.length * 5 + 6;
  }

  const sections: { title: string; checks: { rule: string; status: string; detail: string; citation: string }[] }[] = [
    { title: "Jurisdiction & Zoning", checks: data.jurisdiction_report?.checks ?? [] },
    { title: "Building & Safety", checks: data.building_report?.checks ?? [] },
    {
      title: "Site & Environmental",
      checks: [
        ...(data.site_report?.environmental_checks ?? []),
        ...(data.site_report?.utility_checks ?? []),
      ],
    },
    { title: "Custom Rules", checks: data.custom_rules_report?.checks ?? [] },
  ];

  for (const section of sections) {
    if (!section.checks.length) continue;
    if (y > 250) {
      doc.addPage();
      y = 20;
    }
    doc.setFontSize(12);
    doc.setTextColor(61, 156, 245);
    doc.text(section.title, margin, y);
    y += 4;
    autoTable(doc, {
      startY: y,
      head: [["Rule", "Status", "Detail", "Citation"]],
      body: section.checks.map((c) => [c.rule, c.status, c.detail, c.citation]),
      styles: { fontSize: 8 },
      margin: { left: margin },
    });
    y = (doc as jsPDF & { lastAutoTable: { finalY: number } }).lastAutoTable.finalY + 10;
  }

  if (data.permit_package) {
    if (y > 240) {
      doc.addPage();
      y = 20;
    }
    doc.setFontSize(12);
    doc.text("Permit Package Summary", margin, y);
    y += 6;
    doc.setFontSize(10);
    doc.text(`Est. fees: $${data.permit_package.total_fees_estimate_usd.toLocaleString()}`, margin, y);
    y += 5;
    doc.text(`Timeline: ${data.permit_package.estimated_timeline_days} days`, margin, y);
    y += 8;
  }

  if (data.case_summary?.conflicts?.length) {
    doc.setFontSize(12);
    doc.text("Conflicts & Fixes", margin, y);
    y += 6;
    for (const c of data.case_summary.conflicts) {
      doc.setFontSize(9);
      const lines = doc.splitTextToSize(`${c.issue}: ${c.suggested_fix}`, 180);
      doc.text(lines, margin, y);
      y += lines.length * 4 + 4;
    }
  }

  const hash = data.permit_package?.audit_hash;
  doc.setFontSize(8);
  doc.setTextColor(120, 120, 120);
  const footerY = doc.internal.pageSize.height - 10;
  doc.text(
    `EstatePermit pre-screening report - not legal advice${hash ? ` | Audit: ${hash.slice(0, 16)}...` : ""}`,
    margin,
    footerY
  );

  const safeName = project.name.replace(/[^a-z0-9]/gi, "_").toLowerCase();
  doc.save(`straight-permit-report-${safeName}.pdf`);
}
