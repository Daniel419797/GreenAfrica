from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    def clipped(self, width: int, height: int) -> "BoundingBox":
        return BoundingBox(
            max(0.0, min(float(width - 1), self.x1)),
            max(0.0, min(float(height - 1), self.y1)),
            max(0.0, min(float(width - 1), self.x2)),
            max(0.0, min(float(height - 1), self.y2)),
        )


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    box: BoundingBox
    class_id: int


@dataclass(frozen=True)
class Classification:
    label: str
    confidence: float
    class_id: int
    probabilities: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Candidate:
    detection: Detection
    classification: Classification | None
    roi_overlap: float
    accepted_material: bool


@dataclass(frozen=True)
class AiDecision:
    accepted: bool
    reason: str
    confidence: float = 0.0
    object_label: str | None = None
    material_label: str | None = None
    track_id: str | None = None
    model_version: str | None = None
    detector_version: str | None = None
    classifier_version: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
