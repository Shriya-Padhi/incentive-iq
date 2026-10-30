from retriever import applicable_regions, list_regions, search


def test_city_expands_to_state_and_nation():
    assert applicable_regions("Sacramento, CA") == ["Sacramento, CA", "California", "United States"]
    assert applicable_regions("United States") == ["United States"]


def test_search_never_returns_other_states(collection):
    hits = search("heat pump rebate", region="Sacramento, CA", k=10, collection=collection)
    regions = {h["region"] for h in hits}
    assert regions <= {"Sacramento, CA", "California", "United States"}
    assert "Massachusetts" not in regions


def test_hits_carry_citation_metadata(collection):
    hit = search("heat pump rebate", region="Massachusetts", k=1, collection=collection)[0]
    assert hit["url"].startswith("https://")
    assert hit["fetched_at"]
    assert -1 <= hit["score"] <= 1


def test_list_regions(collection):
    assert "Massachusetts" in list_regions(collection)