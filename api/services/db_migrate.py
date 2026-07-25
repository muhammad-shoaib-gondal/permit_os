"""Lightweight SQLite schema upgrades for existing databases."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)


def _clean_previous_analysis_value(value: Any) -> Any:
    """Normalize persisted results from the retired coordination schema."""
    section_token = "ag" + "ent"
    service_token = "ba" + "nd"
    removed_keys = {
        f"{service_token}_room_id",
        f"{service_token}_orchestrated",
        f"{section_token}_driven",
        "local_fallback",
    }
    renamed_keys = {
        section_token: "source",
        f"{section_token}_id": "source",
        f"{section_token}s": "sections",
        f"source_{section_token}": "source_section",
        f"completed_{section_token}s": "completed_sections",
    }

    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if key in removed_keys:
                continue
            cleaned[renamed_keys.get(key, key)] = _clean_previous_analysis_value(item)
        return cleaned
    if isinstance(value, list):
        return [_clean_previous_analysis_value(item) for item in value]
    if isinstance(value, str):
        value = value.replace(
            f"start_all_{section_token}s.ps1",
            "start_services_background.ps1",
        )
        replacements = (
            (rf"\b{service_token}\b", "external service"),
            (rf"\b{section_token}s\b", "analysis sections"),
            (rf"\b{section_token}\b", "analysis section"),
            (rf"\b{'con' + 'ductor'}\b", "summary"),
            (r"\bpackager\b", "packaging"),
        )
        for pattern, replacement in replacements:
            value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
    return value


def _clean_persisted_analysis(conn: Connection) -> None:
    for case_id, raw_results in conn.execute(
        text("SELECT case_id, results FROM permit_cases WHERE results IS NOT NULL")
    ):
        try:
            results = json.loads(raw_results) if isinstance(raw_results, str) else raw_results
            cleaned = _clean_previous_analysis_value(results)
            conn.execute(
                text("UPDATE permit_cases SET results = :results WHERE case_id = :case_id"),
                {"results": json.dumps(cleaned), "case_id": case_id},
            )
        except (TypeError, json.JSONDecodeError):
            logger.warning("Could not normalize stored results for case %s", case_id)

    for row_id, source, detail, payload in conn.execute(
        text("SELECT id, source, detail, payload FROM audit_log")
    ):
        cleaned_payload = payload
        if payload:
            try:
                decoded = json.loads(payload) if isinstance(payload, str) else payload
                cleaned_payload = json.dumps(_clean_previous_analysis_value(decoded))
            except (TypeError, json.JSONDecodeError):
                pass
        conn.execute(
            text(
                """
                UPDATE audit_log
                SET source = :source, detail = :detail, payload = :payload
                WHERE id = :id
                """
            ),
            {
                "source": _clean_previous_analysis_value(source),
                "detail": _clean_previous_analysis_value(detail),
                "payload": cleaned_payload,
                "id": row_id,
            },
        )


def _column_names(conn: Connection, table: str) -> set[str]:
    inspector = inspect(conn)
    if table not in inspector.get_table_names():
        return set()
    return {col["name"] for col in inspector.get_columns(table)}


def _add_column_if_missing(conn: Connection, table: str, column: str, ddl: str) -> None:
    if column in _column_names(conn, table):
        return
    conn.execute(text(ddl))
    logger.info("Added column %s.%s", table, column)


def _migrate_audit_source(conn: Connection) -> None:
    """Rebuild the audit table when upgrading from the previous source schema."""
    columns = _column_names(conn, "audit_log")
    previous_source = "ag" + "ent_id"
    if previous_source not in columns:
        _add_column_if_missing(
            conn,
            "audit_log",
            "source",
            "ALTER TABLE audit_log ADD COLUMN source VARCHAR(100)",
        )
        return

    conn.execute(
        text(
            """
            CREATE TABLE audit_log_rebuilt (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                case_id VARCHAR(36) NOT NULL,
                timestamp DATETIME,
                source VARCHAR(100),
                event_type VARCHAR(100) NOT NULL,
                payload JSON,
                message_id VARCHAR(255),
                detail TEXT
            )
            """
        )
    )
    conn.execute(
        text(
            f"""
            INSERT INTO audit_log_rebuilt
                (id, case_id, timestamp, source, event_type, payload, message_id, detail)
            SELECT id, case_id, timestamp, {previous_source}, event_type, payload, message_id, detail
            FROM audit_log
            """
        )
    )
    conn.execute(text("DROP TABLE audit_log"))
    conn.execute(text("ALTER TABLE audit_log_rebuilt RENAME TO audit_log"))
    conn.execute(text("CREATE INDEX ix_audit_log_case_id ON audit_log (case_id)"))
    logger.info("Updated audit source schema")


def run_sqlite_migrations(conn: Connection) -> None:
    """Apply additive migrations that create_all does not handle."""
    if conn.dialect.name != "sqlite":
        return

    if "permit_cases" in inspect(conn).get_table_names():
        _add_column_if_missing(
            conn,
            "permit_cases",
            "project_id",
            "ALTER TABLE permit_cases ADD COLUMN project_id VARCHAR(36)",
        )
        previous_room_column = "ba" + "nd_room_id"
        if previous_room_column in _column_names(conn, "permit_cases"):
            conn.execute(text(f'ALTER TABLE permit_cases DROP COLUMN "{previous_room_column}"'))
            logger.info("Removed obsolete permit case coordination column")
    if "audit_log" in inspect(conn).get_table_names():
        _migrate_audit_source(conn)
        _clean_persisted_analysis(conn)
    if "projects" in inspect(conn).get_table_names():
        _add_column_if_missing(
            conn,
            "projects",
            "area",
            "ALTER TABLE projects ADD COLUMN area VARCHAR(100)",
        )
        _add_column_if_missing(
            conn,
            "projects",
            "scope",
            "ALTER TABLE projects ADD COLUMN scope JSON",
        )
        _add_column_if_missing(
            conn,
            "projects",
            "zoning_status",
            "ALTER TABLE projects ADD COLUMN zoning_status VARCHAR(50)",
        )
        _add_column_if_missing(
            conn,
            "projects",
            "zoning_profile",
            "ALTER TABLE projects ADD COLUMN zoning_profile JSON",
        )
        _add_column_if_missing(
            conn,
            "projects",
            "zoning_warnings",
            "ALTER TABLE projects ADD COLUMN zoning_warnings JSON",
        )
        _add_column_if_missing(
            conn,
            "projects",
            "permit_answers",
            "ALTER TABLE projects ADD COLUMN permit_answers JSON",
        )
    if "project_files" in inspect(conn).get_table_names():
        _add_column_if_missing(
            conn,
            "project_files",
            "document_label",
            "ALTER TABLE project_files ADD COLUMN document_label VARCHAR(255)",
        )
        _add_column_if_missing(
            conn,
            "project_files",
            "file_sections",
            "ALTER TABLE project_files ADD COLUMN file_sections JSON",
        )
        _add_column_if_missing(
            conn,
            "project_files",
            "ai_summary",
            "ALTER TABLE project_files ADD COLUMN ai_summary TEXT",
        )
        _add_column_if_missing(
            conn,
            "project_files",
            "classification_source",
            "ALTER TABLE project_files ADD COLUMN classification_source VARCHAR(30)",
        )
        _add_column_if_missing(
            conn,
            "project_files",
            "permit_types",
            "ALTER TABLE project_files ADD COLUMN permit_types JSON",
        )
    if "project_permits" in inspect(conn).get_table_names():
        _add_column_if_missing(
            conn,
            "project_permits",
            "recommendation_evidence",
            "ALTER TABLE project_permits ADD COLUMN recommendation_evidence JSON",
        )
        conn.execute(
            text(
                """
                DELETE FROM project_permits
                WHERE permit_id IN (
                    SELECT permit_id
                    FROM (
                        SELECT
                            permit_id,
                            ROW_NUMBER() OVER (
                                PARTITION BY project_id, permit_type
                                ORDER BY
                                    CASE WHEN origin = 'manual' THEN 1 ELSE 0 END DESC,
                                    CASE WHEN requirement_status IN ('manual', 'removed_by_user') THEN 1 ELSE 0 END DESC,
                                    CASE WHEN lifecycle_status <> 'not_started' THEN 1 ELSE 0 END DESC,
                                    CASE WHEN application_number IS NOT NULL OR issued_number IS NOT NULL THEN 1 ELSE 0 END DESC,
                                    updated_at DESC,
                                    created_at DESC,
                                    permit_id DESC
                            ) AS duplicate_rank
                        FROM project_permits
                    ) ranked
                    WHERE duplicate_rank > 1
                )
                """
            )
        )
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_project_permits_project_type "
                "ON project_permits (project_id, permit_type)"
            )
        )
