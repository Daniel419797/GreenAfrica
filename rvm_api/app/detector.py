import threading
import time
from collections import deque
from typing import Optional

import cv2
import numpy as np

from .ai.pipeline import AiPipeline
from .events import register_accept
from .models import state
from .settings import settings


class Detector:
    """Camera worker with motion pre-filter and model-gated PET acceptance.

    Motion detection is intentionally not authoritative. It only decides when
    to spend compute on AI inference. A paid recycling event can only be emitted
    after AiPipeline returns a temporally verified PET decision.
    """

    def __init__(self, cap, ai_pipeline: AiPipeline | None = None):
        self.cap = cap
        self.ai_pipeline = ai_pipeline
        self.bg: Optional[np.ndarray] = None
        self.mog2 = None
        self.last_count_time = 0.0
        self.last_inference_time = 0.0
        self.last_frame_time = 0.0
        self.frame_buf = deque(maxlen=1)
        self.debug_last_thresh = None
        self.last_ai_decision = None
        self._roi_mask_cache: Optional[np.ndarray] = None
        self._roi_mask_signature: tuple[int, int, int, int, int] | None = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    @staticmethod
    def circular_mask(shape_or_img, cx, cy, r):
        if isinstance(shape_or_img, tuple):
            h, w = shape_or_img[:2]
        else:
            h, w = shape_or_img.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask, (cx, cy), r, 255, -1)
        return mask

    def _roi_mask(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        signature = (h, w, settings.ROI_CX, settings.ROI_CY, settings.ROI_R)
        if self._roi_mask_cache is None or self._roi_mask_signature != signature:
            self._roi_mask_cache = self.circular_mask(
                frame, settings.ROI_CX, settings.ROI_CY, settings.ROI_R
            )
            self._roi_mask_signature = signature
        return self._roi_mask_cache

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="rvm-detector")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _annotate_ai(self, frame: np.ndarray) -> None:
        if self.ai_pipeline is None:
            return
        for candidate in self.ai_pipeline.last_candidates:
            box = candidate.detection.box
            x1, y1, x2, y2 = map(int, (box.x1, box.y1, box.x2, box.y2))
            material = candidate.classification.label if candidate.classification else "unclassified"
            material_conf = candidate.classification.confidence if candidate.classification else 0.0
            color = (0, 200, 0) if candidate.accepted_material else (0, 165, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = (
                f"{candidate.detection.label} {candidate.detection.confidence:.2f} | "
                f"{material} {material_conf:.2f}"
            )
            cv2.putText(
                frame,
                label,
                (x1, max(18, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                color,
                1,
                cv2.LINE_AA,
            )

    def _loop(self):
        ok, frame = self.cap.read()
        if not ok:
            print("[FATAL] Camera not available")
            return

        g0 = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        g0 = cv2.GaussianBlur(g0, (21, 21), 0)
        self.bg = g0.copy()

        self.mog2 = (
            cv2.createBackgroundSubtractorMOG2(history=200, varThreshold=16, detectShadows=False)
            if settings.USE_MOG2
            else None
        )

        consec_hot = 0
        last_idle_reseed = time.time()

        while not self._stop.is_set():
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.02)
                continue

            self.last_frame_time = time.time()
            mask = self._roi_mask(frame)
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            g = cv2.GaussianBlur(g, (21, 21), 0)

            if settings.USE_MOG2 and self.mog2 is not None:
                fgmask = self.mog2.apply(g)
                fgmask = cv2.bitwise_and(fgmask, fgmask, mask=mask)
                thresh = cv2.threshold(fgmask, 127, 255, cv2.THRESH_BINARY)[1]
            else:
                delta = cv2.absdiff(self.bg, g)
                delta_roi = cv2.bitwise_and(delta, delta, mask=mask)
                thresh = cv2.threshold(delta_roi, settings.DIFF_THRESH, 255, cv2.THRESH_BINARY)[1]
                self.bg = cv2.addWeighted(
                    g,
                    settings.BG_LEARN_RATE,
                    self.bg,
                    1.0 - settings.BG_LEARN_RATE,
                    0,
                )

            thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
            thresh = cv2.dilate(thresh, None, iterations=1)
            hot_pixels = int(np.sum(thresh == 255))
            self.debug_last_thresh = thresh
            now = time.time()

            if hot_pixels < (settings.MOTION_PIXELS_THRESHOLD // 2):
                if (now - last_idle_reseed) > settings.IDLE_RESET_SECONDS:
                    if settings.USE_MOG2:
                        self.mog2 = cv2.createBackgroundSubtractorMOG2(
                            history=200, varThreshold=16, detectShadows=False
                        )
                    else:
                        self.bg = g.copy()
                    consec_hot = 0
                    last_idle_reseed = now

            if hot_pixels >= settings.MOTION_PIXELS_THRESHOLD:
                consec_hot += 1
            else:
                consec_hot = 0

            # Motion only wakes the AI. It can never directly register acceptance.
            if (
                settings.AI_ENABLED
                and self.ai_pipeline is not None
                and consec_hot >= settings.CONSEC_FRAMES_REQUIRED
                and (now - self.last_inference_time) >= settings.AI_INFERENCE_MIN_INTERVAL_S
            ):
                decision = self.ai_pipeline.infer(frame)
                self.last_ai_decision = decision
                self.last_inference_time = now
                if decision.accepted and (now - self.last_count_time) >= settings.DETECT_COOLDOWN_S:
                    evidence = {
                        "reason": decision.reason,
                        "confidence": decision.confidence,
                        "object_label": decision.object_label,
                        "material_label": decision.material_label,
                        "track_id": decision.track_id,
                        "model_version": decision.model_version,
                        "detector_version": decision.detector_version,
                        "classifier_version": decision.classifier_version,
                        **decision.evidence,
                    }
                    register_accept(source="ai", evidence=evidence)
                    self.last_count_time = now
                    consec_hot = 0

            cv2.circle(
                frame,
                (settings.ROI_CX, settings.ROI_CY),
                settings.ROI_R,
                (0, 255, 0),
                2,
            )
            self._annotate_ai(frame)
            cv2.putText(
                frame,
                f"Status: {state.message}",
                (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )
            if self.last_ai_decision is not None:
                cv2.putText(
                    frame,
                    f"AI: {self.last_ai_decision.reason}",
                    (10, 56),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (0, 255, 255),
                    1,
                )

            self.frame_buf.append(frame)
            time.sleep(0.01)
