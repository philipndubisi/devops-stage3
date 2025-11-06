Blue/Green Deployment with Observability - Stage 3

Overview

This project implements a Blue/Green deployment strategy with automated failover and real-time monitoring. It features:

- Zero-downtime failover between Blue and Green pools
- Real-time log monitoring via Python watcher service
- Slack alerts for failover events and high error rates
- Automated recovery detection
- Comprehensive observability through structured Nginx logs

 Architecture

┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Nginx (8080)   │ ◄──── Access Logs (structured)
│  Load Balancer  │
└────┬────────┬───┘
     │        │
     ▼        ▼
┌─────────┐ ┌─────────┐
│  Blue   │ │  Green  │
│ (8081)  │ │ (8082)  │
│ Primary │ │ Backup  │
└─────────┘ └─────────┘
     │
     ▼
┌──────────────────┐     ┌────────────┐
│  Alert Watcher   │────▶│   Slack    │
│  (Python)        │     │  Webhook   │
└──────────────────┘     └────────────┘

Prerequisites

- Docker Engine 20.10+
- Docker Compose 1.29+
- curl (for testing)
- jq (optional, for JSON parsing)
- Slack workspace with incoming webhook URL

Quick Start

1. Clone and Setup

git clone https://github.com/yourusername/blue-green-stage3.git
cd blue-green-stage3
cp .env.example .env
nano .env  # or vim, code, etc.

2. Configure Slack Webhook

1. Go to https://api.slack.com/apps
2. Create a new app or select existing
3. Enable "Incoming Webhooks"
4. Create a new webhook for your channel
5. Copy the webhook URL
6. Update `.env`:

SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/HERE

3. Start Services

docker-compose up -d
docker ps

Expected output:
nginx_proxy      - Running
app_blue         - Running
app_green        - Running
alert_watcher    - Running

4. Verify Setup

Check baseline (should show Blue)
curl http://localhost:8080/version

Testing Failover
Test 1: Trigger Failover

curl -X POST http://localhost:8081/chaos/start?mode=error
for i in {1..10}; do
  curl -s http://localhost:8080/version | jq -r '.pool'
  sleep 1
done

Test 2: Check Slack Alert

Within 5-10 seconds, you should receive a Slack alert:


Test 3: Verify Recovery

curl -X POST http://localhost:8081/chaos/stop
sleep 15

for i in {1..10}; do
  curl -s http://localhost:8080/version | jq -r '.pool'
  sleep 1
done

Viewing Logs
Nginx Access Logs (Structured)
docker logs nginx_proxy | tail -20

Alert Watcher Logs
docker logs alert_watcher

Application Logs
docker logs app_blue
docker logs app_green

Configuration
Environment Variables (.env)
BLUE_IMAGE=yimikaade/wonderful:devops-stage-two
GREEN_IMAGE=yimikaade/wonderful:devops-stage-two
ACTIVE_POOL=blue
RELEASE_ID_BLUE=blue-v1.0.0
RELEASE_ID_GREEN=green-v1.0.0

Slack Configuration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

Alert Thresholds
ERROR_RATE_THRESHOLD=2          # Percentage (%)
WINDOW_SIZE=200                 # Number of requests
ALERT_COOLDOWN_SEC=300         # Seconds between same alert type

Tuning for Your Environment

High-traffic sites (1000+ req/min):
WINDOW_SIZE=500
ERROR_RATE_THRESHOLD=1
ALERT_COOLDOWN_SEC=180

Low-traffic sites (< 100 req/min):
WINDOW_SIZE=100
ERROR_RATE_THRESHOLD=5
ALERT_COOLDOWN_SEC=600


Chaos Testing
The application exposes chaos endpoints for testing failover scenarios:

Available Chaos Modes
curl -X POST http://localhost:8081/chaos/start?mode=error
curl -X POST http://localhost:8081/chaos/start?mode=timeout
curl -X POST http://localhost:8081/chaos/stop

Chaos Testing Workflow

1. Baseline: Verify Blue is serving all traffic
2. Chaos Start: Trigger error/timeout on Blue
3. Observe: Watch automatic failover to Green
4. Monitor: Check Slack for failover alert
5. Chaos Stop: Stop chaos on Blue
6. Recovery: Observe automatic return to Blue
7. Verify: Confirm recovery alert in Slack

Project Structure
.
├── docker-compose.yml          # Service orchestration
├── Dockerfile.watcher          # Watcher container definition
├── nginx.conf.template         # Nginx configuration template
├── watcher.py                  # Python log monitoring script
├── requirements.txt            # Python dependencies
├── .env.example                # Environment template
├── .env                        # Your actual config (git-ignored)
├── test-stage3.sh             # Automated testing script
├── runbook.md                  # Operator response guide
└── README.md                   # This file

Failover Performance
- Detection time: < 5 seconds
- Failover time: < 2 seconds
- Zero 5xx responses during failover
- Alert latency: < 5 seconds
