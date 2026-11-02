#!/usr/bin/env bash
set -euo pipefail
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
if [[ ! -x .venv/bin/python ]]; then
  bash install.sh
fi
# Existing app processes do not need to be duplicated after a reconnect.
if .venv/bin/python - <<'PY'
import json,urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=2) as r:
        data=json.load(r)
    assert data.get('status')=='ok' and data.get('schema')==1
except Exception:
    raise SystemExit(1)
PY
then
  echo 'SỨA đang chạy. Mở tab Ports → cổng 8000 → Open in Browser.'
  exit 0
fi
# Secure is set only for the app serving Codespaces' HTTPS forwarded URL.
# Plain HTTP integration tests do not inherit this process-only setting.
if [[ "${CODESPACES:-}" == "true" ]]; then
  export SUA_SECURE_COOKIE=1
fi
export HOST=127.0.0.1
export PORT=8000
nohup .venv/bin/python server.py > /tmp/sua-cafe.log 2>&1 < /dev/null &
app_pid=$!
for attempt in {1..20}; do
  if ! kill -0 "$app_pid" 2>/dev/null; then
    echo 'Không khởi động được SỨA. Xem /tmp/sua-cafe.log.' >&2
    exit 1
  fi
  if .venv/bin/python - <<'PY'
import json,urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=1) as r:
        assert json.load(r).get('status')=='ok'
except Exception:
    raise SystemExit(1)
PY
  then
    echo 'SỨA đã sẵn sàng. Mở tab Ports → cổng 8000 → Open in Browser. Giữ cổng ở chế độ Private.'
    exit 0
  fi
  sleep 0.5
done
echo 'SỨA chưa sẵn sàng. Xem /tmp/sua-cafe.log.' >&2
exit 1
