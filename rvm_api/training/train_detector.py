from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path

import numpy as np
import torch
from ultralytics import YOLO


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the GreenAfrica RVM YOLO detector")
    parser.add_argument("--data", required=True, help="Ultralytics dataset YAML")
    parser.add_argument("--base-model", default="yolo11s.pt")
    parser.add_argument("--epochs", type=int, default=160)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--device", default="0" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=419797)
    parser.add_argument("--patience", type=int, default=30)
    parser.add_argument("--output", default="artifacts/detector")
    parser.add_argument("--version", required=True, help="Semantic/date model release version")
    args = parser.parse_args()

    seed_everything(args.seed)
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    model = YOLO(args.base_model)
    train_result = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        workers=args.workers,
        seed=args.seed,
        deterministic=True,
        patience=args.patience,
        project=str(output_dir),
        name="run",
        exist_ok=True,
        pretrained=True,
        optimizer="AdamW",
        cos_lr=True,
        close_mosaic=15,
        amp=True,
        cache=False,
        plots=True,
        save=True,
        val=True,
    )

    best_pt = output_dir / "run" / "weights" / "best.pt"
    if not best_pt.exists():
        raise SystemExit(f"Training completed without best.pt at {best_pt}")

    best_model = YOLO(str(best_pt))
    val_metrics = best_model.val(data=args.data, split="val", imgsz=args.imgsz, device=args.device)

    test_metrics = None
    try:
        test_metrics = best_model.val(data=args.data, split="test", imgsz=args.imgsz, device=args.device)
    except Exception as exc:
        print(f"[warning] held-out test split was not evaluated: {exc}")

    export_path = Path(
        best_model.export(
            format="onnx",
            imgsz=args.imgsz,
            opset=17,
            dynamic=False,
            simplify=True,
            half=False,
            nms=False,
        )
    )
    released_onnx = output_dir / "pet_detector.onnx"
    shutil.copy2(export_path, released_onnx)
    shutil.copy2(best_pt, output_dir / "pet_detector.pt")

    names = best_model.names
    if isinstance(names, dict):
        classes = [names[index] for index in sorted(names)]
    else:
        classes = list(names)

    def serialize(metrics):
        if metrics is None:
            return None
        box = getattr(metrics, "box", None)
        return {
            "map50_95": float(getattr(box, "map", 0.0)) if box is not None else None,
            "map50": float(getattr(box, "map50", 0.0)) if box is not None else None,
            "map75": float(getattr(box, "map75", 0.0)) if box is not None else None,
            "fitness": float(getattr(metrics, "fitness", 0.0) or 0.0),
        }

    metadata = {
        "version": args.version,
        "base_model": args.base_model,
        "dataset": str(Path(args.data).resolve()),
        "seed": args.seed,
        "image_size": args.imgsz,
        "classes": classes,
        "val": serialize(val_metrics),
        "test": serialize(test_metrics),
        "onnx": str(released_onnx),
        "train_results_dir": str(getattr(train_result, "save_dir", output_dir / "run")),
    }
    (output_dir / "detector_metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
