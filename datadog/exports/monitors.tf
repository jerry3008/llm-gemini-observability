resource "datadog_monitor" "LLM_Latency_Degradation_Detected" {
    name = "LLM Latency Degradation Detected"
    type = "query alert"
  
    query = <<EOT
  max(last_5m):max:dd_gemini.latency_ms{service:dd-gemini-app} > 3000
  EOT
  
    message = <<EOT
  Service: {{service.name}}
  Metric: Gemini response latency
  Current value: {{value}} ms
  Threshold: {{threshold}} ms
  
  Impact:
  - Users may experience slow or stalled AI responses
  - Potential upstream Vertex AI / model saturation
  
  Next actions:
  1. Check Datadog latency graph
  2. Correlate with error rate + traffic
  3. Inspect recent logs for slow prompts or model delays
  EOT
  
    tags             = ["service:dd-gemini-app", "signal:latency", "team:ai"]
    draft_status     = "published"
    include_tags     = false
    on_missing_data  = "default"
    require_full_window = false
  
    monitor_thresholds {
      critical = 3000
      warning  = 2000
    }
  }
  
  resource "datadog_monitor" "LLM_Error_Detected" {
    name = "LLM Error Detected"
    type = "query alert"
  
    query = <<EOT
  avg(last_5m):sum:dd_gemini.chat_error_total{service:dd-gemini-app} by {service} >= 1
  EOT
  
    message = <<EOT
  Service: {{service.name}}
  Errors in last 5 minutes: {{value}}
  
  This indicates authentication issues, rate limiting, or Gemini failures.
  
  Next actions:
  1. Check application and Gemini error logs in Datadog
  2. Correlate with latency and traffic on the LLM dashboard
  3. Inspect request_id and recent deployments for debugging
  
  @team-ai
  EOT
  
    tags             = ["signal:error", "service:dd-gemini-app", "team:ai"]
    draft_status     = "published"
    new_group_delay  = 60
    on_missing_data  = "default"
    require_full_window = false
  
    monitor_thresholds {
      critical = 1
    }
  }
  
  resource "datadog_monitor" "LLM_Traffic_Stopped" {
    name = "LLM Traffic Stopped"
    type = "query alert"
  
    query = <<EOT
  sum(last_5m):sum:dd_gemini.requests_total{service:dd-gemini-app} < 1
  EOT
  
    message = <<EOT
  Service: {{service.name}}
  
  No /chat requests received in the last 5 minutes.
  
  Possible causes:
  - Cloud Run service crashed
  - Bad deployment
  - Auth misconfiguration
  - Gemini / Vertex outage
  
  Action:
  1. Check Cloud Run status
  2. Inspect recent deploys
  3. Review Datadog logs for startup errors
  
  @team-ai
  EOT
  
    tags             = ["service:dd-gemini-app", "signal:availability", "team:ai"]
    draft_status     = "published"
    include_tags     = false
    on_missing_data  = "default"
    require_full_window = false
  
    monitor_thresholds {
      critical = 1
    }
  }
  
  resource "datadog_monitor" "Fast_burn_real_time" {
    name = "Fast burn (real-time)"
    type = "slo alert"
  
    query = <<EOT
  burn_rate("2c152404070c5185a3af343695e9cb53").over("7d").long_window("1h").short_window("5m") > 5
  EOT
  
    message = <<EOT
  {{#is_alert}}
  FAST ERROR BUDGET BURN
  
  Service: dd-gemini-app
  SLO: Gemini Chat Success Rate (7d)
  Burn rate exceeded 5x over 1h / 5m window
  
  This means we are consuming our error budget too quickly
  and risk violating the 7-day SLO.
  
  Immediate actions:
  1) Check Cloud Run logs for errors (4xx/5xx)
  2) Verify Gemini / Vertex AI availability
  3) Roll back recent changes if any
  {{/is_alert}}
  
  {{#is_warning}}
  Elevated error budget burn detected (>=2x)
  
  Service is degrading. Investigate before escalation.
  {{/is_warning}}
  
  {{#is_recovery}}
  Burn rate back to normal.
  Service health has stabilized.
  {{/is_recovery}}
  EOT
  
    tags             = ["team:ai", "signal:burn-rate", "slo:gemini-chat"]
    priority         = 2
    draft_status     = "published"
    require_full_window = false
  
    monitor_thresholds {
      critical = 5
      warning  = 2
    }
  }
  
  resource "datadog_monitor" "LLM_Gemini_Chat_Success_Rate_SLO_Burn_Rate_Alert" {
    name = "LLM Gemini Chat Success Rate - SLO Burn Rate Alert"
    type = "slo alert"
  
    query = <<EOT
  burn_rate("8cdf6790e65456498547a4cedaa0db30").over("7d").long_window("1h").short_window("5m") > 14
  EOT
  
    message = <<EOT
  @incident- LLM Reliability Alert - Error Budget Burning Fast
  
  The LLM Gemini Chat Success Rate SLO is consuming error budget too quickly.
  
  What this means:
  - Chat responses are failing at an abnormal rate
  - User experience is impacted
  - Error budget exhaustion is imminent
  
  Context:
  - Service: dd-gemini-app
  - Endpoint: /chat
  - SLO Window: 7 days
  - Burn Rate Threshold: >14
  
  Immediate Actions:
  1. Inspect Gemini / Vertex AI error responses
  2. Review latency and request failures in the LLM dashboard
  3. Check recent deployments or config changes
  EOT
  
    tags             = ["team:ai", "service:dd-gemini-app"]
    draft_status     = "published"
    require_full_window = false
  
    monitor_thresholds {
      critical = 14
      warning  = 7
    }
  }
  
  resource "datadog_monitor" "SLO_BREACHED_Gemini_Chat_Success_Rate" {
    name = "SLO BREACHED - Gemini Chat Success Rate"
    type = "slo alert"
  
    query = <<EOT
  error_budget("8cdf6790e65456498547a4cedaa0db30").over("7d") > 100
  EOT
  
    message = <<EOT
  SLO BREACHED - Gemini Chat Success Rate
  
  The LLM Gemini Chat Success Rate SLO has breached its error budget.
  
  Impact:
  - User-facing reliability degradation
  - Requires immediate investigation
  
  Next steps:
  1. Check Gemini API errors
  2. Review latency and dependency health
  3. Escalate if breach persists
  
  @pagerduty @slack-llm-alerts
  EOT
  
    tags             = ["team:ai"]
    draft_status     = "published"
    require_full_window = false
  
    monitor_thresholds {
      critical = 100
      warning  = 80
    }
  }
  
  resource "datadog_monitor" "LLMSLOLatency_Gemini_Chat_Latency_Budget_Burn_Breach" {
    name = "LLM SLO Latency - Gemini Chat Latency Budget Burn Breach"
    type = "slo alert"
  
    query = <<EOT
  error_budget("2d00494260005f03813f3ea017f678a0").over("7d") > 100
  EOT
  
    message = <<EOT
  SLO ALERT - Gemini Chat Latency
  
  The Gemini Chat Latency SLO (avg <= 1200ms) has consumed a critical portion
  of its error budget.
  
  What this means:
  - User-facing latency is exceeding acceptable thresholds
  - Risk of SLO breach and degraded chat experience
  - Immediate investigation is required
  
  Recommended actions:
  1. Check recent latency trends on the LLM Observability dashboard
  2. Review upstream dependencies and Gemini API response times
  3. Validate traffic spikes or model performance regressions
  4. Escalate if latency remains elevated
  
  This alert is SLO-based and reflects customer impact, not just raw metrics.
  @incident-
  EOT
  
    tags             = ["service:dd-gemini-app", "slo:latency", "llm:gemini"]
    draft_status     = "published"
    require_full_window = false
  
    monitor_thresholds {
      critical = 100
      warning  = 80
    }
  }