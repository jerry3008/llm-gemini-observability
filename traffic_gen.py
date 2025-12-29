"""
Traffic generator for Datadog demo:
- 70% success
- 15% errors
- 15% slow requests
Duration: 3 minutes
"""

import os
import time
import json
import random
import urllib.request
import urllib.error

APP_URL = os.getenv("APP_URL")
APP_API_KEY = os.getenv("APP_API_KEY")

if not APP_URL:
    raise SystemExit("Missing APP_URL env var (example: set APP_URL=https://...a.run.app)")
if not APP_API_KEY:
    raise SystemExit("Missing APP_API_KEY env var (example: set APP_API_KEY=mysecret@123)")

def post_chat(payload: dict):
    url = APP_URL.rstrip("/") + "/chat"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-API-Key", APP_API_KEY)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")

messages = [
    "hello observability",
    "give me a checklist for debugging latency",
    "summarize what this app does in one sentence",
    "what are 3 common causes of 500 errors",
]

print("Starting traffic generator (success + error + slow)...")

start = time.time()
DURATION_SECONDS = 180  # 3 minutes

while time.time() - start < DURATION_SECONDS:
    mode = random.random()

    try:
        if mode < 0.7:
            # SUCCESS (70%)
            payload = {"message": random.choice(messages)}
            print("[CHAT][SUCCESS]", post_chat(payload)[:200])

        elif mode < 0.85:
            # ERROR (15%) – invalid payload
            payload = {}  # missing required field
            print("[CHAT][ERROR]", post_chat(payload)[:200])

        else:
            # SLOW (15%) – hint for slow processing
            payload = {
                "message": "simulate slow request",
                "slow": True
            }
            print("[CHAT][SLOW]", post_chat(payload)[:200])

    except urllib.error.HTTPError as e:
        print("[HTTP ERROR]", e.code, e.read().decode("utf-8")[:200])
    except Exception as e:
        print("[EXCEPTION]", e)

    time.sleep(2)

print("Traffic run completed.")
