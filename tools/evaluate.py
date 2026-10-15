#!/usr/bin/env python3
"""Evaluate SceneSeek against a labeled, held-out collection of local clips/images."""
from __future__ import annotations
import argparse
import json
import math
import sys
import time
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "apps" / "worker"))
from app.services.media import UnsupportedMedia, dedupe_paths, extract_video_frames, prepare_image, probe_video, validate_image_bytes  # noqa: E402
from worker.pipeline.recognize import recognize  # noqa: E402


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, math.ceil(percentile * len(ordered)) - 1))]


def _process_fixture(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    with tempfile.TemporaryDirectory(prefix="sceneseek-eval-") as temp:
        work = Path(temp)
        frames_dir = work / "frames"
        frames_dir.mkdir()
        if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
            data = path.read_bytes()
            validate_image_bytes(data)
            frame = frames_dir / "frame_001.jpg"
            image = prepare_image(path, max_width=1024)
            image.save(frame, format="JPEG", quality=92)
            image.close()
            frames = [frame]
            video_path = None
        elif suffix in {".mp4", ".webm", ".mov"}:
            info = probe_video(path, 30)
            frames = extract_video_frames(path, frames_dir, info["duration"])
            video_path = path
        else:
            raise UnsupportedMedia(f"Unsupported fixture extension: {suffix}")
        frames = dedupe_paths(frames)
        return recognize(frames, work, video_path=video_path)


def evaluate(labels_path: Path) -> dict[str, Any]:
    labels_data = json.loads(labels_path.read_text(encoding="utf-8"))
    if not isinstance(labels_data, list) or not labels_data:
        raise ValueError("The labels file must be a non-empty JSON list of {'file','title_id'} objects.")
    n = top1 = top5 = 0
    reciprocal_sum = 0.0
    latencies: list[int] = []
    calibration: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "correct": 0})
    per_title: dict[str, dict[str, Any]] = defaultdict(lambda: {"n": 0, "top1": 0, "title": None})
    confusion: Counter[tuple[str, str]] = Counter()
    failures: list[dict[str, str]] = []

    for row_number, item in enumerate(labels_data, start=1):
        if not isinstance(item, dict) or not item.get("file") or not item.get("title_id"):
            raise ValueError(f"labels row {row_number} needs 'file' and 'title_id'.")
        media_path = Path(item["file"])
        if not media_path.is_absolute():
            media_path = (ROOT / media_path).resolve()
        expected = str(item["title_id"])
        title_name = str(item.get("title") or expected)
        started = time.perf_counter()
        result: dict[str, Any] = {}
        try:
            result = _process_fixture(media_path)
            candidates = result.get("candidates") or []
        except Exception as exc:
            failures.append({"file": str(item["file"]), "error": str(exc)[:250]})
            candidates = []
        latency = int((time.perf_counter() - started) * 1000)
        latencies.append(latency)
        predicted_ids = [str(candidate.get("title_id")) for candidate in candidates]
        rank = predicted_ids.index(expected) + 1 if expected in predicted_ids else 0
        n += 1
        top1 += int(rank == 1)
        top5 += int(1 <= rank <= 5)
        reciprocal_sum += 1 / rank if rank else 0
        band = str(result.get("band", "none"))
        calibration[band]["n"] += 1
        calibration[band]["correct"] += int(rank == 1)
        per_title[expected]["n"] += 1
        per_title[expected]["top1"] += int(rank == 1)
        per_title[expected]["title"] = title_name
        if predicted_ids:
            confusion[(expected, predicted_ids[0])] += 1
        print(f"[{row_number}/{len(labels_data)}] {media_path.name}: rank={rank or 'miss'} · {latency} ms")

    return {
        "n": n,
        "top1": round(top1 / n, 4),
        "top5": round(top5 / n, 4),
        "mrr": round(reciprocal_sum / n, 4),
        "p50_ms": _percentile(latencies, 0.50),
        "p95_ms": _percentile(latencies, 0.95),
        "high_band_precision": round(calibration["high"]["correct"] / calibration["high"]["n"], 4) if calibration["high"]["n"] else None,
        "calibration": {band: {"n": values["n"], "precision": round(values["correct"] / values["n"], 4) if values["n"] else None}
                        for band, values in sorted(calibration.items())},
        "per_title": {key: {"title": value["title"], "n": value["n"], "top1": round(value["top1"] / value["n"], 4)}
                      for key, value in sorted(per_title.items())},
        "confusion_top8": [{"expected": a, "predicted": b, "count": count}
                            for (a, b), count in confusion.most_common(8)],
        "failures": failures,
        "note": "Closed-set metrics on the supplied labeled files; not a guarantee for arbitrary uploads.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, default=Path("tests/fixtures/labels.json"))
    parser.add_argument("--output", type=Path, default=Path("reports/evaluation.json"))
    args = parser.parse_args()
    labels = args.labels if args.labels.is_absolute() else ROOT / args.labels
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        report = evaluate(labels.resolve())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md = output.with_suffix(".md")
    md.write_text(
        "# SceneSeek Evaluation\n\n" +
        f"- Samples: {report['n']}\n- Top-1: {report['top1']:.1%}\n- Top-5: {report['top5']:.1%}\n" +
        f"- MRR: {report['mrr']:.4f}\n- High-band precision: {report['high_band_precision'] if report['high_band_precision'] is not None else 'N/A'}\n" +
        f"- p50 latency: {report['p50_ms']} ms\n- p95 latency: {report['p95_ms']} ms\n\n" +
        "> Closed-set metrics on the supplied labeled files; not a guarantee for arbitrary uploads.\n", encoding="utf-8")
    print(f"Top-1={report['top1']:.1%} Top-5={report['top5']:.1%} MRR={report['mrr']:.3f} p95={report['p95_ms']} ms")
    print(f"Wrote {output} and {md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
