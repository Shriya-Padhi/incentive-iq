# IncentiveIQ

**RAG assistant for heat pump and home-energy incentives.** Pick a product, a customer location and an income tier; IncentiveIQ retrieves official program pages and answers with a cited source and fetch date for every claim. If the indexed pages don't cover a question, it says so instead of guessing.

![IncentiveIQ answering whether the federal heat pump tax credit is still available](docs/demo.png)

## Why

Federal heat pump and battery tax credits ended on December 31, 2025. The incentives that remain are a patchwork: income-qualified state rebates that can run out of funding, and utility rebates with their own equipment and paperwork rules. An LLM's training data still says "claim up to $2,000 from the IRS", which is now wrong. Dealers and buyers need answers grounded in current official pages, with dates.

## How it works

```
OFFLINE (python ingest.py)
sources.csv ─► fetch page ─► extract main text ─► chunk (1,200 chars, 200 overlap)
                                                      │
                                                      ▼
                                      Chroma vector DB (embeddings + metadata:
                                      program, region, url, fetched_at)

AT QUESTION TIME
question + product + location + income tier
      │
      ▼
retrieve top-6 chunks, filtered to city + state + nationwide programs
      │  drop weak matches (similarity < 0.35); nothing left → "not found", no LLM call
      ▼
prompt = today's date + equipment specs + numbered, dated sources
      │
      ▼
LLM (Qwen 2.5 7B via Ollama) answers only from sources, cites [n]
      │
      ▼
citations mapped back to URLs ─► Chainlit UI (answer + sources + retrieval trace)
```

![Retrieved passages with similarity scores](docs/retrieval.png)

## Features

- **Grounded answers with citations.** Every `[n]` maps to an official URL and the date it was fetched.
- **Location-scoped retrieval.** A Sacramento customer only sees Sacramento, California and nationwide programs, never another state's.
- **Date-aware.** Today's date is in every prompt, so programs whose end date has passed are reported as ended.
- **Refuses when unsure.** If nothing relevant is retrieved, it says so without calling the LLM.
- **Equipment check.** Specs from a sample product catalog are compared against program requirements.
- **Retrieval transparency.** The UI shows the passages the model read and their similarity scores.

![Settings: product, location and income tier](docs/settingspanel.png)

## Data

| File | Contents |
|---|---|
| `data/sources.csv` | Official program pages: SMUD, TECH Clean California, Mass Save, Minnesota Commerce, DOE and IRS |
| `data/catalog.csv` | **Fictional sample equipment** from "An Electrification Company" (heat pumps, a water heater, a battery), with specs programs check: compressor type, cold-climate rating, SEER2/HSPF2, certificate number, connected controls |

## Run it

```bash
git clone https://github.com/Shriya-Padhi/incentive-iq.git
cd incentive-iq
python -m venv .venv
source .venv/bin/activate          # Windows Git Bash: source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env               # choose Ollama or GitHub Models
ollama pull qwen2.5:7b             # skip if using GitHub Models
python ingest.py                   # builds the local vector database (chroma_db/)
chainlit run app.py -w             # http://localhost:8000
```

## Tests

```bash
python -m pytest -v
```

Tests run offline in under a second: an in-memory Chroma collection with a hash-based test embedding replaces the real model, and a fake LLM client replaces Ollama.

- **Ingestion:** chunk size limits, overlap, blocked pages are skipped rather than fatal
- **Retrieval:** the region filter never returns another state's programs; every hit carries citation metadata
- **Generation:** citation parsing (`[1]`, `[1][3]`, `[1, 3]`), invalid citations dropped, catalog specs and today's date in the prompt, irrelevant questions refused without an LLM call

## Project structure

| File | Purpose |
|---|---|
| `ingest.py` | Fetch, extract, chunk and index program pages |
| `retriever.py` | Region-scoped semantic search |
| `rag.py` | Prompt assembly, grounded generation, citation mapping |
| `app.py` | Chainlit UI with settings, sources and retrieval trace |
| `tests/` | Offline tests with a fake embedding and a fake LLM |

## What I learned building it

- **The LLM has no clock.** Before today's date was added to the prompt, the model called a credit that ended on December 31, 2025 "still available".
- **Retrieval quality decides answer quality.** The IRS FAQ page is mostly about vehicle credits, so heat pump questions retrieved the wrong passages until a 25C-specific page was added.
- **Parse model output defensively.** The model cited `[1, 3]` instead of `[1][3]`, which silently broke the sources list until the parser handled both.

## Limits

- **An ended program can still appear as available** when the retrieved passage omits its end date. Example: asked "which incentives can this product get?", the model listed the 25C credit because the retrieved 25C chunk described how to claim it but not when it ended.
- **Partial citations.** Qwen 2.5 7B cites amounts reliably but sometimes leaves eligibility and paperwork bullets uncited.
- **Snapshot data.** Answers are only as current as the last `python ingest.py` run; the fetch date is shown so users can judge freshness.
- **Seven sources, three states.** This is a prototype; real coverage needs many more programs.
- **Not financial or tax advice.** Confirm details on the official program page.

## Next steps

- **Curated program-status layer:** a small verified table (ended, waitlisted) attached to every chunk from that program, overriding the page text. This fixes the 25C issue above.
- Flag uncited sentences automatically and ask the model to retry
- Scheduled re-ingestion with change detection, so program updates are caught
- Hybrid keyword + vector search for program names and codes

## License

MIT
