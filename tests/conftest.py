"""Shared test fixtures: an in-memory Chroma collection with a tiny offline embedding.

Tests never download a model or touch the network, so they run anywhere, including CI.
"""

import hashlib
import sys
from pathlib import Path

import chromadb
import pytest
from chromadb import Documents, EmbeddingFunction, Embeddings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest import build_index, get_collection  # noqa: E402


class HashEmbedding(EmbeddingFunction):
    """Bag-of-words hashed into 64 dims: crude, but deterministic and offline."""

    def __init__(self):
        pass

    def __call__(self, input: Documents) -> Embeddings:
        vectors = []
        for doc in input:
            v = [0.0] * 64
            for word in doc.lower().split():
                v[int(hashlib.md5(word.encode()).hexdigest(), 16) % 64] += 1.0
            vectors.append(v)
        return vectors

    @staticmethod
    def name() -> str:
        return "hash-test"


PAGES = {
    "smud": ("Sacramento, CA", "SMUD pays a heat pump rebate of up to 3000 dollars for variable-stage systems. " * 10),
    "ca-heehra": ("California", "HEEHRA heat pump rebates are fully reserved and new requests go on a waitlist. " * 10),
    "irs": ("United States", "The 25C credit is not available for property placed in service after December 31 2025. " * 10),
    "masssave": ("Massachusetts", "Mass Save enhanced heat pump rebates for moderate income households. " * 10),
}


@pytest.fixture
def collection():
    col = get_collection(client=chromadb.EphemeralClient(), embedding_function=HashEmbedding(), reset=True)
    sources = [{"id": k, "url": f"https://example.org/{k}", "program": k, "region": r, "program_type": "test"}
               for k, (r, _) in PAGES.items()]
    build_index(sources, col, get_text=lambda s: (PAGES[s["id"]][1], "test"))
    return col