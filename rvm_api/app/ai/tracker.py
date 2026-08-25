from __future__ import annotations

import math
import time
import uuid
from collections import deque
from dataclasses import dataclass, field

from .schemas import BoundingBox, Candidate


def _iou(a: BoundingBox, b: BoundingBox) -> float:
    x1 = max(a.x1, b.x1)
    y1 = max(a.y1, b.y1)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


def _center_distance(a: BoundingBox, b: BoundingBox) -> float:
    ax, ay = a.center
    bx, by = b.center
    return math.hypot(ax - bx, ay - by)


@dataclass
class Track:
    id: str
    box: BoundingBox
    first_center: tuple[float, float]
    first_seen: float
    last_seen: float
    votes: deque[bool]
    confidences: deque[float]
    accepted: bool = False
    last_candidate: Candidate | None = None

    @property
    def positive_votes(self) -> int:
        return sum(1 for vote in self.votes if vote)

    @property
    def motion_px(self) -> float:
        cx, cy = self.box.center
        fx, fy = self.first_center
        return math.hypot(cx - fx, cy - fy)

    @property
    def mean_confidence(self) -> float:
        return sum(self.confidences) / len(self.confidences) if self.confidences else 0.0


class TemporalTracker:
    """Small deterministic tracker used to gate paid recycling events.

    It intentionally avoids a second tracking ML dependency. A candidate must be
    observed consistently over multiple frames and physically move through the
    camera region before it can be accepted once.
    """

    def __init__(
        self,
        *,
        required_positive_frames: int,
        vote_window: int,
        ttl_seconds: float,
        min_motion_px: float,
        match_iou: float = 0.15,
        match_distance_px: float = 90.0,
    ):
        if required_positive_frames <= 0 or vote_window < required_positive_frames:
            raise ValueError("Invalid temporal voting configuration")
        self.required_positive_frames = required_positive_frames
        self.vote_window = vote_window
        self.ttl_seconds = ttl_seconds
        self.min_motion_px = min_motion_px
        self.match_iou = match_iou
        self.match_distance_px = match_distance_px
        self.tracks: dict[str, Track] = {}

    def reset(self) -> None:
        self.tracks.clear()

    def _purge(self, now: float) -> None:
        expired = [track_id for track_id, track in self.tracks.items() if now - track.last_seen > self.ttl_seconds]
        for track_id in expired:
            del self.tracks[track_id]

    def _match(self, candidate: Candidate, used: set[str]) -> Track | None:
        best: Track | None = None
        best_score = -1.0
        for track_id, track in self.tracks.items():
            if track_id in used:
                continue
            overlap = _iou(track.box, candidate.detection.box)
            distance = _center_distance(track.box, candidate.detection.box)
            if overlap < self.match_iou and distance > self.match_distance_px:
                continue
            score = overlap + max(0.0, 1.0 - distance / self.match_distance_px)
            if score > best_score:
                best = track
                best_score = score
        return best

    def update(self, candidates: list[Candidate], now: float | None = None) -> list[Track]:
        now = time.monotonic() if now is None else now
        self._purge(now)
        used: set[str] = set()
        newly_accepted: list[Track] = []

        for candidate in sorted(candidates, key=lambda c: c.detection.confidence, reverse=True):
            track = self._match(candidate, used)
            if track is None:
                track_id = uuid.uuid4().hex[:12]
                track = Track(
                    id=track_id,
                    box=candidate.detection.box,
                    first_center=candidate.detection.box.center,
                    first_seen=now,
                    last_seen=now,
                    votes=deque(maxlen=self.vote_window),
                    confidences=deque(maxlen=self.vote_window),
                )
                self.tracks[track_id] = track

            used.add(track.id)
            track.box = candidate.detection.box
            track.last_seen = now
            track.last_candidate = candidate
            positive = bool(candidate.accepted_material)
            track.votes.append(positive)
            confidence = candidate.classification.confidence if candidate.classification else candidate.detection.confidence
            track.confidences.append(float(confidence))

            if (
                not track.accepted
                and track.positive_votes >= self.required_positive_frames
                and track.motion_px >= self.min_motion_px
            ):
                track.accepted = True
                newly_accepted.append(track)

        return newly_accepted
