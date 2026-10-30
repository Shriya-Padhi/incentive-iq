"""Generation: answer only from retrieved program text, with numbered citations."""

from __future__ import annotations

import csv
import os
import re
from pathlib import Path

from retriever import search

CATALOG_FILE = Path(__file__).parent / "data" / "catalog.csv"
MIN_SCORE = 0.35   # below this, retrieved text is too weakly related to answer from
NOT_FOUND = ("I couldn't find that in the program pages I have indexed. "
             "Check the program's official page or your utility directly.")

SYSTEM_PROMPT = """You are IncentiveIQ, an assistant for home-energy incentives (heat pumps, water heaters, batteries).

Rules:
1. Answer ONLY from the numbered sources provided. Do not use outside knowledge about programs, amounts or dates.
2. Put a citation like [1] right after every fact, amount and requirement you take from a source.
   Cite each source in its own brackets, e.g. [1][3], never [1, 3].
3. If a source says a program is closed, waitlisted, expired or subject to funding, say so plainly.
4. When asked whether equipment qualifies, compare the equipment specs to the program requirements in the sources.
   If the sources don't state the requirement, say it isn't stated rather than guessing.
5. If the sources don't answer the question, say you couldn't find it in the indexed pages.
6. Keep it short: a direct answer first, then bullets for amounts, eligibility and required paperwork.
7. End with: "Program details change often; confirm on the official page before you buy."
"""


def load_catalog(path: Path = CATALOG_FILE) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def mentioned_equipment(question: str, catalog: list[dict]) -> list[dict]:
    q = question.upper()
    return [row for row in catalog if row["model"].upper() in q]


def build_prompt(question: str, hits: list[dict], equipment: list[dict],
                 region: str | None, income_tier: str | None) -> str:
    """Assemble the user message: household context, equipment specs and numbered sources."""
    lines = [f"Question: {question}"]
    if region:
        lines.append(f"Household location: {region}")
    if income_tier:
        lines.append(f"Household income tier: {income_tier}")
    if equipment:
        lines.append("\nEquipment specs (fictional sample catalog):")
        for e in equipment:
            specs = ", ".join(f"{k}={v}" for k, v in e.items() if v and k != "notes")
            lines.append(f"- {specs}")
    lines.append("\nSources:")
    for i, h in enumerate(hits, 1):
        lines.append(f"[{i}] {h['program']} ({h['region']}), fetched {h['fetched_at']}\n{h['text']}\n")
    return "\n".join(lines)


def cited_sources(answer: str, hits: list[dict]) -> list[dict]:
    """Sources the answer actually cites, in order, deduplicated by URL. Accepts [1], [1][3] and [1, 3]. Numbers that don't match a source are ignored.."""
    seen, out = set(), []
    numbers = [int(n) for group in re.findall(r"\[([\d,\s]+)\]", answer)
               for n in re.findall(r"\d+", group)]
    for i in numbers:
        if 1 <= i <= len(hits) and hits[i - 1]["url"] not in seen:
            seen.add(hits[i - 1]["url"])
            out.append({**hits[i - 1], "n": i})
    return out


def answer(question: str, client, model: str, region: str | None = None,
           income_tier: str | None = None, k: int = 6, collection=None) -> dict:
    """Retrieve, then generate. Returns {"answer", "sources", "hits"}."""
    hits = search(question, region=region, k=k, collection=collection)
    hits = [h for h in hits if h["score"] >= MIN_SCORE]
    if not hits:   # refuse before calling the LLM: nothing relevant to ground an answer
        return {"answer": NOT_FOUND, "sources": [], "hits": []}
    equipment = mentioned_equipment(question, load_catalog())
    resp = client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": build_prompt(question, hits, equipment, region, income_tier)}],
    )
    text = resp.choices[0].message.content or ""
    return {"answer": text, "sources": cited_sources(text, hits), "hits": hits}


def make_client():
    from openai import OpenAI
    return OpenAI(base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
                  api_key=os.getenv("LLM_API_KEY", "ollama"))


def model_name() -> str:
    return os.getenv("LLM_MODEL", "qwen2.5:7b")