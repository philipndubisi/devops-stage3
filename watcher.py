#!/usr/bin/env python3
"""
Nginx Log Watcher - Stage 3
Monitors Nginx container logs via Docker and sends Slack alerts.
"""

import os
import re
import time
import subprocess
import requests
from collections import deque
from datetime import datetime

# Configuration from environment variables
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')
ACTIVE_POOL = os.getenv('ACTIVE_POOL', 'blue')
ERROR_RATE_THRESHOLD = float(os.getenv('ERROR_RATE_THRESHOLD', '2'))
WINDOW_SIZE = int(os.getenv('WINDOW_SIZE', '200'))
ALERT_COOLDOWN_SEC = int(os.getenv('ALERT_COOLDOWN_SEC', '300'))

# State tracking
last_pool = ACTIVE_POOL
request_window = deque(maxlen=WINDOW_SIZE)
last_alert_time = {'failover': 0, 'error_rate': 0, 'recovery': 0}
failover_active = False

MIN_SAMPLES = max(50, WINDOW_SIZE // 4)


def now_iso():
    return datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')


def send_slack_alert(message, alert_type):
    """Send alert to Slack with cooldown to prevent spam."""
    current_time = time.time()
    last_time = last_alert_time.get(alert_type, 0)
    elapsed = current_time - last_time

    if elapsed < ALERT_COOLDOWN_SEC:
        remaining = int(ALERT_COOLDOWN_SEC - elapsed)
        print(f"[COOLDOWN] Skipping {alert_type} alert (next allowed in {remaining}s)", flush=True)
        return

    # If webhook is not configured, print the alert and update the cooldown timestamp
    if not SLACK_WEBHOOK_URL or SLACK_WEBHOOK_URL.strip().endswith('/YOUR/WEBHOOK/URL'):
        print(f"[WARNING] No valid Slack webhook configured; printing alert instead:", flush=True)
        print(f"[ALERT] {alert_type.upper()} - {message}", flush=True)
        last_alert_time[alert_type] = current_time
        return

    emoji_map = {
        'failover': ':warning:',
        'error_rate': ':rotating_light:',
        'recovery': ':white_check_mark:'
    }

    payload = {
        "text": f"{emoji_map.get(alert_type, ':bell:')} *Blue/Green Alert*\n\n{message}",
        "username": os.getenv("WATCHER_NAME", "DevOps Watcher - Stage 3 watcher"),
        "icon_emoji": emoji_map.get(alert_type, ':bell:')
    }

    try:
        resp = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=5)
        if resp.status_code == 200:
            print(f"✅ [SLACK ALERT SENT] {alert_type.upper()} at {now_iso()}", flush=True)
            last_alert_time[alert_type] = current_time
        else:
            print(f"❌ [SLACK ERROR] status={resp.status_code} body={resp.text}", flush=True)
    except requests.exceptions.Timeout:
        print("❌ [SLACK ERROR] webhook timeout", flush=True)
    except Exception as exc:
        print(f"❌ [SLACK ERROR] {exc}", flush=True)


def parse_log_line(line):
    """Extract pool and status from Nginx log line"""
    pool_match = re.search(r'pool=(\w+|-)', line)
    upstream_status_match = re.search(r'upstream_status=([0-9, -]+)', line)
    status_match = re.search(r'"[^"]*"\s+(\d+)\s+', line)

    if pool_match and status_match:
        pool = pool_match.group(1)
        final_status = int(status_match.group(1))

        upstream_status = None
        if upstream_status_match:
            statuses = upstream_status_match.group(1).split(',')
            for s in reversed(statuses):
                s = s.strip()
                if s and s != '-' and s.isdigit():
                    upstream_status = int(s)
                    break

        if pool == '-':
            return None

        return {
            'pool': pool,
            'status': final_status,
            'upstream_status': upstream_status,
            'timestamp': datetime.utcnow()
        }
    return None


def check_failover(current_pool):
    """Detect if pool has changed and send failover/recovery alerts."""
    global last_pool, failover_active

    if current_pool != last_pool:
        old_pool = last_pool
        last_pool = current_pool
        failover_active = True

        message = (
            f"*Failover Detected* :warning:\n\n"
            f"Pool switched: `{old_pool}` → `{current_pool}`\n"
            f"Time: {now_iso()}\n\n"
            f"*Action Required:*\n"
            f"• Check health of `{old_pool}` container\n"
            f"• Review logs: `docker logs app_{old_pool}`\n"
            f"• Monitor recovery status"
        )
        send_slack_alert(message, 'failover')
        return True

    if failover_active and current_pool == ACTIVE_POOL:
        failover_active = False
        message = (
            f"*Recovery Detected* :white_check_mark:\n\n"
            f"Primary pool `{ACTIVE_POOL}` is back online\n"
            f"Time: {now_iso()}\n\n"
            f"System has auto-recovered to normal state."
        )
        send_slack_alert(message, 'recovery')

    return False


def check_error_rate():
    """Calculate error rate over sliding window and send alert if threshold exceeded."""
    if len(request_window) < MIN_SAMPLES:
        return

    total = len(request_window)
    errors = sum(1 for req in request_window if req['status'] >= 500)
    error_rate = (errors / total) * 100 if total > 0 else 0.0

    if error_rate > ERROR_RATE_THRESHOLD:
        pool_counts = {}
        for req in request_window:
            pool_counts[req['pool']] = pool_counts.get(req['pool'], 0) + 1
        pool_info = ', '.join([f"{p}: {c}" for p, c in pool_counts.items()])

        message = (
            f"*High Error Rate Detected* :rotating_light:\n\n"
            f"📊 Error Rate: `{error_rate:.2f}%` (threshold: {ERROR_RATE_THRESHOLD}%)\n"
            f"❌ Errors: {errors}/{total} requests\n"
            f"📈 Window: last {total} requests\n"
            f"🔵 Pool distribution: {pool_info}\n\n"
            f"*Action Required:*\n"
            f"• Inspect upstream logs immediately\n"
            f"• Consider manual pool toggle if persistent\n"
            f"• Check application health endpoints"
        )
        send_slack_alert(message, 'error_rate')


def wait_for_nginx(timeout=60):
    """Wait until 'nginx_proxy' container is running."""
    print("⏳ Waiting for nginx container to be running...", flush=True)
    for i in range(timeout):
        try:
            res = subprocess.run(
                ['docker', 'inspect', '-f', '{{.State.Running}}', 'nginx_proxy'],
                capture_output=True, text=True, timeout=2
            )
            if res.returncode == 0 and 'true' in res.stdout.lower():
                print("✅ Nginx container is running!", flush=True)
                time.sleep(1)
                return True
        except Exception:
            pass
        time.sleep(1)
    print("❌ Timeout waiting for nginx container", flush=True)
    return False


def watch_docker_logs():
    """Stream `docker logs -f nginx_proxy` and process access lines."""
    print("=" * 70, flush=True)
    print("🔍 NGINX LOG WATCHER STARTED - STAGE 3", flush=True)
    print("=" * 70, flush=True)
    print(f"🔵 Initial Active Pool: {ACTIVE_POOL}", flush=True)
    print(f"📊 Error Threshold: {ERROR_RATE_THRESHOLD}%", flush=True)
    print(f"📈 Window Size: {WINDOW_SIZE} requests", flush=True)
    print(f"⏰ Alert Cooldown: {ALERT_COOLDOWN_SEC}s", flush=True)
    if SLACK_WEBHOOK_URL and not SLACK_WEBHOOK_URL.strip().endswith('/YOUR/WEBHOOK/URL'):
        print("💬 Slack Webhook: Configured ✅", flush=True)
    else:
        print("💬 Slack Webhook: Not configured ⚠️ (alerts will print to console)", flush=True)
    print("=" * 70, flush=True)
    print("", flush=True)

    if not wait_for_nginx(timeout=60):
        return

    try:
        proc = subprocess.Popen(
            ['docker', 'logs', '-f', '--tail', '0', 'nginx_proxy'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
    except Exception as e:
        print(f"❌ Failed to start docker logs: {e}", flush=True)
        return

    try:
        for raw_line in iter(proc.stdout.readline, ''):
            if not raw_line:
                time.sleep(0.01)
                continue
            line = raw_line.strip()
            if not line or 'pool=' not in line:
                continue

            data = parse_log_line(line)
            if not data:
                continue

            status_icon = "✅" if data['status'] < 400 else "⚠️" if data['status'] < 500 else "❌"
            upstream_info = f" (upstream: {data['upstream_status']})" if data['upstream_status'] else ""
            print(f"{status_icon} Request: pool={data['pool']} status={data['status']}{upstream_info}", flush=True)

            request_window.append(data)

            # Check for events
            check_failover(data['pool'])
            check_error_rate()

            # small sleep to avoid busy spin
            time.sleep(0.005)

    except KeyboardInterrupt:
        print("\n🛑 Received interrupt signal", flush=True)
        proc.terminate()
    except Exception as exc:
        print(f"\n❌ Error in log processing: {exc}", flush=True)
        import traceback
        traceback.print_exc()
        proc.terminate()
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


if __name__ == '__main__':
    try:
        watch_docker_logs()
    except KeyboardInterrupt:
        print("\n\n🛑 Watcher stopped by user", flush=True)
    except Exception as exc:
        print(f"\n\n❌ Watcher crashed: {exc}", flush=True)
        import traceback
        traceback.print_exc()
        raise
