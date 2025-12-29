# datadog_emit.py
import os
import json
import time
import urllib.request
import urllib.error
from typing import Optional, List, Dict, Any

DD_API_KEY = os.getenv("DD_API_KEY")
DD_SITE = os.getenv("DD_SITE", "us5.datadoghq.com")  # e.g. us5.datadoghq.com
DD_ENV = os.getenv("DD_ENV", "prod")
DD_SERVICE = os.getenv("DD_SERVICE", "dd-gemini-app")

API_BASE = f"https://api.{DD_SITE.replace('https://','').replace('http://','')}".rstrip("/")


def _post_json(url: str, payload: Any, headers: Dict[str, str]) -> None:
    if not DD_API_KEY:
        return

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)

    try:
        urllib.request.urlopen(req, timeout=5).read()
    except urllib.error.HTTPError as e:
        _ = e.read()
    except Exception:
        pass


def emit_log(message: str, status: str = "info", extra: Optional[Dict[str, Any]] = None) -> None:
    if not DD_API_KEY:
        return

    body = [{
        "message": message,
        "ddsource": "python",
        "service": DD_SERVICE,
        "status": status,
        "ddtags": f"env:{DD_ENV},service:{DD_SERVICE}",
        **(extra or {}),
    }]

    headers = {"Content-Type": "application/json", "DD-API-KEY": DD_API_KEY}
    _post_json(f"{API_BASE}/api/v2/logs", body, headers)


def emit_metric(
    name: str,
    value: float,
    tags: Optional[List[str]] = None,
    metric_type: str = "gauge",  # "gauge" | "count" | "rate"
) -> None:
    if not DD_API_KEY:
        return

    ts = int(time.time())
    payload = {
        "series": [{
            "metric": name,
            "points": [[ts, float(value)]],
            "type": metric_type,
            "tags": (tags or []) + [f"env:{DD_ENV}", f"service:{DD_SERVICE}"],
        }]
    }

    headers = {"Content-Type": "application/json", "DD-API-KEY": DD_API_KEY}
    _post_json(f"{API_BASE}/api/v1/series", payload, headers)
