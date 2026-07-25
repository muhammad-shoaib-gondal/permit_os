#!/usr/bin/env python3
"""Ingest Manhattan KS Development Code sections into RAG chunks.

Fetches MDC articles from Zoneomics mirror (public text of enCodePlus MDC)
and writes knowledge/kansas/manhattan/code_chunks/chunks.json.

Usage:
  python scripts/ingest_manhattan_code.py
  python scripts/ingest_manhattan_code.py --chapters 2 7 9
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "knowledge" / "kansas" / "manhattan" / "code_chunks" / "chunks.json"
RAW_DIR = ROOT / "knowledge" / "kansas" / "manhattan" / "raw_chapters"
SOURCE_BASE = "https://www.zoneomics.com/code/manhattan-KS/chapter_{n}"
ENCODE_URL = "https://online.encodeplus.com/regs/manhattan-udo"

# Cached chapter exports (from official MDC text mirrors). Filenames: chapter_01.txt … chapter_10.txt

# Topic tags for search / RAG routing (match user & LLM query vocabulary)
TAG_KEYWORDS: dict[str, list[str]] = {
    "fence": ["fence", "fencing", "wall", "screen", "buffer", "bufferyard"],
    "setback": ["setback", "yard", "build-to", "buildable", "lot line", "encroachment"],
    "parking": ["parking", "stall", "garage", "driveway", "bicycle"],
    "sign": ["sign", "signage", "billboard", "banner"],
    "flood": ["flood", "floodplain", "FEMA", "BFE", "stormwater"],
    "zoning": ["zoning", "district", "rezon", "use permit", "conditional use"],
    "subdivision": ["subdivision", "plat", "lot split", "partition"],
    "height": ["height", "stories", "bulk", "coverage", "FAR"],
    "building": ["building permit", "building code", "IBC", "construction"],
    "variance": ["variance", "exception", "appeal", "BZA"],
    "historic": ["historic", "landmark", "preservation"],
    "design": ["design standard", "facade", "architecture", "landscape"],
    "access": ["access management", "driveway", "curb cut", "sidewalk"],
    "utility": ["utility", "easement", "substation", "telecommunication"],
    "environmental": ["environmental", "tree", "landscape surface"],
    "multifamily": ["multifamily", "MFR", "apartment", "dwelling unit", "DU"],
    "commercial": ["commercial", "retail", "industrial", "office"],
    "procedure": ["permit", "application", "hearing", "Type I", "Type II", "Type III"],
}

SECTION_RE = re.compile(
    r"^####\s+Sec\.\s+([\d]+-[\d]+[A-Z]?-[\d]+(?:\.[\d]+)?)[,.\s]+(.*)$",
    re.MULTILINE,
)
RULE_ID_RE = re.compile(r"^(\d+-\d+[A-Z]?-\d+)")


def fetch_chapter(n: int) -> str:
    url = SOURCE_BASE.format(n=n)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read().decode("utf-8", errors="replace")


def infer_tags(text: str) -> list[str]:
    lower = text.lower()
    tags: list[str] = []
    for tag, words in TAG_KEYWORDS.items():
        if any(w.lower() in lower for w in words):
            tags.append(tag)
    return tags or ["general"]


def normalize_text(text: str, max_len: int = 3500) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Drop markdown table noise rows that are just pipes
    cleaned: list[str] = []
    for ln in lines:
        if ln.startswith("|") and ln.count("|") > 4 and len(ln) < 120:
            continue
        if ln.startswith("![") or ln == "Loading...":
            continue
        cleaned.append(ln)
    out = " ".join(cleaned)
    out = re.sub(r"\s+", " ", out).strip()
    if len(out) > max_len:
        out = out[: max_len - 3] + "..."
    return out


def parse_sections(body: str, chapter: int) -> list[dict]:
    chunks: list[dict] = []
    matches = list(SECTION_RE.finditer(body))
    for i, m in enumerate(matches):
        sec_id = m.group(1).strip()
        title_suffix = (m.group(2) or "").strip().rstrip(".")
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        raw = body[start:end]
        text = normalize_text(raw)
        if len(text) < 80:
            continue
        article = sec_id.split("-")[0] if "-" in sec_id else "26"
        rule_id = f"MDC-{sec_id}"
        title = title_suffix or sec_id
        chunks.append(
            {
                "rule_id": rule_id,
                "article": f"26-{chapter}" if chapter else f"26-{article}",
                "section": sec_id,
                "title": title[:200],
                "text": text,
                "source_url": ENCODE_URL,
                "tags": infer_tags(f"{title} {text}"),
            }
        )
    return chunks


def dedupe_chunks(chunks: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for c in chunks:
        key = c["rule_id"]
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return sorted(out, key=lambda x: x["section"])


def load_local_chapters() -> list[tuple[int, str]]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    loaded: list[tuple[int, str]] = []
    for path in sorted(RAW_DIR.glob("chapter_*.txt")):
        try:
            ch = int(path.stem.split("_")[1])
        except (IndexError, ValueError):
            continue
        loaded.append((ch, path.read_text(encoding="utf-8", errors="replace")))
    return loaded


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--chapters",
        type=int,
        nargs="*",
        default=list(range(1, 11)),
        help="Chapter numbers to fetch if no local raw files (default 1-10)",
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="Only ingest from knowledge/.../raw_chapters/ (skip HTTP)",
    )
    args = parser.parse_args()

    all_chunks: list[dict] = []
    local = load_local_chapters()
    if local:
        for n, body in local:
            if args.chapters and n not in args.chapters:
                continue
            found = parse_sections(body, n)
            print(f"Local chapter {n}: {len(found)} sections", flush=True)
            all_chunks.extend(found)
    elif not args.local_only:
        for n in args.chapters:
            print(f"Fetching chapter {n}...", flush=True)
            try:
                body = fetch_chapter(n)
            except Exception as exc:
                print(f"  WARN: chapter {n} failed: {exc}", file=sys.stderr)
                continue
            found = parse_sections(body, n)
            print(f"  -> {len(found)} sections", flush=True)
            all_chunks.extend(found)
    else:
        print("No raw_chapters/*.txt found. Add chapter files or run without --local-only.", file=sys.stderr)
        return 1

    merged = dedupe_chunks(all_chunks)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "jurisdiction": "manhattan-ks",
        "ingested_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "source": "zoneomics.com/code/manhattan-KS (MDC Chapter 26 mirror)",
        "official_source": ENCODE_URL,
        "chunk_count": len(merged),
        "search_topics": list(TAG_KEYWORDS.keys()),
        "chunks": merged,
    }
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(merged)} chunks to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
