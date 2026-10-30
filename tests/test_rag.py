from types import SimpleNamespace as NS
import rag


class FakeClient:
    """Mimics client.chat.completions.create() and records what it was sent."""

    def __init__(self, reply):
        self.reply = reply
        self.sent = None
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kwargs):
        self.sent = kwargs
        return NS(choices=[NS(message=NS(content=self.reply))])


HITS = [{"url": "a", "program": "A"}, {"url": "b", "program": "B"}, {"url": "a", "program": "A again"}]


def test_citation_formats_and_bad_numbers():
    cited = rag.cited_sources("Up to $3,000 [1, 3]. Waitlisted [2][9]. Bogus [12].", HITS)
    assert [(s["n"], s["program"]) for s in cited] == [(1, "A"), (2, "B")]


def test_answer_grounds_prompt_in_sources_and_equipment(collection):
    client = FakeClient("SMUD pays up to $3,000 [1].")
    out = rag.answer("Does EC-HP36-CC get a SMUD heat pump rebate?", client, "fake",
                     region="Sacramento, CA", collection=collection)
    prompt = client.sent["messages"][1]["content"]
    assert "[1]" in prompt and "fetched" in prompt                  # numbered, dated sources
    assert "EC-HP36-CC" in prompt and "variable-speed" in prompt    # catalog specs injected
    assert out["sources"] and out["sources"][0]["n"] == 1


def test_irrelevant_question_refused_without_calling_llm(collection, monkeypatch):
    monkeypatch.setattr(rag, "MIN_SCORE", 0.99)
    client = FakeClient("should not be called")
    out = rag.answer("best pizza in town", client, "fake", region="Sacramento, CA", collection=collection)
    assert out["answer"] == rag.NOT_FOUND
    assert client.sent is None


def test_prompt_includes_todays_date(collection):
    import datetime as dt
    client = FakeClient("ok [1]")
    rag.answer("Is the federal heat pump tax credit available?", client, "fake",
               region="Sacramento, CA", collection=collection)
    assert dt.date.today().isoformat() in client.sent["messages"][1]["content"]