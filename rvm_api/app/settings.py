import os
from pathlib import Path

from pydantic import BaseModel


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if not value:
        return default
    return tuple(part.strip() for part in value.split(",") if part.strip())


class Settings(BaseModel):
    # Camera
    CAM_INDEX: int = int(os.getenv("RVM_CAM_INDEX", "0"))
    FRAME_W: int = int(os.getenv("RVM_FRAME_W", "640"))
    FRAME_H: int = int(os.getenv("RVM_FRAME_H", "480"))

    # Camera image controls, applied via v4l2-ctl on open.
    CAM_V4L2_CONTROLS: dict = {
        "auto_exposure": 3,
        "white_balance_automatic": 1,
        "gain": 32,
        "brightness": 0,
        "power_line_frequency": 1,
    }

    # ROI (physical entry gate)
    ROI_CX: int = int(os.getenv("RVM_ROI_CX", "310"))
    ROI_CY: int = int(os.getenv("RVM_ROI_CY", "190"))
    ROI_R: int = int(os.getenv("RVM_ROI_R", "55"))

    # Motion is now only a cheap pre-filter. It can never award points.
    USE_MOG2: bool = _env_bool("RVM_USE_MOG2", True)
    MOTION_PIXELS_THRESHOLD: int = int(os.getenv("RVM_MOTION_PIXELS_THRESHOLD", "1500"))
    CONSEC_FRAMES_REQUIRED: int = int(os.getenv("RVM_MOTION_CONSEC_FRAMES", "3"))
    DETECT_COOLDOWN_S: float = float(os.getenv("RVM_DETECT_COOLDOWN_S", "2.5"))
    DIFF_THRESH: int = int(os.getenv("RVM_DIFF_THRESH", "15"))
    BG_LEARN_RATE: float = float(os.getenv("RVM_BG_LEARN_RATE", "0.005"))
    IDLE_RESET_SECONDS: float = float(os.getenv("RVM_IDLE_RESET_SECONDS", "10"))

    # Production AI acceptance policy
    AI_ENABLED: bool = _env_bool("RVM_AI_ENABLED", True)
    AI_FAIL_STARTUP_IF_UNAVAILABLE: bool = _env_bool("RVM_AI_FAIL_STARTUP_IF_UNAVAILABLE", False)
    AI_MODEL_MANIFEST: str = os.getenv("RVM_AI_MODEL_MANIFEST", "models/manifest.json")
    AI_REQUIRE_MODEL_HASHES: bool = _env_bool("RVM_AI_REQUIRE_MODEL_HASHES", True)
    AI_EXECUTION_PROVIDER: str = os.getenv("RVM_AI_EXECUTION_PROVIDER", "auto")
    AI_ALLOWED_OBJECT_LABELS: tuple[str, ...] = _env_csv(
        "RVM_AI_ALLOWED_OBJECT_LABELS", ("bottle",)
    )
    AI_ALLOWED_PET_LABELS: tuple[str, ...] = _env_csv(
        "RVM_AI_ALLOWED_PET_LABELS", ("pet_clear", "pet_colored")
    )
    AI_MIN_ROI_SCORE: float = float(os.getenv("RVM_AI_MIN_ROI_SCORE", "0.30"))
    AI_MIN_BOX_AREA_PX: float = float(os.getenv("RVM_AI_MIN_BOX_AREA_PX", "1200"))
    AI_REQUIRED_POSITIVE_FRAMES: int = int(os.getenv("RVM_AI_REQUIRED_POSITIVE_FRAMES", "4"))
    AI_VOTE_WINDOW: int = int(os.getenv("RVM_AI_VOTE_WINDOW", "6"))
    AI_TRACK_TTL_SECONDS: float = float(os.getenv("RVM_AI_TRACK_TTL_SECONDS", "1.5"))
    AI_MIN_TRACK_MOTION_PX: float = float(os.getenv("RVM_AI_MIN_TRACK_MOTION_PX", "10"))
    AI_INFERENCE_MIN_INTERVAL_S: float = float(os.getenv("RVM_AI_INFERENCE_MIN_INTERVAL_S", "0.10"))

    # Manual/operator controls are disabled by default. When enabled, write
    # endpoints require X-RVM-Admin-Token using this secret.
    ALLOW_MANUAL_EVENTS: bool = _env_bool("RVM_ALLOW_MANUAL_EVENTS", False)
    ADMIN_TOKEN: str = os.getenv("RVM_ADMIN_TOKEN", "")

    # JPEG quality for tooling images
    JPEG_QUALITY: int = int(os.getenv("RVM_JPEG_QUALITY", "80"))

    @property
    def model_manifest_path(self) -> Path:
        path = Path(self.AI_MODEL_MANIFEST)
        if path.is_absolute():
            return path
        # main.py normally runs from rvm_api; resolving here also works from tests.
        rvm_api_dir = Path(__file__).resolve().parent.parent
        return (rvm_api_dir / path).resolve()


settings = Settings()
