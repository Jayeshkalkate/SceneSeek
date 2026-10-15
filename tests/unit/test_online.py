from worker.pipeline.online import _band, parse_trace_response, pick_frames
from worker.pipeline.recognize import merge_results
from pathlib import Path


def test_band_thresholds():
    assert _band(0.95) == "high" and _band(0.88) == "medium" and _band(0.5) == "low"


def test_parse_trace_drops_adult_and_bad_rows():
    payload = {"result": [
        {"anilist": {"id": 1, "title": {"english": "Show A", "native": "A"}, "isAdult": False}, "similarity": 0.97, "episode": 3, "from": 61.2, "image": "http://x/i.jpg"},
        {"anilist": {"id": 2, "title": {"romaji": "Adult"}, "isAdult": True}, "similarity": 0.99},
        {"anilist": None, "similarity": 0.9},
        {"anilist": {"id": 3, "title": {}}, "similarity": 0.9},
    ]}
    rows = parse_trace_response(payload)
    assert [r["anilist_id"] for r in rows] == [1]
    assert rows[0]["episode"] == 3


def test_pick_frames_limits_and_spreads():
    paths = [Path(f"f{i}.jpg") for i in range(10)]
    picked = pick_frames(paths, 3)
    assert len(picked) == 3 and picked[0] == paths[0] and picked[-1] == paths[-1]


def _cand(title, score, conf="low"):
    return {"title_id": title, "title": title, "score": score, "confidence": conf}


def test_merge_prefers_online_when_local_empty():
    local = {"band": "none", "margin": 0.0, "candidates": [], "signals_used": ["visual"], "message": "none"}
    out = merge_results(local, [_cand("Show A", 0.95, "high")])
    assert out["band"] == "high" and out["candidates"][0]["title"] == "Show A" and out["message"] is None


def test_merge_dedupes_and_keeps_local_when_no_online():
    local = {"band": "high", "margin": 0.2, "candidates": [_cand("Show A", 0.9, "high")], "signals_used": ["visual"]}
    assert merge_results(local, []) is local
    out = merge_results(local, [_cand("show a", 0.8, "medium")])
    assert len(out["candidates"]) == 1
