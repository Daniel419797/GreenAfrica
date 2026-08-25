from __future__ import annotations

import time

import cv2
import numpy as np

from .model_registry import ModelSpec
from .schemas import Classification

try:
    import onnxruntime as ort
except ImportError:  # pragma: no cover
    ort = None


class ClassifierRuntimeError(RuntimeError):
    pass


class OnnxMaterialClassifier:
    """Secondary material classifier for candidate bottle crops.

    The classifier is deliberately separate from the detector so acceptance can
    require agreement between object identity and material identity. This makes
    false positives such as glass bottles, cans, hands, and random objects much
    less likely to create a paid recycling event.
    """

    IMAGENET_MEAN = (0.485, 0.456, 0.406)
    IMAGENET_STD = (0.229, 0.224, 0.225)

    def __init__(self, spec: ModelSpec, execution_provider: str = "auto"):
        if ort is None:
            raise ClassifierRuntimeError("onnxruntime is not installed")
        self.spec = spec
        self.session = ort.InferenceSession(
            str(spec.path),
            providers=self._resolve_providers(execution_provider),
        )
        inputs = self.session.get_inputs()
        if len(inputs) != 1:
            raise ClassifierRuntimeError(f"Classifier must expose one input, got {len(inputs)}")
        self.input_name = inputs[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]
        self.last_latency_ms = 0.0
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
                raise ClassifierRuntimeError(f"Unknown ONNX execution provider: {requested}")
            if provider not in available:
                raise ClassifierRuntimeError(
                    f"Requested provider {provider} unavailable; available={sorted(available)}"
                )
            return [provider, "CPUExecutionProvider"] if provider != "CPUExecutionProvider" else [provider]

        ordered = ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"]
        providers = [p for p in ordered if p in available]
        if not providers:
            raise ClassifierRuntimeError("No ONNX Runtime execution provider is available")
        return providers

    def _warmup(self) -> None:
        size = self.spec.input_size
        dummy = np.zeros((1, 3, size, size), dtype=np.float32)
        self.session.run(self.output_names, {self.input_name: dummy})

    def _preprocess(self, crop: np.ndarray) -> np.ndarray:
        if crop.size == 0:
            raise ClassifierRuntimeError("Cannot classify an empty crop")
        size = self.spec.input_size
        resized = cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        mean = np.asarray(self.spec.mean or self.IMAGENET_MEAN, dtype=np.float32)
        std = np.asarray(self.spec.std or self.IMAGENET_STD, dtype=np.float32)
        rgb = (rgb - mean) / std
        tensor = np.transpose(rgb, (2, 0, 1))[None, ...]
        return np.ascontiguousarray(tensor, dtype=np.float32)

    @staticmethod
    def _softmax(values: np.ndarray) -> np.ndarray:
        values = values.astype(np.float64)
        values = values - np.max(values)
        exp = np.exp(values)
        denom = float(np.sum(exp))
        if denom == 0 or not np.isfinite(denom):
            raise ClassifierRuntimeError("Classifier produced invalid logits")
        return (exp / denom).astype(np.float32)

    def classify(self, crop: np.ndarray) -> Classification:
        started = time.perf_counter()
        outputs = self.session.run(self.output_names, {self.input_name: self._preprocess(crop)})
        if not outputs:
            raise ClassifierRuntimeError("Classifier returned no outputs")
        logits = np.asarray(outputs[0]).squeeze()
        if logits.ndim != 1 or logits.shape[0] != len(self.spec.classes):
            raise ClassifierRuntimeError(
                f"Classifier output shape {outputs[0].shape} does not match {len(self.spec.classes)} classes"
            )
        probabilities = self._softmax(logits)
        class_id = int(np.argmax(probabilities))
        confidence = float(probabilities[class_id])
        self.last_latency_ms = (time.perf_counter() - started) * 1000.0
        return Classification(
            label=self.spec.classes[class_id],
            confidence=confidence,
            class_id=class_id,
            probabilities={
                label: float(probabilities[idx]) for idx, label in enumerate(self.spec.classes)
            },
        )
