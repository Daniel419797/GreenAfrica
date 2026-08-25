from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Sequence

import cv2
import numpy as np

from .model_registry import ModelSpec
from .schemas import BoundingBox, Detection

try:
    import onnxruntime as ort
except ImportError:  # pragma: no cover - exercised by deployment validation
    ort = None


class YoloRuntimeError(RuntimeError):
    pass


@dataclass(frozen=True)
class InferenceStats:
    latency_ms: float
    raw_candidates: int
    kept: int


def _iou(a: BoundingBox, b: BoundingBox) -> float:
    x1 = max(a.x1, b.x1)
    y1 = max(a.y1, b.y1)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


def _nms(detections: Sequence[Detection], iou_threshold: float) -> list[Detection]:
    result: list[Detection] = []
    by_class: dict[int, list[Detection]] = {}
    for det in detections:
        by_class.setdefault(det.class_id, []).append(det)

    for class_dets in by_class.values():
        pending = sorted(class_dets, key=lambda d: d.confidence, reverse=True)
        while pending:
            current = pending.pop(0)
            result.append(current)
            pending = [candidate for candidate in pending if _iou(current.box, candidate.box) < iou_threshold]

    return sorted(result, key=lambda d: d.confidence, reverse=True)


class YoloOnnxDetector:
    """YOLOv5/v8/v11-compatible ONNX detector with class-aware NMS.

    Production expects an exported model whose labels exactly match the model
    manifest. The service never infers class names from an untrusted model file.
    """

    def __init__(self, spec: ModelSpec, execution_provider: str = "auto"):
        if ort is None:
            raise YoloRuntimeError("onnxruntime is not installed")
        self.spec = spec
        self.execution_provider = execution_provider
        self.session = ort.InferenceSession(
            str(spec.path),
            providers=self._resolve_providers(execution_provider),
        )
        inputs = self.session.get_inputs()
        if len(inputs) != 1:
            raise YoloRuntimeError(f"Detector must expose one input, got {len(inputs)}")
        self.input_name = inputs[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        self.last_stats = InferenceStats(latency_ms=0.0, raw_candidates=0, kept=0)
        self._warmup()

    @staticmethod
    def _resolve_providers(requested: str) -> list[str]:
        available = set(ort.get_available_providers())
        aliases = {
            "cpu": "CPUExecutionProvider",
            "cuda": "CUDAExecutionProvider",
            "tensorrt": "TensorrtExecutionProvider",
        }
        requested = requested.lower().strip()
        if requested != "auto":
            provider = aliases.get(requested)
            if provider is None:
                raise YoloRuntimeError(f"Unknown ONNX execution provider: {requested}")
            if provider not in available:
                raise YoloRuntimeError(f"Requested provider {provider} is unavailable; available={sorted(available)}")
            return [provider, "CPUExecutionProvider"] if provider != "CPUExecutionProvider" else [provider]

        ordered = [
            "TensorrtExecutionProvider",
            "CUDAExecutionProvider",
            "CPUExecutionProvider",
        ]
        providers = [p for p in ordered if p in available]
        if not providers:
            raise YoloRuntimeError("No ONNX Runtime execution provider is available")
        return providers

    def _warmup(self) -> None:
        size = self.spec.input_size
        dummy = np.zeros((1, 3, size, size), dtype=np.float32)
        self.session.run(self.output_names, {self.input_name: dummy})

    def _letterbox(self, frame: np.ndarray) -> tuple[np.ndarray, float, float, float]:
        height, width = frame.shape[:2]
        size = self.spec.input_size
        ratio = min(size / width, size / height)
        new_w = int(round(width * ratio))
        new_h = int(round(height * ratio))
        resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        pad_x = (size - new_w) / 2.0
        pad_y = (size - new_h) / 2.0
        left = int(round(pad_x - 0.1))
        right = int(round(pad_x + 0.1))
        top = int(round(pad_y - 0.1))
        bottom = int(round(pad_y + 0.1))
        padded = cv2.copyMakeBorder(
            resized, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114)
        )
        rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
        tensor = rgb.astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))[None, ...]
        return np.ascontiguousarray(tensor), ratio, pad_x, pad_y

    def detect(self, frame: np.ndarray) -> list[Detection]:
        started = time.perf_counter()
        tensor, ratio, pad_x, pad_y = self._letterbox(frame)
        outputs = self.session.run(self.output_names, {self.input_name: tensor})
        if not outputs:
            raise YoloRuntimeError("Detector returned no outputs")

        pred = np.asarray(outputs[0])
        pred = np.squeeze(pred)
        if pred.ndim != 2:
            raise YoloRuntimeError(f"Unsupported YOLO output shape: {outputs[0].shape}")

        class_count = len(self.spec.classes)
        valid_widths = {4 + class_count, 5 + class_count}
        if pred.shape[0] in valid_widths and pred.shape[1] not in valid_widths:
            pred = pred.T
        if pred.shape[1] not in valid_widths:
            raise YoloRuntimeError(
                f"YOLO output width {pred.shape[1]} does not match {class_count} manifest classes"
            )

        has_objectness = pred.shape[1] == 5 + class_count
        candidates: list[Detection] = []
        frame_h, frame_w = frame.shape[:2]

        for row in pred:
            xywh = row[:4]
            if has_objectness:
                objectness = float(row[4])
                scores = row[5:]
            else:
                objectness = 1.0
                scores = row[4:]

            class_id = int(np.argmax(scores))
            confidence = objectness * float(scores[class_id])
            if confidence < self.spec.confidence_threshold:
                continue

            cx, cy, w, h = (float(v) for v in xywh)
            x1 = (cx - w / 2.0 - pad_x) / ratio
            y1 = (cy - h / 2.0 - pad_y) / ratio
            x2 = (cx + w / 2.0 - pad_x) / ratio
            y2 = (cy + h / 2.0 - pad_y) / ratio
            box = BoundingBox(x1, y1, x2, y2).clipped(frame_w, frame_h)
            if box.area <= 1:
                continue
            candidates.append(
                Detection(
                    label=self.spec.classes[class_id],
                    confidence=confidence,
                    box=box,
                    class_id=class_id,
                )
            )

        kept = _nms(candidates, self.spec.iou_threshold or 0.45)
        self.last_stats = InferenceStats(
            latency_ms=(time.perf_counter() - started) * 1000.0,
            raw_candidates=len(candidates),
            kept=len(kept),
        )
        return kept
