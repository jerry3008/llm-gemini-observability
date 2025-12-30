# main.py
import os
import time
import uuid
import json
import logging
import threading
from typing import Optional
from collections import defaultdict, deque

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

import vertexai
from vertexai.generative_models import GenerativeModel

from datadog_emit import emit_metric, emit_log

# ----------------------------
# Config
# ----------------------------
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

APP_API_KEY = os.getenv("APP_API_KEY")  # set in Cloud Run env vars

SYSTEM_INSTRUCTION = os.getenv(
    "SYSTEM_INSTRUCTION",
    "You are dd-gemini-app: a production-style Gemini (Vertex AI) API demo for observability. "
    "Answer concisely and practically. If asked what you do, say you provide Gemini responses "
    "and return model + latency for monitoring. Do not claim to be 'trained by Google' or describe yourself as a generic LLM."
)

SLOW_MS = int(os.getenv("SLOW_MS", "0"))  # injected latency
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "256"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))

RATE_LIMIT_RPM = int(os.getenv("RATE_LIMIT_RPM", "30"))  # per IP, per minute

# ----------------------------
# Datadog metric names (NEW, count-safe)
# ----------------------------
# Use these for SLOs:
METRIC_REQUESTS_COUNT = "dd_gemini.slo_requests_count"
METRIC_SUCCESS_COUNT = "dd_gemini.slo_chat_success_count"
METRIC_ERROR_COUNT = "dd_gemini.slo_chat_error_count"

# Latency is for dashboards/monitors (not count-based SLO):
METRIC_LATENCY_MS = "dd_gemini.chat_latency_ms"

# ----------------------------
# Logging
# ----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dd-gemini-app")


def log_json(payload: dict) -> None:
    logger.info(json.dumps(payload, ensure_ascii=False))


# ----------------------------
# App
# ----------------------------
app = FastAPI()

_lock = threading.Lock()

TOTAL_REQUESTS = 0
TOTAL_ERRORS = 0
TOTAL_LATENCY_MS = 0

_ip_hits = defaultdict(deque)  # ip -> timestamps
_model: Optional[GenerativeModel] = None


def init_vertex_model() -> GenerativeModel:
    global _model
    if not GOOGLE_CLOUD_PROJECT:
        raise RuntimeError("Missing GOOGLE_CLOUD_PROJECT env var")

    if _model is None:
        vertexai.init(project=GOOGLE_CLOUD_PROJECT, location=GOOGLE_CLOUD_LOCATION)
        _model = GenerativeModel(GEMINI_MODEL, system_instruction=SYSTEM_INSTRUCTION)

    return _model


def rate_limit_ok(client_ip: str) -> bool:
    now = time.time()
    window_start = now - 60

    with _lock:
        q = _ip_hits[client_ip]
        while q and q[0] < window_start:
            q.popleft()

        if len(q) >= RATE_LIMIT_RPM:
            return False

        q.append(now)
        return True


class ChatRequest(BaseModel):
    message: str


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/metrics")
def metrics():
    with _lock:
        avg_latency = (TOTAL_LATENCY_MS / TOTAL_REQUESTS) if TOTAL_REQUESTS else 0
        return {
            "requests_total": TOTAL_REQUESTS,
            "errors_total": TOTAL_ERRORS,
            "avg_latency_ms": round(avg_latency, 2),
            "model": GEMINI_MODEL,
            "location": GOOGLE_CLOUD_LOCATION,
            "rate_limit_rpm": RATE_LIMIT_RPM,
        }


@app.on_event("startup")
def startup():
    if not GOOGLE_CLOUD_PROJECT:
        log_json({"event": "startup_warning", "warning": "Missing GOOGLE_CLOUD_PROJECT env var"})
        return
    try:
        init_vertex_model()
        log_json({"event": "startup_ok", "model": GEMINI_MODEL, "location": GOOGLE_CLOUD_LOCATION})
    except Exception as e:
        log_json({"event": "startup_error", "error_type": type(e).__name__, "error": str(e)})


@app.post("/chat")
def chat(
    req: ChatRequest,
    request: Request,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    global TOTAL_REQUESTS, TOTAL_ERRORS, TOTAL_LATENCY_MS

    request_id = str(uuid.uuid4())
    start = time.time()

    xff = request.headers.get("x-forwarded-for", "")
    client_ip = (xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown"))

    #  Total events for SLO (COUNT)
    emit_metric(METRIC_REQUESTS_COUNT, 1, tags=["endpoint:chat"], metric_type="count")

    try:
        # API key gate (401)
        if APP_API_KEY and (not x_api_key or x_api_key != APP_API_KEY):
            raise HTTPException(status_code=401, detail="Unauthorized: missing or invalid X-API-Key")

        # Rate limit (429)
        if not rate_limit_ok(client_ip):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        user_prompt = (req.message or "").strip()
        if not user_prompt:
            raise HTTPException(status_code=400, detail="message cannot be empty")

        # Force a server error (500) for monitor testing
        if user_prompt == "force_500":
            raise RuntimeError("Forced 500 for monitor test")

        with _lock:
            TOTAL_REQUESTS += 1

        model = init_vertex_model()
        resp = model.generate_content(
            user_prompt,
            generation_config={
                "max_output_tokens": MAX_OUTPUT_TOKENS,
                "temperature": TEMPERATURE,
            },
        )

        if SLOW_MS > 0:
            time.sleep(SLOW_MS / 1000)

        latency_ms = int((time.time() - start) * 1000)
        answer_text = getattr(resp, "text", None) or ""

        with _lock:
            TOTAL_LATENCY_MS += latency_ms

        #  Latency for dashboards/latency monitors (GAUGE)
        emit_metric(METRIC_LATENCY_MS, latency_ms, tags=["endpoint:chat", "status:ok"], metric_type="gauge")

        #  Good events for SLO (COUNT)
        emit_metric(METRIC_SUCCESS_COUNT, 1, tags=["endpoint:chat"], metric_type="count")

        emit_log(
            "chat_ok",
            "info",
            {
                "request_id": request_id,
                "latency_ms": latency_ms,
                "model": GEMINI_MODEL,
                "location": GOOGLE_CLOUD_LOCATION,
                "client_ip": client_ip,
            },
        )

        log_json(
            {
                "event": "chat_ok",
                "request_id": request_id,
                "latency_ms": latency_ms,
                "model": GEMINI_MODEL,
                "client_ip": client_ip,
            }
        )

        return {
            "request_id": request_id,
            "model": GEMINI_MODEL,
            "latency_ms": latency_ms,
            "answer": answer_text,
        }

    #  HTTPException path: 400/401/429 etc.
    except HTTPException as he:
        latency_ms = int((time.time() - start) * 1000)

        with _lock:
            TOTAL_LATENCY_MS += latency_ms
            TOTAL_ERRORS += 1

        # Latency (GAUGE)
        emit_metric(
            METRIC_LATENCY_MS,
            latency_ms,
            tags=["endpoint:chat", "status:error", f"code:{he.status_code}"],
            metric_type="gauge",
        )

        #  Bad events for SLO (COUNT)
        emit_metric(
            METRIC_ERROR_COUNT,
            1,
            tags=["endpoint:chat", f"code:{he.status_code}"],
            metric_type="count",
        )

        emit_log(
            "chat_http_error",
            "error",
            {
                "request_id": request_id,
                "latency_ms": latency_ms,
                "model": GEMINI_MODEL,
                "location": GOOGLE_CLOUD_LOCATION,
                "client_ip": client_ip,
                "http_status": he.status_code,
                "detail": str(he.detail),
            },
        )

        log_json(
            {
                "event": "chat_http_error",
                "request_id": request_id,
                "latency_ms": latency_ms,
                "http_status": he.status_code,
                "detail": he.detail,
            }
        )

        raise

    #  true 500 path
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)

        with _lock:
            TOTAL_LATENCY_MS += latency_ms
            TOTAL_ERRORS += 1

        # Latency (GAUGE)
        emit_metric(
            METRIC_LATENCY_MS,
            latency_ms,
            tags=["endpoint:chat", "status:error", "code:500"],
            metric_type="gauge",
        )

        # Bad events for SLO (COUNT)
        emit_metric(
            METRIC_ERROR_COUNT,
            1,
            tags=["endpoint:chat", f"error_type:{type(e).__name__}", "code:500"],
            metric_type="count",
        )

        emit_log(
            "chat_error",
            "error",
            {
                "request_id": request_id,
                "latency_ms": latency_ms,
                "model": GEMINI_MODEL,
                "location": GOOGLE_CLOUD_LOCATION,
                "client_ip": client_ip,
                "error_type": type(e).__name__,
                "error": str(e),
            },
        )

        log_json(
            {
                "event": "chat_error",
                "request_id": request_id,
                "latency_ms": latency_ms,
                "error_type": type(e).__name__,
                "error": str(e),
            }
        )

        raise HTTPException(status_code=500, detail=f"Internal error (request_id={request_id})")
