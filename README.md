# LLM Gemini — Production Observability with Datadog

Production-grade observability for a Gemini-powered LLM service running on Google Cloud (Cloud Run), with Datadog dashboards, SLOs, monitors, and incident workflows.

## What this project does
- Exposes an LLM chat endpoint (`/chat`) powered by **Google Cloud Vertex AI (Gemini)**
- Emits key telemetry to **Datadog** (request rate, success/errors, latency)
- Visualizes application health in Datadog dashboards
- Defines detection rules (Monitors + SLO alerts)
- Automatically creates actionable items (Incidents) on SLO breach
- Includes a traffic generator to trigger signals and demonstrate alerts

## Architecture (high level)
Cloud Run app → Gemini (Vertex AI) → custom metrics sent to Datadog → dashboards & SLOs → monitors → incident creation on breach

---

## Tech Stack
- Google Cloud Run
- Vertex AI (Gemini)
- Datadog (Metrics, Dashboards, SLOs, Monitors, Incidents)
- Python

---

## Repository structure
```text
.
├── main.py
├── datadog_emit.py
├── traffic_gen.py
├── requirements.txt
├── Dockerfile
├── LICENSE
├── .env.example
├── exports/            # Datadog JSON exports (dashboards, SLOs, monitors)
└── evidence/
    └── screenshots/   # Dashboard, SLO, monitor, and incident screenshots
Prerequisites
Python 3.10+

Datadog API key and Application key

Google Cloud project with Vertex AI / Gemini enabled

(Optional) gcloud CLI for Cloud Run deployment

Environment variables
Create a local .env file (do not commit it). Example values are provided in .env.example.

Common variables:

DD_API_KEY — Datadog API key

DD_APP_KEY — Datadog Application key (used for API exports)

DD_SITE — e.g. us5.datadoghq.com

DD_SERVICE — dd-gemini-app

GCP_PROJECT_ID — Google Cloud project ID

GEMINI_MODEL — e.g. gemini-1.5-pro

Note: Secrets are intentionally masked in screenshots and videos.

Run locally

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
Test the endpoint:


curl http://localhost:8080/chat
Traffic generator (trigger monitors)
Use this script to generate load and demonstrate SLO breaches and incidents:


python traffic_gen.py --url https://YOUR_CLOUD_RUN_URL
Deploy to Cloud Run (high-level)
Build and containerize the app (Dockerfile)

Deploy to Cloud Run

Verify /chat endpoint is publicly reachable

Run traffic_gen.py to generate traffic and validate alerts

Datadog configuration exports
Datadog configurations used in this project are included in exports/:

Dashboards (JSON)

SLOs (JSON)

Monitors (JSON)

These exports are provided for reproducibility and Devpost judging.

Evidence (screenshots)
See evidence/screenshots/ for:

Application health dashboard

SLO health and error budget status

Monitor triggering

Incident creation with context

License
MIT License — see LICENSE.

