from prometheus_client import Counter, Gauge, Histogram

AI_READY = Gauge(
    "greenafrica_rvm_ai_ready",
    "Whether the RVM AI model stack is initialized and ready",
)
AI_INFERENCES = Counter(
    "greenafrica_rvm_ai_inferences_total",
    "AI decisions by result",
    ["reason", "accepted"],
)
AI_ACCEPTS = Counter(
    "greenafrica_rvm_ai_accepts_total",
    "Verified PET acceptances emitted by the AI pipeline",
    ["material"],
)
AI_DETECTOR_LATENCY = Histogram(
    "greenafrica_rvm_ai_detector_latency_seconds",
    "YOLO detector inference latency",
    buckets=(0.005, 0.01, 0.02, 0.04, 0.08, 0.12, 0.2, 0.4, 0.8, 1.5),
)
AI_CLASSIFIER_LATENCY = Histogram(
    "greenafrica_rvm_ai_classifier_latency_seconds",
    "Material classifier inference latency",
    buckets=(0.002, 0.005, 0.01, 0.02, 0.04, 0.08, 0.15, 0.3, 0.6),
)
AI_ACCEPT_CONFIDENCE = Histogram(
    "greenafrica_rvm_ai_accept_confidence",
    "Mean temporal PET confidence for accepted tracks",
    buckets=(0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.93, 0.95, 0.97, 0.99, 1.0),
)


def set_ready(ready: bool) -> None:
    AI_READY.set(1 if ready else 0)


def record_decision(*, reason: str, accepted: bool) -> None:
    AI_INFERENCES.labels(reason=reason, accepted=str(bool(accepted)).lower()).inc()


def record_accept(material: str, confidence: float) -> None:
    AI_ACCEPTS.labels(material=material or "unknown").inc()
    AI_ACCEPT_CONFIDENCE.observe(max(0.0, min(1.0, float(confidence))))


def observe_detector_ms(milliseconds: float) -> None:
    AI_DETECTOR_LATENCY.observe(max(0.0, float(milliseconds)) / 1000.0)


def observe_classifier_ms(milliseconds: float) -> None:
    AI_CLASSIFIER_LATENCY.observe(max(0.0, float(milliseconds)) / 1000.0)
