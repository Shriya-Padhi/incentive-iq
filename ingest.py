"""Ingestion pipeline: fetch official program pages -> clean text -> chunk -> store in Chroma.

Run:  python ingest.py
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import chromadb
import requests
import trafilatura

ROOT = Path(__file__).parent
SOURCES_FILE = ROOT / "data" / "sources.csv"
RAW_DIR = ROOT / "data" / "raw"          # optional manual saves: <id>.html or <id>.txt
DB_PATH = ROOT / "chroma_db"
COLLECTION = "incentives"
USER_AGENT = "Mozilla/5.0 (IncentiveIQ research prototype)"


def load_sources(path: Path = SOURCES_FILE) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fetch_html(url: str, timeout: int = 20) -> str:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def extract_text(html: str, url: str | None = None) -> str:
    """Keep the main content of a page; drop menus, footers and scripts."""
    text = trafilatura.extract(html, url=url, include_tables=True, favor_recall=True)
    return (text or "").strip()


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 200) -> list[str]:
    """Split on paragraph boundaries into chunks of at most ~max_chars.

    Consecutive chunks share `overlap` characters so a fact that straddles
    a boundary still appears whole in at least one chunk.
    """
    # 1. Paragraphs; any paragraph longer than max_chars becomes overlapping windows.
    pieces: list[str] = []
    step = max_chars - overlap
    for para in (p.strip() for p in text.split("\n")):
        if not para:
            continue
        if len(para) <= max_chars:
            pieces.append(para)
        else:
            pieces += [para[i:i + max_chars] for i in range(0, len(para) - overlap, step)]

    # 2. Pack pieces into chunks, carrying the last `overlap` characters forward.
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        candidate = f"{current}\n{piece}" if current else piece
        if len(candidate) <= max_chars:
            current = candidate
            continue
        chunks.append(current)
        tail = current[-overlap:]
        current = f"{tail}\n{piece}" if len(tail) + 1 + len(piece) <= max_chars else piece
    if current:
        chunks.append(current)
    return chunks


def get_page_text(source: dict) -> tuple[str, str]:
    """Return (text, origin). Tries a manual save in data/raw first, then the live URL."""
    for ext in (".txt", ".html"):
        saved = RAW_DIR / f"{source['id']}{ext}"
        if saved.exists():
            content = saved.read_text(encoding="utf-8", errors="ignore")
            text = content if ext == ".txt" else extract_text(content, source["url"])
            return text, f"manual save ({saved.name})"
    return extract_text(fetch_html(source["url"]), source["url"]), "live fetch"


def get_collection(client=None, embedding_function=None, reset: bool = False):
    client = client or chromadb.PersistentClient(path=str(DB_PATH))
    if reset:
        try:
            client.delete_collection(COLLECTION)
        except Exception:
            pass
    kwargs = {"name": COLLECTION, "metadata": {"hnsw:space": "cosine"}}
    if embedding_function is not None:
        kwargs["embedding_function"] = embedding_function
    return client.get_or_create_collection(**kwargs)


def build_index(sources: list[dict], collection, get_text=get_page_text) -> list[dict]:
    """Fetch, chunk and store every source. Returns a per-source report."""
    fetched_at = dt.date.today().isoformat()
    report = []
    for src in sources:
        try:
            text, origin = get_text(src)
            if len(text) < 200:
                raise ValueError("too little readable text (page may need JavaScript)")
            chunks = chunk_text(text)
            collection.add(
                ids=[f"{src['id']}-{i}" for i in range(len(chunks))],
                documents=chunks,
                metadatas=[{
                    "source_id": src["id"],
                    "program": src["program"],
                    "region": src["region"],
                    "program_type": src["program_type"],
                    "url": src["url"],
                    "fetched_at": fetched_at,
                    "chunk": i,
                } for i in range(len(chunks))],
            )
            report.append({"id": src["id"], "status": "ok", "chunks": len(chunks), "origin": origin})
        except Exception as exc:  # one bad page must not stop the run
            report.append({"id": src["id"], "status": f"skipped: {exc}", "chunks": 0, "origin": "-"})
    return report


def main() -> None:
    collection = get_collection(reset=True)
    report = build_index(load_sources(), collection)
    print(f"{'source':<20} {'chunks':>6}  status")
    for row in report:
        print(f"{row['id']:<20} {row['chunks']:>6}  {row['status']} [{row['origin']}]")
    print(f"\nTotal chunks stored: {collection.count()}  ->  {DB_PATH.name}/")


if __name__ == "__main__":
    main()