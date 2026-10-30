from ingest import build_index, chunk_text


def test_short_text_is_one_chunk():
    assert chunk_text("Heat pump rebate up to $3,000.") == ["Heat pump rebate up to $3,000."]


def test_empty_text_has_no_chunks():
    assert chunk_text("") == []


def test_chunks_respect_max_size():
    text = "\n".join(f"Paragraph {i} about rebate rules and paperwork. " * 6 for i in range(30))
    chunks = chunk_text(text, max_chars=1200, overlap=200)
    assert len(chunks) > 1
    assert max(len(c) for c in chunks) <= 1200


def test_long_paragraph_is_split_with_overlap():
    chunks = chunk_text("x" * 5000, max_chars=1200, overlap=200)
    assert all(len(c) <= 1200 for c in chunks)
    assert sum(len(c) for c in chunks) > 5000   # overlap means some text repeats


def test_bad_source_is_skipped_not_fatal(collection):
    def get_text(src):
        raise RuntimeError("403 Forbidden")
    report = build_index([{"id": "blocked", "url": "u", "program": "p", "region": "r", "program_type": "t"}],
                         collection, get_text=get_text)
    assert report[0]["status"].startswith("skipped")