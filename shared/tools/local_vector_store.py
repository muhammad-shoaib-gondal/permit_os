from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.tools.knowledge import resolve_knowledge_root

TOKEN_RE = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)?")
VECTOR_DIMENSIONS = 384
INDEX_VERSION = 1


@dataclass(frozen=True)
class SearchResult:
    record_id: str
    score: float
    source_file: str
    record_type: str
    title: str
    text: str
    metadata: dict[str, Any]


class LocalKnowledgeVectorStore:
    """Small, dependency-free SQLite vector store for jurisdiction knowledge packs.

    Embeddings use deterministic feature hashing. This keeps indexing local and reproducible;
    search results are supporting evidence and never decide permit applicability.
    """

    def __init__(self, path: Path):
        self.path = Path(path)

    def rebuild(self, knowledge_root: Path) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.executescript(
                """
                DROP TABLE IF EXISTS records;
                DROP TABLE IF EXISTS index_meta;
                CREATE TABLE records (
                    record_id TEXT PRIMARY KEY,
                    source_file TEXT NOT NULL,
                    record_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    text TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    vector BLOB NOT NULL
                );
                CREATE TABLE index_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE INDEX records_source_file_idx ON records(source_file);
                CREATE INDEX records_type_idx ON records(record_type);
                """
            )
            records = _knowledge_records(knowledge_root)
            for record in records:
                connection.execute(
                    "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        record["record_id"],
                        record["source_file"],
                        record["record_type"],
                        record["title"],
                        record["text"],
                        json.dumps(record["metadata"], ensure_ascii=False, sort_keys=True),
                        _pack_vector(_embed(record["text"])),
                    ),
                )
            meta = {
                "index_version": str(INDEX_VERSION),
                "dimensions": str(VECTOR_DIMENSIONS),
                "embedding": "deterministic-feature-hashing",
                "record_count": str(len(records)),
                "authority_policy": "retrieval-only",
            }
            connection.executemany("INSERT INTO index_meta VALUES (?, ?)", meta.items())
            connection.commit()
        return len(records)

    def search(self, query: str, *, limit: int = 8) -> list[SearchResult]:
        query_vector = _embed(query)
        if not self.path.is_file():
            raise FileNotFoundError(f"Vector index not found: {self.path}")
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                "SELECT record_id, source_file, record_type, title, text, metadata_json, vector FROM records"
            ).fetchall()
        ranked = sorted(
            (
                SearchResult(
                    record_id=row[0],
                    source_file=row[1],
                    record_type=row[2],
                    title=row[3],
                    text=row[4],
                    metadata=json.loads(row[5]),
                    score=_dot(query_vector, _unpack_vector(row[6])),
                )
                for row in rows
            ),
            key=lambda result: result.score,
            reverse=True,
        )
        return ranked[: max(1, limit)]

    def metadata(self) -> dict[str, str]:
        with sqlite3.connect(self.path) as connection:
            return dict(connection.execute("SELECT key, value FROM index_meta").fetchall())


def default_kcmo_index_path() -> Path:
    return resolve_knowledge_root("kansas_city_mo") / ".index" / "kcmo.sqlite3"


def build_kcmo_vector_index(output_path: Path | None = None) -> int:
    root = resolve_knowledge_root("kansas_city_mo")
    return LocalKnowledgeVectorStore(output_path or default_kcmo_index_path()).rebuild(root)


def default_kck_index_path() -> Path:
    return resolve_knowledge_root("kansas_city_ks") / ".index" / "kck.sqlite3"


def build_kck_vector_index(output_path: Path | None = None) -> int:
    root = resolve_knowledge_root("kansas_city_ks")
    return LocalKnowledgeVectorStore(output_path or default_kck_index_path()).rebuild(root)


def _knowledge_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        records.extend(_records_from_payload(path.name, payload))
    for path in sorted((root / "sources").glob("*.txt")):
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        for index, chunk in enumerate(_text_chunks(text)):
            records.append(
                {
                    "record_id": f"sources/{path.name}:text:{index}",
                    "source_file": f"sources/{path.name}",
                    "record_type": "official_source_text",
                    "title": f"{path.stem} source text {index + 1}",
                    "text": chunk,
                    "metadata": {"source_id": path.stem, "chunk": index},
                }
            )
    return records


def _text_chunks(text: str, *, chunk_size: int = 4000, overlap: int = 400) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start + chunk_size // 2:
                end = boundary
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return [chunk for chunk in chunks if chunk]


def _records_from_payload(source_file: str, payload: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        scalar_context = {key: value for key, value in payload.items() if not isinstance(value, (dict, list))}
        for key, value in payload.items():
            if isinstance(value, list):
                for index, item in enumerate(value):
                    records.append(_make_record(source_file, key, index, item, scalar_context))
            elif isinstance(value, dict):
                for index, (child_key, item) in enumerate(value.items()):
                    records.append(
                        _make_record(
                            source_file,
                            key,
                            index,
                            {"key": child_key, "value": item},
                            scalar_context,
                        )
                    )
        if not records:
            records.append(_make_record(source_file, "document", 0, payload, {}))
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            records.append(_make_record(source_file, "items", index, item, {}))
    return records


def _make_record(
    source_file: str,
    record_type: str,
    index: int,
    item: Any,
    context: dict[str, Any],
) -> dict[str, Any]:
    data = item if isinstance(item, dict) else {"value": item}
    title = str(
        data.get("title")
        or data.get("name")
        or data.get("permit_name")
        or data.get("rule")
        or data.get("id")
        or f"{record_type} {index + 1}"
    )
    text = _flatten_text({**context, **data})
    stable_key = f"{source_file}:{record_type}:{data.get('id', data.get('key', index))}"
    return {
        "record_id": stable_key,
        "source_file": source_file,
        "record_type": record_type,
        "title": title,
        "text": text,
        "metadata": data,
    }


def _flatten_text(value: Any) -> str:
    parts: list[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                parts.append(str(key).replace("_", " "))
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif item is not None:
            parts.append(str(item))

    visit(value)
    return " | ".join(parts)


def _embed(text: str) -> list[float]:
    vector = [0.0] * VECTOR_DIMENSIONS
    tokens = TOKEN_RE.findall(text.casefold())
    features = tokens + [f"{tokens[i]}_{tokens[i + 1]}" for i in range(len(tokens) - 1)]
    for feature in features:
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        raw = int.from_bytes(digest, "little")
        index = raw % VECTOR_DIMENSIONS
        sign = 1.0 if raw & (1 << 63) else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _pack_vector(vector: list[float]) -> bytes:
    return struct.pack(f"<{VECTOR_DIMENSIONS}f", *vector)


def _unpack_vector(value: bytes) -> list[float]:
    return list(struct.unpack(f"<{VECTOR_DIMENSIONS}f", value))
