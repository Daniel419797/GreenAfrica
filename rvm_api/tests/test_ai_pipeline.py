import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from app.ai.model_registry import ModelRegistry, ModelRegistryError
from app.ai.pipeline import AiPipeline
from app.ai.schemas import BoundingBox, Classification, Detection


class FakeDetector:
    def __init__(self, boxes, label="bottle", confidence=0.95):
        self.boxes = list(boxes)
        self.label = label
        self.confidence = confidence
        self.index = 0
        self.last_stats = SimpleNamespace(latency_ms=3.5)

    def detect(self, _frame):
        box = self.boxes[min(self.index, len(self.boxes) - 1)]
        self.index += 1
        return [Detection(self.label, self.confidence, box, 0)]


class FakeClassifier:
    def __init__(self, label="pet_clear", confidence=0.96):
        self.label = label
        self.confidence = confidence
        self.last_latency_ms = 1.2

    def classify(self, _crop):
        return Classification(
            label=self.label,
            confidence=self.confidence,
            class_id=0,
            probabilities={self.label: self.confidence},
        )


def make_pipeline(classifier_label="pet_clear"):
    pipeline = AiPipeline(
        manifest_path="missing.json",
        execution_provider="cpu",
        require_hashes=True,
        allowed_object_labels={"bottle"},
        allowed_pet_labels={"pet_clear", "pet_colored"},
        roi_center=(50, 50),
        roi_radius=80,
        min_roi_score=0.1,
        min_box_area_px=50,
        required_positive_frames=2,
        vote_window=3,
        track_ttl_seconds=2.0,
        min_track_motion_px=5.0,
    )
    pipeline.registry = SimpleNamespace(
        version="test-registry",
        detector=SimpleNamespace(version="detector-test"),
        classifier=SimpleNamespace(version="classifier-test", confidence_threshold=0.8),
    )
    pipeline.detector = FakeDetector(
        [BoundingBox(20, 20, 50, 70), BoundingBox(30, 20, 60, 70)]
    )
    pipeline.classifier = FakeClassifier(classifier_label)
    pipeline.ready = True
    return pipeline


class AiPipelineTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.zeros((120, 120, 3), dtype=np.uint8)

    def test_missing_model_fails_closed(self):
        pipeline = AiPipeline(
            manifest_path="definitely-missing.json",
            execution_provider="cpu",
            require_hashes=True,
            allowed_object_labels={"bottle"},
            allowed_pet_labels={"pet_clear"},
            roi_center=(50, 50),
            roi_radius=50,
            min_roi_score=0.2,
            min_box_area_px=50,
            required_positive_frames=2,
            vote_window=3,
            track_ttl_seconds=1.0,
            min_track_motion_px=5.0,
        )
        decision = pipeline.infer(self.frame)
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason, "model_unavailable")

    def test_pet_requires_temporal_votes_and_motion(self):
        pipeline = make_pipeline("pet_clear")
        first = pipeline.infer(self.frame)
        second = pipeline.infer(self.frame)
        self.assertFalse(first.accepted)
        self.assertEqual(first.reason, "temporal_verification_pending")
        self.assertTrue(second.accepted)
        self.assertEqual(second.reason, "verified_pet")
        self.assertEqual(second.material_label, "pet_clear")
        self.assertGreaterEqual(second.evidence["positive_votes"], 2)
        self.assertGreaterEqual(second.evidence["motion_px"], 5.0)

    def test_non_pet_material_is_rejected(self):
        pipeline = make_pipeline("glass")
        for _ in range(3):
            decision = pipeline.infer(self.frame)
            self.assertFalse(decision.accepted)
            self.assertEqual(decision.reason, "non_pet_material")

    def test_static_pet_does_not_count(self):
        pipeline = make_pipeline("pet_clear")
        pipeline.detector = FakeDetector([BoundingBox(20, 20, 50, 70)] * 4)
        for _ in range(4):
            decision = pipeline.infer(self.frame)
            self.assertFalse(decision.accepted)


class ModelRegistryTests(unittest.TestCase):
    def test_registry_rejects_model_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "detector.onnx").write_bytes(b"detector")
            (root / "classifier.onnx").write_bytes(b"classifier")
            manifest = root / "manifest.json"
            manifest.write_text(
                """{
                  \"version\": \"test\",
                  \"detector\": {
                    \"path\": \"detector.onnx\",
                    \"sha256\": \"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\",
                    \"version\": \"1\",
                    \"classes\": [\"bottle\"]
                  },
                  \"classifier\": {
                    \"path\": \"classifier.onnx\",
                    \"sha256\": \"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\",
                    \"version\": \"1\",
                    \"classes\": [\"pet_clear\"]
                  }
                }""",
                encoding="utf-8",
            )
            with self.assertRaises(ModelRegistryError):
                ModelRegistry.load(manifest, require_hashes=True)


if __name__ == "__main__":
    unittest.main()
