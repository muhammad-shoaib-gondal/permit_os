from __future__ import annotations

import asyncio
from difflib import SequenceMatcher
import html
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

import httpx

SOCRATA_API = "https://data.kcmo.org/resource"
CITY_PERMITS_DATASET = "w8jz-wjgn"
CPD_PERMITS_DATASET = "ntw8-aacc"
STATUS_HISTORY_DATASET = "6h9j-mu65"
CONTRACTOR_DIRECTORY = "https://city.kcmo.org/kc/Codes/LicensedContractors"
MOPRO_LICENSE_SEARCH = "https://mopro.mo.gov/license/s/license-search"

CONTRACTOR_LICENSE_TYPES = {
    "demolition": ["Demolition Contractor Class I", "Demolition Contractor Class II"],
    "electrical": [
        "Electrical Contractor Class I",
        "Electrical Contractor Class II",
        "Electrical Contractor Class III",
    ],
    "electrical_service": [
        "Electrical Contractor Class I",
        "Electrical Contractor Class II",
        "Electrical Contractor Class III",
    ],
    "elevator_state": ["Elevator Contractor Class I", "Elevator Contractor Class II"],
    "fire_sprinkler": [
        "Fire Protection Contractor Class I",
        "Fire Protection Contractor Class II",
        "Fire Protection Contractor Class III",
    ],
    "kitchen_hood_suppression": [
        "Fire Protection Contractor Class I",
        "Fire Protection Contractor Class II",
        "Fire Protection Contractor Class III",
    ],
    "mechanical": ["Mechanical Contractor", "Pipe Fitting Contractor"],
    "gas_piping": ["Gas-fired Appliance Contractor", "Pipe Fitting Contractor"],
    "plumbing": ["Plumbing Contractor"],
    "domestic_water_service": ["Plumbing Contractor"],
    "fire_water_service": ["Fire Protection Contractor Class I", "Plumbing Contractor"],
    "sanitary_sewer_connection": ["Plumbing Contractor"],
}


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_cell = False
        self.cell_parts: list[str] = []
        self.current_row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"td", "th"}:
            self.in_cell = True
            self.cell_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.in_cell:
            value = html.unescape(" ".join(self.cell_parts))
            self.current_row.append(" ".join(value.split()))
            self.in_cell = False
        elif tag == "tr" and self.current_row:
            self.rows.append(self.current_row)
            self.current_row = []


def _soql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


async def _get_json(url: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    return payload if isinstance(payload, list) else []


async def _permit_dataset_rows(dataset: str, field: str, permit_number: str) -> list[dict[str, Any]]:
    return await _get_json(
        f"{SOCRATA_API}/{dataset}.json",
        {
            "$where": f"upper({field})=upper({_soql_literal(permit_number)})",
            "$limit": 100,
        },
    )


def _dated_evidence(
    permit_number: str,
    label: str,
    date: Any,
    detail: str,
    source_url: str,
) -> dict[str, Any] | None:
    if not date:
        return None
    return {
        "document": f"KCMO public record {permit_number}: {label}",
        "page": None,
        "detail": detail,
        "sourceType": "dated_status_record",
        "date": str(date),
        "url": source_url,
        "provider": "kcmo_open_data",
    }


async def lookup_permit_record(permit_number: str) -> dict[str, Any]:
    number = permit_number.strip()
    if not number:
        return {"lookupStatus": "missing_identifier", "records": [], "evidence": []}

    city_rows, cpd_rows, history_rows = await asyncio.gather(
        _permit_dataset_rows(CITY_PERMITS_DATASET, "permit_number", number),
        _permit_dataset_rows(CPD_PERMITS_DATASET, "permitnum", number),
        _permit_dataset_rows(STATUS_HISTORY_DATASET, "permitnum", number),
    )
    records = [*city_rows, *cpd_rows]
    evidence: list[dict[str, Any]] = []
    city_url = f"https://data.kcmo.org/d/{CITY_PERMITS_DATASET}"
    cpd_url = f"https://data.kcmo.org/d/{CPD_PERMITS_DATASET}"
    history_url = f"https://data.kcmo.org/d/{STATUS_HISTORY_DATASET}"

    for row in city_rows:
        status = row.get("permit_status")
        for label, key in (
            ("application", "application_date"),
            ("issuance", "issue_date"),
            ("last inspection", "last_inspection_date"),
            ("final", "finaled_date"),
            ("expiration", "expiration_date"),
        ):
            item = _dated_evidence(
                number,
                label,
                row.get(key),
                f"{label.title()} date {row.get(key)}; current status {status or 'not stated'}.",
                city_url,
            )
            if item:
                evidence.append(item)

    for row in cpd_rows:
        status = row.get("statuscurrent")
        for label, key in (
            ("application", "applieddate"),
            ("issuance", "issueddate"),
            ("completion", "completeddate"),
            ("certificate of occupancy", "coissueddate"),
            ("hold", "holddate"),
            ("expiration", "expiresdate"),
            ("void", "voiddate"),
        ):
            item = _dated_evidence(
                number,
                label,
                row.get(key),
                f"{label.title()} date {row.get(key)}; current status {status or 'not stated'}.",
                cpd_url,
            )
            if item:
                evidence.append(item)

    for row in history_rows:
        date = row.get("statuspreviousdate") or row.get("applieddate")
        item = _dated_evidence(
            number,
            "status history",
            date,
            (
                f"Status changed from {row.get('statusprevious') or 'not stated'} to "
                f"{row.get('statuscurrent') or 'not stated'} on {date}. "
                f"{row.get('comments') or ''}"
            ).strip(),
            history_url,
        )
        if item:
            evidence.append(item)

    return {
        "lookupStatus": "found" if records or history_rows else "not_found",
        "permitNumber": number,
        "records": records,
        "statusHistory": history_rows,
        "evidence": evidence,
        "sources": [city_url, cpd_url, history_url],
        "retrievedAt": datetime.now(timezone.utc).isoformat(),
    }


def _hidden_value(page: str, name: str) -> str:
    match = re.search(
        rf'name="{re.escape(name)}"[^>]*value="([^"]*)"',
        page,
        re.IGNORECASE,
    )
    return html.unescape(match.group(1)) if match else ""


async def _contractors_for_license_type(license_type: str) -> list[dict[str, str]]:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        initial = await client.get(CONTRACTOR_DIRECTORY)
        initial.raise_for_status()
        page = initial.text
        response = await client.post(
            CONTRACTOR_DIRECTORY,
            data={
                "__VIEWSTATE": _hidden_value(page, "__VIEWSTATE"),
                "__VIEWSTATEGENERATOR": _hidden_value(page, "__VIEWSTATEGENERATOR"),
                "__EVENTVALIDATION": _hidden_value(page, "__EVENTVALIDATION"),
                "ctl00$MainContent$ddlLicenseType": license_type,
                "ctl00$MainContent$btnSearch": "Get Contractors List",
            },
        )
        response.raise_for_status()

    parser = _TableParser()
    parser.feed(response.text)
    if not parser.rows:
        return []
    headers = [value.casefold() for value in parser.rows[0]]
    output: list[dict[str, str]] = []
    for row in parser.rows[1:]:
        if len(row) != len(headers):
            continue
        output.append({headers[index]: value for index, value in enumerate(row)})
    return output


async def lookup_contractor(name: str, permit_type: str) -> dict[str, Any]:
    normalized = " ".join(name.casefold().split())
    if not normalized:
        return {"lookupStatus": "missing_identifier", "matches": [], "evidence": []}
    license_types = CONTRACTOR_LICENSE_TYPES.get(permit_type, [])
    if not license_types:
        return {
            "lookupStatus": "not_applicable",
            "matches": [],
            "evidence": [],
            "source": CONTRACTOR_DIRECTORY,
        }

    rows_by_type = await asyncio.gather(
        *(_contractors_for_license_type(license_type) for license_type in license_types),
        return_exceptions=True,
    )
    matches: list[dict[str, Any]] = []
    failures: list[str] = []
    for license_type, rows in zip(license_types, rows_by_type):
        if isinstance(rows, Exception):
            failures.append(license_type)
            continue
        for row in rows:
            company = str(row.get("company name") or "")
            company_normalized = " ".join(company.casefold().split())
            similarity = SequenceMatcher(None, normalized, company_normalized).ratio()
            if company_normalized == normalized or (
                min(len(normalized), len(company_normalized)) >= 8 and similarity >= 0.86
            ):
                matches.append({**row, "licenseType": license_type})

    evidence = [
        {
            "document": f"KCMO active contractor directory: {match.get('company name')}",
            "page": None,
            "detail": (
                f"{match.get('company name')} is listed as {match.get('licenseType')}; "
                f"license {match.get('license #') or 'not stated'} expires "
                f"{match.get('license expires') or 'not stated'}."
            ),
            "sourceType": "authoritative_registry",
            "url": CONTRACTOR_DIRECTORY,
            "provider": "kcmo_contractor_directory",
        }
        for match in matches
    ]
    return {
        "lookupStatus": "found" if matches else ("partial" if failures else "not_found"),
        "query": name,
        "permitType": permit_type,
        "matches": matches,
        "failedLicenseTypes": failures,
        "evidence": evidence,
        "source": CONTRACTOR_DIRECTORY,
        "retrievedAt": datetime.now(timezone.utc).isoformat(),
    }


async def collect_external_records(permits: list[Any]) -> dict[str, Any]:
    permit_queries: list[tuple[str, str]] = []
    contractor_queries: list[tuple[str, str]] = []
    for permit in permits:
        identifier = str(permit.application_number or permit.issued_number or "").strip()
        if identifier:
            permit_queries.append((permit.permit_type, identifier))
        contractor = str(permit.assigned_contractor or "").strip()
        if contractor:
            contractor_queries.append((permit.permit_type, contractor))

    permit_results = await asyncio.gather(
        *(lookup_permit_record(identifier) for _, identifier in permit_queries),
        return_exceptions=True,
    )
    contractor_results = await asyncio.gather(
        *(lookup_contractor(name, permit_type) for permit_type, name in contractor_queries),
        return_exceptions=True,
    )

    permit_records: dict[str, Any] = {}
    contractor_records: dict[str, Any] = {}
    evidence: list[dict[str, Any]] = []
    for (permit_type, identifier), result in zip(permit_queries, permit_results):
        if isinstance(result, Exception):
            result = {"lookupStatus": "failed", "error": str(result), "evidence": []}
        permit_records[permit_type] = result
        evidence.extend(
            {**item, "permitType": permit_type}
            for item in result.get("evidence", [])
        )
    for (permit_type, name), result in zip(contractor_queries, contractor_results):
        if isinstance(result, Exception):
            result = {"lookupStatus": "failed", "error": str(result), "evidence": []}
        contractor_records[permit_type] = result
        evidence.extend(
            {**item, "permitType": permit_type}
            for item in result.get("evidence", [])
        )

    return {
        "version": 1,
        "permitRecords": permit_records,
        "contractorRecords": contractor_records,
        "professionalLicenseProvider": {
            "lookupStatus": "interactive_only",
            "url": MOPRO_LICENSE_SEARCH,
            "acceptedFallback": "Upload an official MOPRO license-search result as a license record.",
        },
        "evidence": evidence,
        "retrievedAt": datetime.now(timezone.utc).isoformat(),
    }
