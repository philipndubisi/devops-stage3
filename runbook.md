Blue/Green Deployment Runbook - Stage 3

Overview
This runbook describes how to respond to alerts from the Blue/Green deployment monitoring system.

Alert Types

1. Failover Detected

Alert Message:

Failover Detected
Pool switched: blue → green
Time: 2025-11-02 14:30:45 UTC

Action Required:
• Check health of blue container
• Review logs: docker logs app_blue
• Monitor recovery status

What It Means:
The system detected that the active pool has changed. This indicates:
- The primary pool (usually Blue) has failed health checks
- Nginx automatically routed traffic to the backup pool (usually Green)
- The failover happened automatically with zero downtime

Operator Actions:

1. Investigate the failed pool immediately:
   docker ps -a | grep app_blue
   docker logs --tail 100 app_blue
   curl http://localhost:8081/healthz

2. Verify the backup pool is stable:
   docker logs --tail 20 alert_watcher
   
   for i in {1..10}; do 
     curl -s http://localhost:8080/version | jq -r '.pool'
   done


3. Determine root cause:
   - Application crash or OOM kill?
   - Network connectivity issue?
   - Chaos mode accidentally triggered?
   - Resource exhaustion (CPU/memory)?

4. Recovery options:

   Option A: Wait for auto-recovery (Recommended)
   - If Blue was temporarily unhealthy, it will auto-recover
   - Monitor watcher logs for "Recovery Detected" alert
   - Typical recovery time: 5-30 seconds after issue resolves

   Option B: Manual intervention
   docker restart app_blue
   curl -X POST http://localhost:8081/chaos/stop

   Option C: Keep Green active
   - If Blue has persistent issues, leave Green serving
   - Schedule maintenance window to fix Blue
   - Update ACTIVE_POOL in .env if needed for long-term

5. Post-incident:
   - Document root cause
   - Review metrics/logs for patterns
   - Consider application fixes if crash was code-related

Expected Timeline:
- Detection: < 5 seconds after failure
- Failover: < 2 seconds (automatic)
- Alert sent: < 5 seconds after failover
- Recovery: 5-30 seconds (if transient issue)


2. High Error Rate Detected

Alert Message:

High Error Rate Detected

Error Rate: 5.50% (threshold: 2%)
Errors: 11/200 requests
Window: last 200 requests
Pool distribution: green: 200

Action Required:
• Inspect upstream logs immediately
• Consider manual pool toggle if persistent
• Check application health endpoints


What It Means:
The system is experiencing an elevated rate of 5xx errors over the sliding window. This could indicate:
- Degraded performance in the active pool
- Intermittent application issues
- Database/backend service problems
- Resource constraints

Operator Actions:

1. Assess severity:
   docker logs alert_watcher | tail -50
   docker logs nginx_proxy | grep "50[0-9]" | tail -20


2. Investigate the active pool:
   ACTIVE=$(curl -s http://localhost:8080/version | jq -r '.pool')
   docker logs --tail 100 app_$ACTIVE
   docker stats --no-stream app_$ACTIVE
   ```

3. Check dependencies:
   - Database connectivity?
   - External API availability?
   - Network issues?

4. Immediate mitigation options:

   Option A: Toggle to backup pool (if errors are pool-specific)
   
   echo "ACTIVE_POOL=green" >> .env
   docker-compose up -d --force-recreate nginx
   
   Option B: Restart the problematic container
   docker restart app_$ACTIVE
   
   Option C: Scale down traffic
   - If external, consider rate limiting
   - If internal, investigate load patterns

5. Monitor recovery:
   docker logs -f alert_watcher
   
   for i in {1..20}; do
     curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/version
     sleep 0.5
   done

   Expected Timeline:
- Detection: Within 200 requests (~30-60 seconds)
- Alert sent: Immediate after threshold breach
- Investigation: 2-5 minutes
- Resolution: Varies by root cause

3. Recovery Detected

Alert Message: Recovery Detected

Primary pool blue is back online
Time: 2025-11-02 14:35:20 UTC

System has auto-recovered to normal state.

What It Means:
The primary pool has recovered and is now serving traffic again.

Operator Actions:

1. Verify stability:
   for i in {1..20}; do
     curl -s http://localhost:8080/version | jq -r '.pool'
   done
   
2. Review incident:
   - Check what caused the initial failure
   - Review recovery duration
   - Document any findings

3. No immediate action required - system is healthy
   - Continue monitoring for recurring issues
   - Consider post-mortem if downtime was significant

If you need to perform planned maintenance (e.g., intentional pool toggle), you can temporarily disable alerts:

Method 1: Pause the watcher
docker stop alert_watcher
docker start alert_watcher

Method 2: Set very high cooldown

In .env
ALERT_COOLDOWN_SEC=3600

docker-compose up -d alert_watcher

Slack Alert Configuration

Testing Slack Integration
grep SLACK_WEBHOOK_URL .env
curl -X POST http://localhost:8081/chaos/start?mode=error
curl -X POST http://localhost:8081/chaos/stop
