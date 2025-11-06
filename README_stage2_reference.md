DevOps Stage 2 - Blue/Green Deployment with Nginx

This project implements a Blue/Green deployment strategy using Nginx as a reverse proxy with automatic failover capabilities.

Architecture

- Nginx: Reverse proxy with upstream failover configuration
- Blue Service: Primary application instance (port 8081)
- Green Service: Backup application instance (port 8082)
- Public Endpoint: http://localhost:8080

Prerequisites

- Docker
- Docker Compose

Setup Instructions

1. Clone this repository
2. Create a `.env` file with your image configuration
3. Start the services:
```bash
docker-compose up -d
```

4. Verify deployment:
```bash
curl http://localhost:8080/version
```

Testing Failover

Run the test script:
```bash
chmod +x test-failover.sh
./test-failover.sh
```

Or manually:

1. Check current active pool:
```bash
curl -I http://localhost:8080/version
```

2. Induce failure on Blue:
```bash
curl -X POST http://localhost:8081/chaos/start?mode=error
```

3. Verify automatic failover to Green:
```bash
curl -I http://localhost:8080/version
```

4. Stop chaos:
```bash
curl -X POST http://localhost:8081/chaos/stop
```

Configuration

All configuration is managed through environment variables in the `.env` file:

- `BLUE_IMAGE`: Docker image for Blue service
- `GREEN_IMAGE`: Docker image for Green service
- `ACTIVE_POOL`: Currently active pool (blue/green)
- `RELEASE_ID_BLUE`: Release identifier for Blue
- `RELEASE_ID_GREEN`: Release identifier for Green

Endpoints

- `GET /version` - Returns version info with headers
- `GET /healthz` - Health check endpoint
- `POST /chaos/start?mode=error` - Simulate downtime
- `POST /chaos/stop` - End simulated downtime

Stopping Services
```bash
docker-compose down
```

Logs

View logs for specific services:
```bash
docker-compose logs nginx
docker-compose logs app_blue
docker-compose logs app_green
```