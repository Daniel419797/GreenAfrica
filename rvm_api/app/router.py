import hmac
import io
import time
from pathlib import Path
from typing import Any, Optional

import cv2
import qrcode
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .events import register_accept, register_reject
from .factory import ai_pipeline, detector
from .models import event_lock, state
from .settings import settings

WEB_DIR = Path(__file__).resolve().parent.parent / "web"
router = APIRouter()


def require_admin(x_rvm_admin_token: Optional[str] = Header(default=None)) -> None:
    if not settings.ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Operator controls are disabled until RVM_ADMIN_TOKEN is configured",
        )
    if not x_rvm_admin_token or not hmac.compare_digest(x_rvm_admin_token, settings.ADMIN_TOKEN):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid operator token")


# -------------------- Kiosk UI --------------------
@router.get("/", include_in_schema=False)
@router.get("/kiosk", include_in_schema=False)
def kiosk_page():
    return FileResponse(WEB_DIR / "kiosk.html", media_type="text/html")


@router.get("/kiosk/ding.mp3", include_in_schema=False)
def kiosk_ding():
    return FileResponse(WEB_DIR / "ding.mp3", media_type="audio/mpeg")


# -------------------- Health / AI status --------------------
@router.get("/health/live")
def health_live():
    return {"status": "alive"}


@router.get("/health/ready")
def health_ready():
    camera_ready = bool(detector.cap is not None and detector.cap.isOpened())
    ai_ready = True if not settings.AI_ENABLED else bool(ai_pipeline and ai_pipeline.ready)
    ready = camera_ready and ai_ready
    payload = {
        "ready": ready,
        "camera_ready": camera_ready,
        "ai_enabled": settings.AI_ENABLED,
        "ai_ready": ai_ready,
        "ai_error": ai_pipeline.error if ai_pipeline else None,
    }
    if not ready:
        return Response(
            content=__import__("json").dumps(payload),
            media_type="application/json",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return payload


@router.get("/ai/status")
def ai_status():
    if ai_pipeline is None:
        return {"enabled": False, "ready": False, "reason": "AI disabled"}
    return {"enabled": True, **ai_pipeline.status()}


# -------------------- Status --------------------
class StatusOut(BaseModel):
    message: str
    points: int
    last_event: Optional[str] = None
    last_code: Optional[str] = None
    last_ai: Optional[dict[str, Any]] = None
    last_rejection_reason: Optional[str] = None


@router.get("/status", response_model=StatusOut)
def get_status():
    with event_lock:
        return StatusOut(**state.model_dump())


# -------------------- Operator controls --------------------
@router.post("/event/accept")
def accept_event(_: None = Depends(require_admin)):
    if not settings.ALLOW_MANUAL_EVENTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manual acceptance is disabled; production acceptance requires AI verification",
        )
    register_accept(source="manual", evidence={"operator_override": True})
    return {"ok": True, "code": state.last_code, "points": state.points}


@router.post("/event/reject")
def reject_event(_: None = Depends(require_admin)):
    if not settings.ALLOW_MANUAL_EVENTS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manual events are disabled")
    register_reject(source="manual", reason="operator_reject", evidence={"operator_override": True})
    return {"ok": True}


@router.get("/qr.png")
def qr_png(code: Optional[str] = None):
    code = code or state.last_code or "NO-CODE"
    points = state.points or 0
    img = qrcode.make(f"http://greenafrica.earth/dashboard?code={code}&points={points}")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")


@router.post("/reset")
def reset_status(_: None = Depends(require_admin)):
    with event_lock:
        state.points = 0
        state.message = "Ready"
        state.last_event = None
        state.last_code = None
        state.last_ai = None
        state.last_rejection_reason = None
    if ai_pipeline is not None:
        ai_pipeline.tracker.reset()
    return {"ok": True, "message": "State reset", "points": state.points}


# -------------------- Config --------------------
class ConfigOut(BaseModel):
    ROI_CX: int
    ROI_CY: int
    ROI_R: int
    USE_MOG2: bool
    MOTION_PIXELS_THRESHOLD: int
    CONSEC_FRAMES_REQUIRED: int
    DETECT_COOLDOWN_S: float
    DIFF_THRESH: int
    BG_LEARN_RATE: float
    IDLE_RESET_SECONDS: float
    AI_ENABLED: bool
    AI_EXECUTION_PROVIDER: str
    AI_ALLOWED_OBJECT_LABELS: tuple[str, ...]
    AI_ALLOWED_PET_LABELS: tuple[str, ...]
    AI_MIN_ROI_SCORE: float
    AI_REQUIRED_POSITIVE_FRAMES: int
    AI_VOTE_WINDOW: int
    AI_MIN_TRACK_MOTION_PX: float
    ALLOW_MANUAL_EVENTS: bool


class SetRoiIn(BaseModel):
    cx: int
    cy: int
    r: int


@router.get("/config", response_model=ConfigOut)
def read_config():
    return ConfigOut(
        ROI_CX=settings.ROI_CX,
        ROI_CY=settings.ROI_CY,
        ROI_R=settings.ROI_R,
        USE_MOG2=settings.USE_MOG2,
        MOTION_PIXELS_THRESHOLD=settings.MOTION_PIXELS_THRESHOLD,
        CONSEC_FRAMES_REQUIRED=settings.CONSEC_FRAMES_REQUIRED,
        DETECT_COOLDOWN_S=settings.DETECT_COOLDOWN_S,
        DIFF_THRESH=settings.DIFF_THRESH,
        BG_LEARN_RATE=settings.BG_LEARN_RATE,
        IDLE_RESET_SECONDS=settings.IDLE_RESET_SECONDS,
        AI_ENABLED=settings.AI_ENABLED,
        AI_EXECUTION_PROVIDER=settings.AI_EXECUTION_PROVIDER,
        AI_ALLOWED_OBJECT_LABELS=settings.AI_ALLOWED_OBJECT_LABELS,
        AI_ALLOWED_PET_LABELS=settings.AI_ALLOWED_PET_LABELS,
        AI_MIN_ROI_SCORE=settings.AI_MIN_ROI_SCORE,
        AI_REQUIRED_POSITIVE_FRAMES=settings.AI_REQUIRED_POSITIVE_FRAMES,
        AI_VOTE_WINDOW=settings.AI_VOTE_WINDOW,
        AI_MIN_TRACK_MOTION_PX=settings.AI_MIN_TRACK_MOTION_PX,
        ALLOW_MANUAL_EVENTS=settings.ALLOW_MANUAL_EVENTS,
    )


@router.post("/config/roi", response_model=ConfigOut)
def set_roi(body: SetRoiIn, _: None = Depends(require_admin)):
    if body.r < 10 or body.r > min(settings.FRAME_W, settings.FRAME_H):
        raise HTTPException(status_code=422, detail="ROI radius is outside safe bounds")
    if not (0 <= body.cx < settings.FRAME_W and 0 <= body.cy < settings.FRAME_H):
        raise HTTPException(status_code=422, detail="ROI center is outside the configured frame")
    settings.ROI_CX = int(body.cx)
    settings.ROI_CY = int(body.cy)
    settings.ROI_R = int(body.r)
    if ai_pipeline is not None:
        ai_pipeline.update_roi((settings.ROI_CX, settings.ROI_CY), settings.ROI_R)
    return read_config()


@router.post("/reseed")
def reseed_background(_: None = Depends(require_admin)):
    ok, frame = detector.cap.read()
    if not ok:
        raise HTTPException(status_code=503, detail="Camera unavailable")
    g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(g, (21, 21), 0)
    detector.bg = g.copy()
    if settings.USE_MOG2:
        detector.mog2 = cv2.createBackgroundSubtractorMOG2(
            history=200, varThreshold=16, detectShadows=False
        )
    return {"ok": True}


# -------------------- Debug / Tooling --------------------
def generate_frames():
    while True:
        try:
            frame = detector.frame_buf[-1] if detector.frame_buf else None
            if frame is None:
                ok, frame = detector.cap.read()
                if not ok:
                    time.sleep(0.1)
                    continue

            ok, buffer = cv2.imencode(
                ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), settings.JPEG_QUALITY]
            )
            if not ok:
                time.sleep(0.1)
                continue

            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
            time.sleep(0.033)
        except Exception as exc:
            print(f"Stream error: {exc}")
            time.sleep(0.1)


@router.get("/stream")
def video_stream():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/frame.jpg")
def latest_frame():
    frame = detector.frame_buf[-1] if detector.frame_buf else None
    if frame is None:
        ok, frame = detector.cap.read()
        if not ok:
            raise HTTPException(status_code=503, detail="No frame")
    ok, buf = cv2.imencode(
        ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), settings.JPEG_QUALITY]
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Encode error")
    return Response(content=buf.tobytes(), media_type="image/jpeg")


@router.get("/frame/overlay.jpg")
def overlay_preview(_: None = Depends(require_admin)):
    ok, frame = detector.cap.read()
    if not ok:
        raise HTTPException(status_code=503, detail="No frame")
    cv2.circle(frame, (settings.ROI_CX, settings.ROI_CY), settings.ROI_R, (0, 255, 0), 2)
    detector._annotate_ai(frame)
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise HTTPException(status_code=500, detail="Encode error")
    return Response(content=buf.tobytes(), media_type="image/jpeg")


@router.get("/debug/binary.jpg")
def debug_binary(_: None = Depends(require_admin)):
    img = detector.debug_last_thresh
    if img is None:
        raise HTTPException(status_code=503, detail="No debug frame")
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise HTTPException(status_code=500, detail="Encode error")
    return Response(content=buf.tobytes(), media_type="image/jpeg")
