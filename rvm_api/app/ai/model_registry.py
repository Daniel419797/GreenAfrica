from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ModelRegistryError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelSpec:
    name: str
    path: Path
    sha256: str
    version: str
    input_size: int
    classes: tuple[str, ...]
    confidence_threshold: float
    iou_threshold: float | None = None
    mean: tuple[float, float, float] | None = None
    std: tuple[float, float, float] | None = None


@dataclass(frozen=True)
class ModelRegistry:
    manifest_path: Path
    version: str
    detector: ModelSpec
    classifier: ModelSpec

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def load(cls, manifest_path: str | Path, *, require_hashes: bool = True) -> "ModelRegistry":
        manifest_path = Path(manifest_path).expanduser().resolve()
        if not manifest_path.exists():
            raise ModelRegistryError(f"AI model manifest not found: {manifest_path}")

        try:
            payload: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelRegistryError(f"Invalid AI model manifest: {exc}") from exc

        base_dir = manifest_path.parent

        def parse_spec(key: str) -> ModelSpec:
            raw = payload.get(key)
            if not isinstance(raw, dict):
                raise ModelRegistryError(f"Missing model spec: {key}")

            model_path = Path(str(raw.get("path", "")))
            if not model_path.is_absolute():
                model_path = (base_dir / model_path).resolve()

            classes = raw.get("classes")
            if not isinstance(classes, list) or not classes or not all(isinstance(v, str) for v in classes):
                raise ModelRegistryError(f"{key}.classes must be a non-empty string list")

            sha256 = str(raw.get("sha256", "")).lower().strip()
            if require_hashes and len(sha256) != 64:
                raise ModelRegistryError(f"{key}.sha256 must contain a production SHA-256 digest")
            if not model_path.exists():
                raise ModelRegistryError(f"{key} model file not found: {model_path}")
            if sha256:
                actual = cls._sha256(model_path)
                if actual != sha256:
                    raise ModelRegistryError(
                        f"{key} model integrity check failed: expected {sha256}, got {actual}"
                    )

            mean = raw.get("mean")
            std = raw.get("std")
            return ModelSpec(
                name=str(raw.get("name", key)),
                path=model_path,
                sha256=sha256,
                version=str(raw.get("version", "unknown")),
                input_size=int(raw.get("input_size", 640 if key == "detector" else 224)),
                classes=tuple(classes),
                confidence_threshold=float(raw.get("confidence_threshold", 0.5)),
                iou_threshold=(
                    float(raw.get("iou_threshold", 0.45)) if key == "detector" else None
                ),
                mean=tuple(float(v) for v in mean) if isinstance(mean, list) and len(mean) == 3 else None,
                std=tuple(float(v) for v in std) if isinstance(std, list) and len(std) == 3 else None,
            )

        return cls(
            manifest_path=manifest_path,
            version=str(payload.get("version", "unknown")),
            detector=parse_spec("detector"),
            classifier=parse_spec("classifier"),
        )
