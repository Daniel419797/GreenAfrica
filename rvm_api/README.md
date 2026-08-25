# GreenAfrica RVM API

The RVM API is the edge service that runs with a GreenAfrica reverse vending machine. It handles camera capture, production AI verification, QR/session events and the machine-facing API used by the rest of the platform.

The Python service is blockchain-neutral. Only after a bottle passes the AI acceptance policy does the backend receive an accepted recycling session and submit the corresponding record to Algorand.

## Production AI flow

```text
Camera
  |
  v
OpenCV motion pre-filter              <- compute trigger only; cannot award points
  |
  v
YOLO ONNX object detector
  |-- bottle
  |-- can
  |-- hand
  `-- other object
  |
  | bottle candidate in physical gate ROI
  v
ONNX material classifier
  |-- PET clear / PET coloured        <- accepted material classes
  |-- glass / HDPE / aluminum / other <- rejected
  |
  v
Temporal tracker
  |-- repeated positive frames
  |-- minimum physical motion
  `-- one acceptance per track
  |
  v
Verified PET event + model evidence
  |
  v
GreenAfrica backend
  |
  v
Algorand application
```

The previous motion-only detector is no longer authoritative. Motion merely wakes AI inference. Missing models, bad model hashes, inference errors, low confidence, non-PET material, insufficient temporal evidence and static detections all fail closed.

## Runtime stack

- FastAPI / Uvicorn
- OpenCV / NumPy
- ONNX Runtime
- YOLO-compatible ONNX object detection
- calibrated ONNX material classification
- deterministic temporal tracking and duplicate suppression
- WebSockets / QR generation

## Model security and versioning

Production reads `models/manifest.json`. The manifest pins:

- detector and classifier versions;
- exact class order;
- input size;
- calibrated confidence thresholds;
- detector IoU threshold;
- SHA-256 digest of each ONNX artifact.

The service verifies the files before loading them. Set `RVM_AI_FAIL_STARTUP_IF_UNAVAILABLE=true` in production to prevent the RVM from becoming ready when its model release is missing or invalid.

Training and release tooling lives in `training/`. It includes deterministic YOLO fine-tuning, a MobileNetV3 material classifier with imbalance handling and confidence calibration, held-out evaluation, ONNX export and immutable manifest generation. See `training/README.md`.

## Production environment

```text
RVM_AI_ENABLED=true
RVM_AI_FAIL_STARTUP_IF_UNAVAILABLE=true
RVM_AI_REQUIRE_MODEL_HASHES=true
RVM_AI_MODEL_MANIFEST=models/manifest.json
RVM_AI_EXECUTION_PROVIDER=auto
RVM_AI_ALLOWED_OBJECT_LABELS=bottle
RVM_AI_ALLOWED_PET_LABELS=pet_clear,pet_colored

RVM_AI_MIN_ROI_SCORE=0.30
RVM_AI_MIN_BOX_AREA_PX=1200
RVM_AI_REQUIRED_POSITIVE_FRAMES=4
RVM_AI_VOTE_WINDOW=6
RVM_AI_TRACK_TTL_SECONDS=1.5
RVM_AI_MIN_TRACK_MOTION_PX=10
RVM_AI_INFERENCE_MIN_INTERVAL_S=0.10

RVM_ALLOW_MANUAL_EVENTS=false
RVM_ADMIN_TOKEN=<strong random operator secret>
```

`auto` prefers TensorRT, then CUDA, then CPU when available.

## Operator/control security

The following write/debug operations require `X-RVM-Admin-Token` and a configured `RVM_ADMIN_TOKEN`:

- manual accept/reject;
- reset;
- ROI mutation;
- background reseed;
- raw debug/overlay image endpoints.

Manual accept/reject is additionally disabled unless `RVM_ALLOW_MANUAL_EVENTS=true`. Production should leave it false.

## Health endpoints

- `GET /health/live` — process liveness.
- `GET /health/ready` — camera + required AI readiness. Returns HTTP 503 when not ready.
- `GET /ai/status` — model versions, provider, inference counters and last decision.
- `GET /status` — kiosk/recycling state including last AI evidence.

## Recycling evidence

An accepted AI event includes evidence such as:

- object label and detector confidence;
- PET material label and classifier confidence;
- bounding box and ROI score;
- temporal positive-vote count;
- physical track motion;
- model/detector/classifier release versions;
- detector/classifier latency;
- track ID.

That evidence can be included in the existing receipt/media payload before the backend hashes it and calls Algorand `recordDeposit`.

## Local setup

```bash
cd rvm_api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Without a valid `models/manifest.json` and matching ONNX files, AI startup is marked unavailable and automatic recycling acceptance remains disabled. That is intentional; production code must never silently fall back to motion-only rewards.

## Algorand boundary

The RVM service must not hold the GreenAfrica Algorand operator mnemonic. Blockchain signing remains in the backend. After a verified session reaches the backend, the server calls `recordDeposit` with the recycler Green ID, RVM ID, PET count, Green Points, unique session ID and hash of the evidence/receipt payload.
