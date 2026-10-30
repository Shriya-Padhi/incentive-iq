"""Retrieval: find the chunks most relevant to a question, limited to programs that apply to a location."""

from __future__ import annotations

from ingest import get_collection

NATIONWIDE = "United States"
STATE_NAMES = {"CA": "California", "MA": "Massachusetts", "MN": "Minnesota"}


def applicable_regions(region: str) -> list[str]:
    """A city's programs also include its state's and nationwide ones.

    "Sacramento, CA" -> ["Sacramento, CA", "California", "United States"]
    """
    regions = [region]
    if "," in region:
        state = STATE_NAMES.get(region.rsplit(",", 1)[1].strip().upper())
        if state:
            regions.append(state)
    if NATIONWIDE not in regions:
        regions.append(NATIONWIDE)
    return regions


def search(query: str, region: str | None = None, k: int = 5, collection=None) -> list[dict]:
    """Return the top-k chunks for `query`, most similar first."""
    collection = collection or get_collection()
    where = {"region": {"$in": applicable_regions(region)}} if region else None
    res = collection.query(query_texts=[query], n_results=k, where=where)
    hits = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        hits.append({
            "text": doc,
            "program": meta["program"],
            "region": meta["region"],
            "url": meta["url"],
            "fetched_at": meta["fetched_at"],
            "score": round(1 - dist, 3),   # cosine similarity: 1.0 = same meaning
        })
    return hits


def list_regions(collection=None) -> list[str]:
    collection = collection or get_collection()
    metas = collection.get(include=["metadatas"])["metadatas"]
    return sorted({m["region"] for m in metas})