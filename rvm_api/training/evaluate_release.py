from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import cv2

# Allows running from rvm_api with: python training/evaluate_release.py ...
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai.pipeline import AiPipeline  # noqa: E402


def load_cases(path: Path) -> list[dict]:
    cases: list[dict] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSONL at line {line_no}: {exc}") from exc
        if case.get("expected") not in {"accept", "reject"}:
            raise SystemExit(f"Case line {line_no} must set expected=accept|reject")
        if not case.get("video"):
            raise SystemExit(f"Case line {line_no} is missing video")
        cases.append(case)
    if not cases:
        raise SystemExit("No validation cases found")
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description="Field-release gate for GreenAfrica RVM AI")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--cases", required=True, help="JSONL with video, expected and optional material")
    parser.add_argument("--provider", default="auto")
    parser.add_argument("--sample-every", type=int, default=1)
    parser.add_argument("--roi-cx", type=int, default=310)
    parser.add_argument("--roi-cy", type=int, default=190)
    parser.add_argument("--roi-r", type=int, default=55)
    parser.add_argument("--min-roi-score", type=float, default=0.30)
    parser.add_argument("--min-box-area", type=float, default=1200)
    parser.add_argument("--positive-frames", type=int, default=4)
    parser.add_argument("--vote-window", type=int, default=6)
    parser.add_argument("--track-ttl", type=float, default=1.5)
    parser.add_argument("--min-motion", type=float, default=10.0)
    parser.add_argument("--max-false-accept-rate", type=float, default=0.01)
    parser.add_argument("--min-accept-recall", type=float, default=0.95)
    parser.add_argument("--output", default="artifacts/release_evaluation.json")
    args = parser.parse_args()

    if args.sample_every < 1:
        raise SystemExit("--sample-every must be >= 1")

    pipeline = AiPipeline(
        manifest_path=args.manifest,
        execution_provider=args.provider,
        require_hashes=True,
        allowed_object_labels={"bottle"},
        allowed_pet_labels={"pet_clear", "pet_colored"},
        roi_center=(args.roi_cx, args.roi_cy),
        roi_radius=args.roi_r,
        min_roi_score=args.min_roi_score,
        min_box_area_px=args.min_box_area,
        required_positive_frames=args.positive_frames,
        vote_window=args.vote_window,
        track_ttl_seconds=args.track_ttl,
        min_track_motion_px=args.min_motion,
    )
    pipeline.start()
    if not pipeline.ready:
        raise SystemExit(f"Model release could not initialize: {pipeline.error}")

    cases_path = Path(args.cases).resolve()
    cases = load_cases(cases_path)
    results: list[dict] = []
    counts = Counter()
    false_accept_by_material = Counter()

    for case in cases:
        video_path = Path(case["video"])
        if not video_path.is_absolute():
            video_path = (cases_path.parent / video_path).resolve()
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise SystemExit(f"Cannot open validation video: {video_path}")

        pipeline.tracker.reset()
        accepted = False
        accepted_material = None
        last_reason = "no_frames"
        frame_index = 0
        inference_count = 0

        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame_index += 1
            if frame_index % args.sample_every:
                continue
            inference_count += 1
            decision = pipeline.infer(frame)
            last_reason = decision.reason
            if decision.accepted:
                accepted = True
                accepted_material = decision.material_label
                break
        cap.release()

        expected_accept = case["expected"] == "accept"
        if expected_accept and accepted:
            outcome = "tp"
        elif expected_accept and not accepted:
            outcome = "fn"
        elif not expected_accept and accepted:
            outcome = "fp"
            false_accept_by_material[str(case.get("material", "unknown"))] += 1
        else:
            outcome = "tn"
        counts[outcome] += 1
        results.append(
            {
                "video": str(video_path),
                "expected": case["expected"],
                "expected_material": case.get("material"),
                "accepted": accepted,
                "accepted_material": accepted_material,
                "outcome": outcome,
                "last_reason": last_reason,
                "frames_seen": frame_index,
                "inferences": inference_count,
            }
        )

    accept_total = counts["tp"] + counts["fn"]
    reject_total = counts["tn"] + counts["fp"]
    accept_recall = counts["tp"] / accept_total if accept_total else 0.0
    false_accept_rate = counts["fp"] / reject_total if reject_total else 0.0
    report = {
        "manifest": str(Path(args.manifest).resolve()),
        "cases": len(cases),
        "tp": counts["tp"],
        "tn": counts["tn"],
        "fp": counts["fp"],
        "fn": counts["fn"],
        "accept_recall": accept_recall,
        "false_accept_rate": false_accept_rate,
        "false_accept_by_material": dict(false_accept_by_material),
        "release_thresholds": {
            "max_false_accept_rate": args.max_false_accept_rate,
            "min_accept_recall": args.min_accept_recall,
        },
        "passed": (
            false_accept_rate <= args.max_false_accept_rate
            and accept_recall >= args.min_accept_recall
        ),
        "results": results,
    }

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, indent=2))
    pipeline.stop()

    if not report["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
