# GreenAfrica RVM API

The RVM API is the edge service that runs with a GreenAfrica reverse vending machine. It handles camera capture, bottle-acceptance detection, QR/session events and the machine-facing API used by the rest of the platform.

The Python service itself is intentionally blockchain-neutral. After it verifies an accepted bottle session, the GreenAfrica backend submits the corresponding recycling record to the Algorand application.

## Stack

- FastAPI
- Uvicorn
- OpenCV
- NumPy
- WebSockets
- QR code generation

## Flow

```text
Camera
  |
  v
OpenCV detector
  |
  | accepted bottle
  v
RVM API event
  |
  +--> session / QR payload
  +--> optional evidence metadata
  |
  v
GreenAfrica backend
  |
  v
Algorand application
  |-- validates active RVM
  |-- rejects duplicate session ID
  |-- updates PET total
  |-- awards Green Points
  `-- emits audit event
```

## Local setup

```bash
cd rvm_api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Responsibilities

The RVM service is responsible for:

- camera and region-of-interest capture
- bottle-entry detection
- event timing and cooldown logic
- generating machine/session events
- exposing operator and diagnostic endpoints
- supplying the backend with the data needed to build an Algorand recycling receipt

It should not hold the GreenAfrica Algorand operator mnemonic. Blockchain signing stays in the server/backend layer rather than on a public machine or browser client.

## Algorand integration boundary

When an accepted session reaches the backend, the server uses the webapp Algorand client to call `recordDeposit` with:

- recycler Green ID
- RVM ID
- PET count
- Green Points awarded
- unique session ID
- hash of the evidence/receipt payload

The Algorand application is the authoritative blockchain record. Firebase can mirror the resulting balance and transaction ID for the user interface.
