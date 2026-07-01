"""Lightweight SQLite schema upgrades for existing databases."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)


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
    if "projects" in inspect(conn).get_table_names():
        _add_column_if_missing(
            conn,
            "projects",
            "area",
            "ALTER TABLE projects ADD COLUMN area VARCHAR(100)",
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
