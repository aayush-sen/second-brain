#!/bin/sh
# Launch the Pierce dashboard: start serve.py if port 8877 is free, then open
# the browser. Desktop Pierce.app wraps this script — logic stays versioned here.
VAULT="$(cd "$(dirname "$0")/../.." && pwd)"
PORT=8877
if ! lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  cd "$VAULT" || exit 1
  nohup python3 os/dashboard/serve.py >/tmp/pierce-dashboard.log 2>&1 &
  # wait up to 10s for the port; bail loudly if it never comes up
  i=0
  while ! lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; do
    i=$((i + 1))
    [ $i -ge 40 ] && { echo "Pierce failed to start — see /tmp/pierce-dashboard.log" >&2; exit 1; }
    sleep 0.25
  done
fi
open "http://localhost:$PORT"
