from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_list(value: str) -> list[str]:
    values = [part.strip() for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("class list cannot be empty")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a verified GreenAfrica AI model manifest")
    parser.add_argument("--detector", required=True)
    parser.add_argument("--classifier", required=True)
    parser.add_argument("--detector-classes", type=csv_list, required=True)
    parser.add_argument("--classifier-classes-json", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--detector-confidence", type=float, default=0.62)
    parser.add_argument("--detector-iou", type=float, default=0.45)
    parser.add_argument("--classifier-confidence", type=float, default=0.78)
    parser.add_argument("--output-dir", default="models")
    args = parser.parse_args()

    detector = Path(args.detector).resolve()
    classifier = Path(args.classifier).resolve()
    if not detector.exists() or not classifier.exists():
        raise SystemExit("Both ONNX files must exist")

    classifier_classes = json.loads(Path(args.classifier_classes_json).read_text(encoding="utf-8"))
    if not isinstance(classifier_classes, list) or not all(isinstance(v, str) for v in classifier_classes):
        raise SystemExit("classifier classes file must contain a JSON string list")

    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    detector_out = output / "pet_detector.onnx"
    classifier_out = output / "pet_material_classifier.onnx"
    shutil.copy2(detector, detector_out)
    shutil.copy2(classifier, classifier_out)

    manifest = {
        "version": args.version,
        "detector": {
            "name": "greenafrica-rvm-yolo",
            "path": detector_out.name,
            "sha256": sha256(detector_out),
            "version": args.version,
            "input_size": 640,
            "classes": args.detector_classes,
            "confidence_threshold": args.detector_confidence,
            "iou_threshold": args.detector_iou,
        },
        "classifier": {
            "name": "greenafrica-pet-material",
            "path": classifier_out.name,
            "sha256": sha256(classifier_out),
            "version": args.version,
            "input_size": 224,
            "classes": classifier_classes,
            "confidence_threshold": args.classifier_confidence,
            "mean": [0.485, 0.456, 0.406],
            "std": [0.229, 0.224, 0.225],
        },
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(manifest_path)
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
