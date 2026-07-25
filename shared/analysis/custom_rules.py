"""Evidence-grounded evaluation for project and system review rules."""

from __future__ import annotations

import base64
import asyncio
import json
import logging
import mimetypes
from pathlib import Path
from typing import Any

from shared.analysis.rule_execution import execution_contract, missing_evidence_detail, relevant_documents
from shared.llm.zenmux import chat_completion
from shared.schemas.project_brief import ProjectBrief
from shared.schemas.reports import CheckResult, CheckStatus

logger = logging.getLogger(__name__)

RULE_BATCH_SIZE = 16
RULE_BATCH_CONCURRENCY = 4
MAX_ATTACHED_DOCUMENTS = 6
MAX_TOTAL_ATTACHMENT_BYTES = 30 * 1024 * 1024


def _status(raw: str) -> CheckStatus:
    try:
        return CheckStatus(raw.lower())
    except ValueError:
        return CheckStatus.WARN


def _rule_check_type(rule: dict[str, Any]) -> str:
    return str(rule.get("checkType") or rule.get("check_type") or "")


def _execution(rule: dict[str, Any]) -> dict[str, Any]:
    return dict(rule.get("execution") or execution_contract(_rule_check_type(rule)))


def _warning_result(
    rule: dict[str, Any],
    detail: str,
    missing_inputs: list[str] | None = None,
    evidence: list[dict[str, Any]] | None = None,
) -> CheckResult:
    execution = _execution(rule)
    return CheckResult(
        rule_id=str(rule.get("_evaluationId") or rule.get("id") or "") or None,
        permit_type=str(rule.get("permitType") or "") or None,
        permit_name=str(rule.get("permitName") or "") or None,
        rule=rule.get("rule", "Review check"),
        status=CheckStatus.WARN,
        citation=rule.get("source") or "Review rule",
        detail=detail,
        category=rule.get("category", "custom"),
        evaluator=execution.get("evaluator"),
        evidence=evidence or [],
        missing_inputs=missing_inputs or list(execution.get("requiredInputs", [])),
    )


def _document_content(
    documents: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    content: list[dict[str, Any]] = []
    omitted: list[str] = []
    total_bytes = 0
    for document in documents:
        path_value = document.get("storage_path")
        if not path_value:
            continue
        path = Path(str(path_value))
        if not path.is_file():
            omitted.append(f"{document.get('name') or path.name} (file unavailable)")
            continue
        size = path.stat().st_size
        if size <= 0:
            omitted.append(f"{document.get('name') or path.name} (empty file)")
            continue
        if len(content) >= MAX_ATTACHED_DOCUMENTS:
            omitted.append(f"{document.get('name') or path.name} (attachment count limit)")
            continue
        if size > 20 * 1024 * 1024 or total_bytes + size > MAX_TOTAL_ATTACHMENT_BYTES:
            omitted.append(f"{document.get('name') or path.name} (attachment size limit)")
            continue
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        encoded = base64.standard_b64encode(path.read_bytes()).decode("ascii")
        content.append(
            {
                "type": "file",
                "file": {
                    "filename": str(document.get("name") or path.name),
                    "file_data": f"data:{mime};base64,{encoded}",
                },
            }
        )
        total_bytes += size
    return content, omitted


def _parse_json_array(raw: str) -> list[dict[str, Any]]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.lstrip().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []


def _normalized_evidence(item: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = item.get("evidence")
    if not isinstance(evidence, list):
        return []
    output: list[dict[str, Any]] = []
    for entry in evidence:
        if not isinstance(entry, dict):
            continue
        document = str(entry.get("document") or entry.get("source") or "").strip()
        detail = str(entry.get("detail") or entry.get("quote") or "").strip()
        source_type = str(
            entry.get("source_type") or entry.get("sourceType") or "project_document"
        ).strip()
        if document and detail:
            output.append(
                {
                    "document": document,
                    "page": entry.get("page"),
                    "detail": detail,
                    "sourceType": source_type,
                }
            )
    return output


def _official_standard_evidence(
    rule: dict[str, Any], authoritative_context: dict[str, Any]
) -> list[dict[str, Any]]:
    links = rule.get("sourceLinks") or []
    if not links:
        return []
    link = links[0]
    execution = _execution(rule)
    if execution.get("requiresContextStandard"):
        profile = authoritative_context.get("zoningProfile")
        if not isinstance(profile, dict) or not profile:
            return []
        controlling = profile.get("controllingRecord")
        if rule.get("requiresResolvedStandardValues"):
            has_detected_standard = bool(
                profile.get("standards")
                or (isinstance(controlling, dict) and controlling.get("standards"))
            )
        else:
            has_detected_standard = bool(
                profile.get("classification")
                or profile.get("district")
                or profile.get("standards")
                or (isinstance(controlling, dict) and controlling.get("standards"))
            )
        if not has_detected_standard:
            return []
        return [
            {
                "document": "Detected zoning profile and controlling approval record",
                "page": None,
                "detail": json.dumps(profile, default=str)[:12000],
                "sourceType": "authoritative_standard",
                "url": link.get("url"),
                "provider": "estatepermit_authoritative_context",
                "verifiedAt": rule.get("verifiedAt"),
            }
        ]
    return [
        {
            "document": str(link.get("title") or rule.get("source") or "Official rule source"),
            "page": None,
            "detail": str(rule.get("condition") or rule.get("rule") or "Governing requirement"),
            "sourceType": "authoritative_standard",
            "url": link.get("url"),
            "provider": "estatepermit_verified_catalog",
            "verifiedAt": rule.get("verifiedAt"),
        }
    ]


def _external_evidence(
    rule: dict[str, Any], authoritative_context: dict[str, Any]
) -> list[dict[str, Any]]:
    records = authoritative_context.get("externalRecords") or {}
    output: list[dict[str, Any]] = []
    for entry in records.get("evidence", []):
        if not isinstance(entry, dict):
            continue
        if entry.get("sourceType") not in {"authoritative_registry", "dated_status_record"}:
            continue
        output.append(dict(entry))
    return output


def _trusted_model_evidence(
    item: dict[str, Any],
    documents: list[dict[str, Any]],
    official_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    documents_by_name = {
        str(document.get("name") or "").strip().casefold(): document
        for document in documents
        if str(document.get("name") or "").strip()
    }
    official_by_identity = {
        (
            str(entry.get("sourceType") or ""),
            str(entry.get("document") or "").strip().casefold(),
        ): entry
        for entry in official_evidence
        if str(entry.get("document") or "").strip()
    }
    output: list[dict[str, Any]] = []
    for entry in _normalized_evidence(item):
        source_type = entry["sourceType"]
        name = entry["document"].strip()
        official = official_by_identity.get((source_type, name.casefold()))
        if official is not None:
            output.append(dict(official))
            continue
        document = documents_by_name.get(name.casefold())
        if source_type == "project_record" and name.casefold() == "project record":
            output.append({**entry, "provider": "estatepermit_project_record"})
            continue
        if document is None:
            continue

        document_type = str(document.get("document_type") or "")
        uploaded = {
            **entry,
            "sourceType": "project_document",
            "documentType": document_type,
            "permitTypes": list(document.get("permit_types") or []),
            "provider": "uploaded_project_document",
        }
        output.append(uploaded)

        if source_type == "authoritative_standard" and document_type == "agency_approval":
            output.append(
                {
                    **uploaded,
                    "sourceType": "authoritative_standard",
                    "provider": "uploaded_official_approval_record",
                }
            )

        if source_type == "authoritative_registry" and document_type == "license_record":
            output.append(
                {
                    **uploaded,
                    "sourceType": "authoritative_registry",
                    "provider": "uploaded_official_license_record",
                }
            )
        if source_type == "dated_status_record" and document_type in {
            "permit_record",
            "inspection_record",
            "agency_approval",
        }:
            output.append({**uploaded, "sourceType": "dated_status_record"})
    return output


def _dedupe_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for entry in evidence:
        key = (
            str(entry.get("sourceType") or ""),
            str(entry.get("document") or "").casefold(),
            str(entry.get("detail") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(entry)
    return output


def _missing_evidence_requirements(
    execution: dict[str, Any], evidence: list[dict[str, Any]]
) -> list[str]:
    missing: list[str] = []
    for requirement in execution.get("evidenceRequirements", []):
        allowed = {str(value) for value in requirement.get("anyOf", [])}
        matching = [entry for entry in evidence if entry.get("sourceType") in allowed]
        accepted_providers = {str(value) for value in requirement.get("providers", [])}
        if accepted_providers:
            matching = [
                entry for entry in matching if str(entry.get("provider") or "") in accepted_providers
            ]
        if requirement.get("distinctDocuments"):
            available = len(
                {
                    str(entry.get("document") or "").strip().casefold()
                    for entry in matching
                    if str(entry.get("document") or "").strip()
                }
            )
        else:
            available = len(matching)
        minimum = int(requirement.get("minimum") or 1)
        if available < minimum:
            label = " or ".join(value.replace("_", " ") for value in sorted(allowed))
            missing.append(f"{label} ({minimum} required, {available} available)")
    return missing


def _missing_required_permit_statuses(
    rule: dict[str, Any],
    execution: dict[str, Any],
    evidence: list[dict[str, Any]],
    authoritative_context: dict[str, Any],
) -> list[str]:
    if not execution.get("requiresAllRequiredPermitStatuses"):
        return []
    current_permit = str(rule.get("permitType") or "")
    required_permits = {
        str(permit.get("permitType"))
        for permit in authoritative_context.get("projectPermits", [])
        if permit.get("requirementStatus") == "required"
        and str(permit.get("permitType") or "") != current_permit
    }
    evidenced_permits: set[str] = set()
    for entry in evidence:
        if entry.get("sourceType") != "dated_status_record":
            continue
        if entry.get("permitType"):
            evidenced_permits.add(str(entry["permitType"]))
        evidenced_permits.update(str(value) for value in entry.get("permitTypes", []))
    return [
        f"dated final/status record for required permit: {permit_type}"
        for permit_type in sorted(required_permits - evidenced_permits)
    ]


def _validated_result(
    rule: dict[str, Any],
    item: dict[str, Any],
    documents: list[dict[str, Any]],
    authoritative_context: dict[str, Any],
    unreviewed_documents: list[str] | None = None,
) -> CheckResult:
    execution = _execution(rule)
    status = _status(str(item.get("status", "warn")))
    evidence = _dedupe_evidence(
        [
            *_official_standard_evidence(rule, authoritative_context),
            *_trusted_model_evidence(
                item,
                documents,
                _external_evidence(rule, authoritative_context),
            ),
        ]
    )
    missing_inputs = [str(value) for value in item.get("missing_inputs", []) if str(value).strip()]

    if execution.get("evaluator") == "unsupported":
        return _warning_result(rule, "This rule has no configured evaluator and was not run.")

    needs_project_document = any(
        "project_document" in requirement.get("anyOf", [])
        for requirement in execution.get("evidenceRequirements", [])
    )
    if status in {CheckStatus.PASS, CheckStatus.FAIL} and needs_project_document and unreviewed_documents:
        return _warning_result(
            rule,
            "EstatePermit did not accept the conclusion because not every relevant project document was available to the evaluator.",
            list(unreviewed_documents),
            evidence,
        )

    if status in {CheckStatus.PASS, CheckStatus.FAIL}:
        missing_evidence = [
            *_missing_evidence_requirements(execution, evidence),
            *_missing_required_permit_statuses(
                rule,
                execution,
                evidence,
                authoritative_context,
            ),
        ]
        if missing_evidence:
            return _warning_result(
                rule,
                "EstatePermit rejected the conclusion because its required evidence was not verified.",
                missing_evidence,
                evidence,
            )

    if status == CheckStatus.PASS and missing_inputs:
        return _warning_result(
            rule,
            "Required inputs are still missing, so EstatePermit did not accept the pass result.",
            missing_inputs,
        )

    detail = str(item.get("detail") or "No review detail was returned.").strip()
    if status == CheckStatus.WARN and missing_inputs:
        detail = f"{detail} Missing: {', '.join(missing_inputs)}."
    return CheckResult(
        rule_id=str(rule.get("_evaluationId") or rule.get("id") or "") or None,
        permit_type=str(rule.get("permitType") or "") or None,
        permit_name=str(rule.get("permitName") or "") or None,
        rule=rule.get("rule") or str(item.get("rule") or "Review check"),
        status=status,
        citation=rule.get("source") or str(item.get("citation") or "Review rule"),
        detail=detail,
        category=rule.get("category", "custom"),
        evaluator=execution.get("evaluator"),
        evidence=evidence,
        missing_inputs=missing_inputs,
    )


async def _evaluate_batch(
    brief: ProjectBrief,
    rules: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    authoritative_context: dict[str, Any],
) -> list[CheckResult]:
    rules_payload = [
        {
            "id": rule.get("_evaluationId") or rule.get("id"),
            "name": rule.get("rule"),
            "requirement": rule.get("condition") or rule.get("rule"),
            "check_type": _rule_check_type(rule),
            "citation": rule.get("source"),
            "source_links": rule.get("sourceLinks", []),
            "permit_type": rule.get("permitType"),
            "execution": _execution(rule),
        }
        for rule in rules
    ]
    document_inventory = [
        {
            "name": document.get("name"),
            "document_type": document.get("document_type"),
            "label": document.get("label"),
            "summary": document.get("summary"),
            "permit_types": document.get("permit_types", []),
        }
        for document in documents
    ]
    instruction = (
        "Evaluate every listed permitting rule using only the supplied project record, authoritative city "
        "context, and attached project documents. Never use general knowledge to fill a missing project value "
        "or controlling standard. Return only a JSON array with exactly one object per rule. Each object must "
        "contain id, status (pass, fail, or warn), detail, missing_inputs, and evidence. Evidence is an array of "
        "objects with document, page, detail, and source_type. Allowed source_type values are project_document, "
        "project_record, authoritative_standard, authoritative_registry, and dated_status_record. Quote or "
        "precisely identify the supporting value and page. Never invent a document name, registry lookup, city record, "
        "URL, or source type. EstatePermit validates every cited identity against its server-side inventory. "
        "A pass or fail requires traceable evidence. A cross_document conclusion requires evidence from "
        "at least two project_document sources. A value_match conclusion requires one authoritative_standard "
        "source and one project_document source. A credential conclusion requires project_document and "
        "authoritative_registry sources. A sequencing conclusion requires the authoritative standard and at least "
        "one dated_status_record source. Official standards and external records are supplied by the server; cite "
        "their exact names when used. If a controlling UR plan, numeric standard, drawing value, credential, approval, "
        "inspection, or other required input is unavailable, return warn and identify that input. Do not treat a "
        "document filename as proof of its contents. Project-record facts may cite document='Project record' and "
        "source_type='project_record'.\n\n"
        f"Project record:\n{json.dumps(brief.model_dump(mode='json'), default=str)[:8000]}\n\n"
        f"Authoritative city context:\n{json.dumps(authoritative_context, default=str)[:30000]}\n\n"
        f"Document inventory:\n{json.dumps(document_inventory, default=str)[:12000]}\n\n"
        f"Rules:\n{json.dumps(rules_payload, default=str)}"
    )
    document_content, unreviewed_documents = _document_content(documents)
    if unreviewed_documents:
        instruction += (
            "\n\nFiles unavailable to this evaluation call:\n"
            + json.dumps(unreviewed_documents)
            + "\nReturn warn for every rule that could depend on any unavailable file."
        )
    content: list[dict[str, Any]] = [{"type": "text", "text": instruction}]
    content.extend(document_content)

    raw = await chat_completion(
        "permit_rule_evaluation",
        [{"role": "user", "content": content}],
        max_tokens=7000,
    )
    parsed = _parse_json_array(raw)
    parsed_by_id = {str(item.get("id")): item for item in parsed if item.get("id") is not None}
    return [
        _validated_result(
            rule,
            parsed_by_id[str(rule.get("_evaluationId") or rule.get("id"))],
            documents,
            authoritative_context,
            unreviewed_documents,
        )
        if str(rule.get("_evaluationId") or rule.get("id")) in parsed_by_id
        else _warning_result(rule, "The evaluator returned no result for this rule.")
        for rule in rules
    ]


async def evaluate_custom_rules(
    brief: ProjectBrief,
    rules: list[dict[str, Any]],
    document_context: list[dict[str, Any]] | None = None,
    target_permit_types: list[str] | None = None,
    authoritative_context: dict[str, Any] | None = None,
) -> list[CheckResult]:
    target_set = set(target_permit_types or [])
    selected = [
        dict(rule)
        for rule in rules
        if rule.get("enabled", True)
        and (not target_set or not rule.get("permitType") or rule.get("permitType") in target_set)
    ]
    used_ids: set[str] = set()
    enabled: list[dict[str, Any]] = []
    for index, rule in enumerate(selected):
        base_id = str(rule.get("id") or f"rule-{index + 1}")
        evaluation_id = base_id
        suffix = 2
        while evaluation_id in used_ids:
            evaluation_id = f"{base_id}#{suffix}"
            suffix += 1
        used_ids.add(evaluation_id)
        rule["_evaluationId"] = evaluation_id
        rule["_evaluationOrder"] = index
        enabled.append(rule)
    if not enabled:
        return []

    documents = [
        document
        for document in (document_context or [])
        if document.get("document_type") != "permit_checklist"
    ]
    authoritative_context = authoritative_context or {}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for rule in enabled:
        grouped.setdefault(str(rule.get("permitType") or "__shared__"), []).append(rule)
    batches = [
        group[start : start + RULE_BATCH_SIZE]
        for group in grouped.values()
        for start in range(0, len(group), RULE_BATCH_SIZE)
    ]
    semaphore = asyncio.Semaphore(RULE_BATCH_CONCURRENCY)

    async def evaluate_batch(batch: list[dict[str, Any]]) -> list[CheckResult]:
        batch_results: list[CheckResult] = []
        permit_types = {str(rule.get("permitType")) for rule in batch if rule.get("permitType")}
        batch_documents = documents
        if len(permit_types) == 1:
            batch_documents = relevant_documents(documents, next(iter(permit_types)))

        runnable: list[dict[str, Any]] = []
        for rule in batch:
            execution = _execution(rule)
            if execution.get("evaluator") == "unsupported":
                batch_results.append(_warning_result(rule, "This rule has no configured evaluator and was not run."))
                continue
            external = _external_evidence(rule, authoritative_context)
            can_run_without_document = _rule_check_type(rule) == "applicability" or (
                _rule_check_type(rule) == "sequencing"
                and any(item.get("sourceType") == "dated_status_record" for item in external)
            )
            if not batch_documents and not can_run_without_document:
                batch_results.append(_warning_result(rule, missing_evidence_detail(rule)))
                continue
            runnable.append(rule)

        if not runnable:
            return batch_results
        try:
            async with semaphore:
                batch_results.extend(
                    await _evaluate_batch(
                        brief,
                        runnable,
                        batch_documents,
                        authoritative_context,
                    )
                )
        except Exception as exc:
            logger.warning("Rule evaluation batch failed: %s", exc)
            batch_results.extend(
                _warning_result(
                    rule,
                    "This check could not be completed automatically. Try again or review it manually.",
                )
                for rule in runnable
            )
        return batch_results

    nested_results = await asyncio.gather(*(evaluate_batch(batch) for batch in batches))
    results = [result for batch_results in nested_results for result in batch_results]
    order = {str(rule["_evaluationId"]): int(rule["_evaluationOrder"]) for rule in enabled}
    returned_ids = {str(result.rule_id) for result in results}
    for rule in enabled:
        if str(rule["_evaluationId"]) not in returned_ids:
            results.append(_warning_result(rule, "No evaluation result was produced for this rule."))
    results.sort(key=lambda result: order.get(str(result.rule_id), len(enabled)))
    return results
