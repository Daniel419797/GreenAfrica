from .ai.pipeline import AiPipeline
from .camera import open_camera
from .detector import Detector
from .settings import settings


# Global singletons for app lifetime. Model loading itself happens during FastAPI
# startup so a failed integrity check is visible before the machine accepts items.
_cap = open_camera()

ai_pipeline = (
    AiPipeline(
        manifest_path=settings.model_manifest_path,
        execution_provider=settings.AI_EXECUTION_PROVIDER,
        require_hashes=settings.AI_REQUIRE_MODEL_HASHES,
        allowed_object_labels=set(settings.AI_ALLOWED_OBJECT_LABELS),
        allowed_pet_labels=set(settings.AI_ALLOWED_PET_LABELS),
        roi_center=(settings.ROI_CX, settings.ROI_CY),
        roi_radius=settings.ROI_R,
        min_roi_score=settings.AI_MIN_ROI_SCORE,
        min_box_area_px=settings.AI_MIN_BOX_AREA_PX,
        required_positive_frames=settings.AI_REQUIRED_POSITIVE_FRAMES,
        vote_window=settings.AI_VOTE_WINDOW,
        track_ttl_seconds=settings.AI_TRACK_TTL_SECONDS,
        min_track_motion_px=settings.AI_MIN_TRACK_MOTION_PX,
    )
    if settings.AI_ENABLED
    else None
)

detector = Detector(_cap, ai_pipeline=ai_pipeline)
