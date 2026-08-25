from __future__ import annotations

import logging
import math
import threading
import time
from pathlib import Path

import numpy as np

from .classifier import OnnxMaterialClassifier
from .metrics import (
    observe_classifier_ms,
    observe_detector_ms,
    record_accept,
    record_decision,
    set_ready,
)
from .model_registry import ModelRegistry, ModelRegistryError
from .schemas import AiDecision, BoundingBox, Candidate
from .tracker import TemporalTracker
from .yolo_onnx import YoloOnnxDetector

logger = logging.getLogger(__name__)


class AiPipeline:
    """Fail-closed two-stage AI acceptance pipeline.

    Acceptance requires:
      1. a YOLO object detection in the configured RVM entry ROI,
      2. a valid bottle-like object label,
      3. a secondary material classifier identifying an allowed PET type,
      4. multi-frame temporal agreement and real object motion.
    """

    def __init__(
        self,
        *,
        manifest_path: str | Path,
        execution_provider: str,
        require_hashes: bool,
        allowed_object_labels: set[str],
        allowed_pet_labels: set[str],
        roi_center: tuple[int, int],
        roi_radius: int,
        min_roi_score: float,
        min_box_area_px: float,
        required_positive_frames: int,
        vote_window: int,
        track_ttl_seconds: float,
        min_track_motion_px: float,
    ):
        self.manifest_path = str(manifest_path)
        self.execution_provider = execution_provider
        self.require_hashes = require_hashes
        self.allowed_object_labels = {label.lower() for label in allowed_object_labels}
        self.allowed_pet_labels = {label.lower() for label in allowed_pet_labels}
        self.roi_center = roi_center
        self.roi_radius = roi_radius
        self.min_roi_score = min_roi_score
        self.min_box_area_px = min_box_area_px
        self.tracker = TemporalTracker(
            required_positive_frames=required_positive_frames,
            vote_window=vote_window,
            ttl_seconds=track_ttl_seconds,
            min_motion_px=min_track_motion_px,
        )
        self.registry: ModelRegistry | None = None
        self.detector: YoloOnnxDetector | None = None
        self.classifier: OnnxMaterialClassifier | None = None
        self.ready = False
        self.error: str | None = None
        self.last_decision = AiDecision(accepted=False, reason="not_started")
        self.last_candidates: list[Candidate] = []
        self.last_inference_at: float | None = None
        self.total_inferences = 0
        self.total_accepts = 0
        self.total_rejects = 0
        self._lock = threading.RLock()
        set_ready(False)

    def start(self) -> None:
        with self._lock:
            try:
                self.registry = ModelRegistry.load(self.manifest_path, require_hashes=self.require_hashes)
                self.detector = YoloOnnxDetector(
                    self.registry.detector,
                    execution_provider=self.execution_provider,
                )
                self.classifier = OnnxMaterialClassifier(
                    self.registry.classifier,
                    execution_provider=self.execution_provider,
                )
                missing_object_labels = self.allowed_object_labels.difference(
                    label.lower() for label in self.registry.detector.classes
                )
                missing_pet_labels = self.allowed_pet_labels.difference(
                    label.lower() for label in self.registry.classifier.classes
                )
                if missing_object_labels:
                    raise ModelRegistryError(
                        f"Allowed detector labels absent from manifest: {sorted(missing_object_labels)}"
                    )
                if missing_pet_labels:
                    raise ModelRegistryError(
                        f"Allowed PET labels absent from manifest: {sorted(missing_pet_labels)}"
                    )
                self.ready = True
                self.error = None
                self.tracker.reset()
                set_ready(True)
                logger.info(
                    "RVM AI ready: registry=%s detector=%s classifier=%s",
                    self.registry.version,
                    self.registry.detector.version,
                    self.registry.classifier.version,
                )
            except Exception as exc:
                self.ready = False
                self.error = f"{type(exc).__name__}: {exc}"
                self.detector = None
                self.classifier = None
                set_ready(False)
                logger.exception("RVM AI failed to initialize")

    def stop(self) -> None:
        with self._lock:
            self.ready = False
            self.detector = None
            self.classifier = None
            self.tracker.reset()
            set_ready(False)

    def update_roi(self, center: tuple[int, int], radius: int) -> None:
        with self._lock:
            self.roi_center = center
            self.roi_radius = radius
            self.tracker.reset()

    def _roi_score(self, box: BoundingBox) -> float:
        cx, cy = box.center
        rx, ry = self.roi_center
        distance = math.hypot(cx - rx, cy - ry)
        denom = max(1.0, self.roi_radius * 1.5)
        return max(0.0, 1.0 - distance / denom)

    @staticmethod
    def _crop(frame: np.ndarray, box: BoundingBox, padding: float = 0.08) -> np.ndarray:
        h, w = frame.shape[:2]
        pad_x = box.width * padding
        pad_y = box.height * padding
        x1 = max(0, int(math.floor(box.x1 - pad_x)))
        y1 = max(0, int(math.floor(box.y1 - pad_y)))
        x2 = min(w, int(math.ceil(box.x2 + pad_x)))
        y2 = min(h, int(math.ceil(box.y2 + pad_y)))
        return frame[y1:y2, x1:x2]

    def infer(self, frame: np.ndarray) -> AiDecision:
        with self._lock:
            self.total_inferences += 1
            self.last_inference_at = time.time()
            if not self.ready or self.detector is None or self.classifier is None or self.registry is None:
                self.total_rejects += 1
                self.last_candidates = []
                self.last_decision = AiDecision(
                    accepted=False,
                    reason="model_unavailable",
                    evidence={"error": self.error},
                )
                record_decision(reason=self.last_decision.reason, accepted=False)
                return self.last_decision

            try:
                detections = self.detector.detect(frame)
                observe_detector_ms(self.detector.last_stats.latency_ms)
                candidates: list[Candidate] = []

                for detection in detections:
                    if detection.label.lower() not in self.allowed_object_labels:
                        continue
                    if detection.box.area < self.min_box_area_px:
                        continue
                    roi_score = self._roi_score(detection.box)
                    if roi_score < self.min_roi_score:
                        continue

                    classification = self.classifier.classify(self._crop(frame, detection.box))
                    observe_classifier_ms(self.classifier.last_latency_ms)
                    accepted_material = (
                        classification.label.lower() in self.allowed_pet_labels
                        and classification.confidence >= self.registry.classifier.confidence_threshold
                    )
                    candidates.append(
                        Candidate(
                            detection=detection,
                            classification=classification,
                            roi_overlap=roi_score,
                            accepted_material=accepted_material,
                        )
                    )

                self.last_candidates = candidates
                accepted_tracks = self.tracker.update(candidates)
                if accepted_tracks:
                    track = max(accepted_tracks, key=lambda item: item.mean_confidence)
                    candidate = track.last_candidate
                    assert candidate is not None and candidate.classification is not None
                    evidence = {
                        "detector_confidence": round(candidate.detection.confidence, 6),
                        "material_confidence": round(candidate.classification.confidence, 6),
                        "roi_score": round(candidate.roi_overlap, 6),
                        "bbox": [
                            round(candidate.detection.box.x1, 2),
                            round(candidate.detection.box.y1, 2),
                            round(candidate.detection.box.x2, 2),
                            round(candidate.detection.box.y2, 2),
                        ],
                        "positive_votes": track.positive_votes,
                        "motion_px": round(track.motion_px, 2),
                        "detector_latency_ms": round(self.detector.last_stats.latency_ms, 2),
                        "classifier_latency_ms": round(self.classifier.last_latency_ms, 2),
                    }
                    self.total_accepts += 1
                    self.last_decision = AiDecision(
                        accepted=True,
                        reason="verified_pet",
                        confidence=track.mean_confidence,
                        object_label=candidate.detection.label,
                        material_label=candidate.classification.label,
                        track_id=track.id,
                        model_version=self.registry.version,
                        detector_version=self.registry.detector.version,
                        classifier_version=self.registry.classifier.version,
                        evidence=evidence,
                    )
                    record_decision(reason=self.last_decision.reason, accepted=True)
                    record_accept(candidate.classification.label, track.mean_confidence)
                    return self.last_decision

                reason = "no_candidate"
                if candidates:
                    if any(candidate.accepted_material for candidate in candidates):
                        reason = "temporal_verification_pending"
                    else:
                        reason = "non_pet_material"
                self.total_rejects += 1
                self.last_decision = AiDecision(
                    accepted=False,
                    reason=reason,
                    model_version=self.registry.version,
                    detector_version=self.registry.detector.version,
                    classifier_version=self.registry.classifier.version,
                    evidence={
                        "candidate_count": len(candidates),
                        "detector_latency_ms": round(self.detector.last_stats.latency_ms, 2),
                    },
                )
                record_decision(reason=self.last_decision.reason, accepted=False)
                return self.last_decision
            except Exception as exc:
                self.total_rejects += 1
                self.error = f"{type(exc).__name__}: {exc}"
                self.last_candidates = []
                self.last_decision = AiDecision(
                    accepted=False,
                    reason="inference_error",
                    model_version=self.registry.version if self.registry else None,
                    evidence={"error": self.error},
                )
                record_decision(reason=self.last_decision.reason, accepted=False)
                logger.exception("RVM AI inference failed")
                return self.last_decision

    def status(self) -> dict:
        with self._lock:
            registry = self.registry
            return {
                "ready": self.ready,
                "error": self.error,
                "manifest": self.manifest_path,
                "registry_version": registry.version if registry else None,
                "detector_version": registry.detector.version if registry else None,
                "classifier_version": registry.classifier.version if registry else None,
                "execution_provider": self.execution_provider,
                "require_hashes": self.require_hashes,
                "total_inferences": self.total_inferences,
                "total_accepts": self.total_accepts,
                "total_rejects": self.total_rejects,
                "last_inference_at": self.last_inference_at,
                "last_decision": self.last_decision.__dict__,
            }
