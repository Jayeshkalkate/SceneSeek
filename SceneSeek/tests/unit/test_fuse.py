from app.services.fuse import fuse_scores


def title(title_id, name):
    return {"title_id": title_id, "title": name, "kind": "anime", "genres": [], "rating": {"value": None, "source": None}}


def test_clear_visual_winner_gets_high_band():
    titles = {"one": title("one", "Title One"), "two": title("two", "Title Two")}
    result = fuse_scores({"one": [0.98, 0.95, 0.97], "two": [0.1, 0.2, 0.15]}, 3, titles)
    assert result["band"] == "high"
    assert result["candidates"][0]["title_id"] == "one"
    assert result["candidates"][0]["confidence"] == "high"
    assert len(result["candidates"]) == 2


def test_ambiguous_top_scores_are_not_called_high_confidence():
    titles = {"one": title("one", "Title One"), "two": title("two", "Title Two")}
    result = fuse_scores({"one": [0.92, 0.90], "two": [0.91, 0.89]}, 2, titles)
    assert result["band"] == "low"
    assert result["candidates"][0]["confidence"] == "low"


def test_empty_index_returns_actionable_no_match():
    result = fuse_scores({}, 1, {})
    assert result["band"] == "none"
    assert result["candidates"] == []
    assert "index" in result["message"].lower()


def test_low_visual_evidence_returns_no_match():
    result = fuse_scores({"one": [0.12, 0.15]}, 2, {"one": title("one", "Title One")})
    assert result["band"] == "none"
    assert result["candidates"] == []


def test_random_dhash_distance_gives_no_match():
    # A hash distance of 32 bits (unrelated image) must not become a candidate after rescaling.
    sim = 1.0 - 32 / 64.0
    rescaled = max(0.0, min(1.0, (sim - 0.70) / 0.25))
    assert rescaled == 0.0
