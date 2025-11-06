#!/bin/sh
set -e
echo "=== Nginx entrypoint: rendering config from template ==="
if [ "${ACTIVE_POOL}" = "blue" ]; then
  BLUE_ROLE='max_fails=1 fail_timeout=5s'
  GREEN_ROLE='backup'
else
  BLUE_ROLE='backup'
  GREEN_ROLE='max_fails=1 fail_timeout=5s'
fi

export BLUE_ROLE GREEN_ROLE

echo "Using roles: BLUE_ROLE='${BLUE_ROLE}' GREEN_ROLE='${GREEN_ROLE}'"
echo "Rendering /etc/nginx/nginx.conf ..."
envsubst '$BLUE_ROLE $GREEN_ROLE' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

echo "=== Rendered Nginx config ==="
cat /etc/nginx/nginx.conf
echo "=== Starting Nginx ==="

exec nginx -g 'daemon off;'
