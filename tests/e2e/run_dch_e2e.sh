#!/usr/bin/env bash
# End-to-end: real Chromium + real extension + native host + CLI + worker, with a FAKE site and FAKE token.
# Needs: node + playwright, Xvfb (xvfb-run), python deps. Not part of the default pytest run.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
WORK="$(mktemp -d)"
trap 'touch "$WORK/done"; sleep 1; rm -rf "$WORK"' EXIT
export YTDLP_DCH_STATE="$WORK/state" YTDLP_DCH_OUTPUT="$WORK/out" PYTHONPATH="$ROOT/src"
EXT_ID="$(python -c 'import ytdlp_tool.dch_host as h; print(h.EXTENSION_ID)')"
FAKE_TOKEN="$(python - <<PY
import sys; sys.path.insert(0, "$ROOT/tests")
from test_dch import make_token; print(make_token())
PY
)"
mkdir -p "$WORK/profile/NativeMessagingHosts"
cat > "$WORK/host.sh" <<SH
#!/usr/bin/env bash
exec python -m ytdlp_tool.dch_host "\$@"
SH
chmod +x "$WORK/host.sh"
cat > "$WORK/profile/NativeMessagingHosts/com.ytdlp_tool.dch.json" <<JSON
{"name":"com.ytdlp_tool.dch","description":"e2e","path":"$WORK/host.sh","type":"stdio",
 "allowed_origins":["chrome-extension://$EXT_ID/"]}
JSON
xvfb-run -a node "$ROOT/tests/e2e/dch_extension_e2e.js" "$ROOT/extensions/dch-bridge" "$WORK/profile" \
  "$WORK/ready" "$WORK/done" "$FAKE_TOKEN" > "$WORK/browser.log" 2>&1 &
for _ in $(seq 1 80); do [ -f "$WORK/ready" ] && break; sleep 0.5; done
[ -f "$WORK/ready" ] || { echo "FAIL: browser not ready"; cat "$WORK/browser.log"; exit 1; }
for _ in $(seq 1 40); do [ -f "$YTDLP_DCH_STATE/dch-bridge.json" ] && break; sleep 0.5; done
[ -f "$YTDLP_DCH_STATE/dch-bridge.json" ] || { echo "FAIL: native host never connected"; cat "$YTDLP_DCH_STATE/host.log" 2>/dev/null; cat "$WORK/browser.log"; exit 1; }
echo "OK: extension connected to the native host"

# 1) no URL given: the single open concert tab must be detected
OUT="$(python -m ytdlp_tool dch-start --list)"
echo "$OUT"
JOB="$(echo "$OUT" | python -c 'import json,sys; print(json.load(sys.stdin)["job_id"])')"
echo "$OUT" | grep -q '"state": "running"' || { echo "FAIL: job not started"; exit 1; }
echo "$OUT" | grep -q "$FAKE_TOKEN" && { echo "FAIL: token leaked to the client"; exit 1; }

# 2) the worker must have received the token on stdin and recorded a final state
for _ in $(seq 1 60); do
  STATUS="$(python -m ytdlp_tool dch-status "$JOB")"
  echo "$STATUS" | grep -q '"state": "running"' || break
  sleep 1
done
echo "$STATUS"
echo "$STATUS" | grep -q "did not receive an access token" && { echo "FAIL: worker got no token"; exit 1; }
grep -rq "$FAKE_TOKEN" "$YTDLP_DCH_STATE" && { echo "FAIL: token written to disk"; exit 1; }
echo "$STATUS" | grep -q '"state": "running"' && { echo "FAIL: worker still running"; exit 1; }
echo "OK: worker ran with the token from the browser; final state recorded; token not on disk"

# 3) explicit URL, wrong site is refused before the browser is asked
if python -m ytdlp_tool dch-start https://evil.test/en/concert/1 2>"$WORK/err"; then echo "FAIL: evil URL accepted"; exit 1; fi
grep -q "digitalconcerthall.com" "$WORK/err" && echo "OK: foreign URL refused"
echo "E2E PASSED"
