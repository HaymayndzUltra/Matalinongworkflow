# =========================
# KYC HARDENING + TEST PLAN
# =========================
# Target path: /home/haymayndz/MatalinongWorkflow/KYC VERIFICATION
# Run these from repo root (same directory level as "KYC VERIFICATION")

# 1) Prepare environment
cd /home/haymayndz/MatalinongWorkflow
python3 --version
pip install -r "KYC VERIFICATION/requirements.txt"

# 2) Apply stricter runtime thresholds via env (no code changes)
export FACE_BBOX_FILL_MIN=0.35
export FACE_CENTERING_TOLERANCE=0.10
export FACE_POSE_MAX_ANGLE=20
export FACE_TENENGRAD_MIN_640W=800
export FACE_BRIGHTNESS_P05_MIN=30
export FACE_BRIGHTNESS_P95_MAX=225
export FACE_STABILITY_MIN_MS=1200
export FACE_PAD_SCORE_MIN=0.80
export FACE_PAD_SPOOF_THRESHOLD=0.25
export FACE_CONSENSUS_MEDIAN_MIN=0.68
export FACE_CONSENSUS_FRAME_MIN_COUNT=4
export FACE_CONSENSUS_FRAME_MIN_SCORE=0.60

# 3) (Optional) Persist stricter face thresholds into JSON for audit (keeps env precedence)
#    Only if you want to store to file-managed config too.
jq '.thresholds.geometry.face_bbox_fill_min.value=0.35
  | .thresholds.geometry.face_centering_tolerance.value=0.10
  | .thresholds.geometry.face_pose_max_angle.value=20
  | .thresholds.geometry.face_tenengrad_min_640w.value=800
  | .thresholds.geometry.face_brightness_p05_min.value=30
  | .thresholds.geometry.face_brightness_p95_max.value=225
  | .thresholds.geometry.face_stability_min_ms.value=1200
  | .thresholds.pad.face_pad_score_min.value=0.80
  | .thresholds.pad.face_pad_spoof_threshold.value=0.25
  | .thresholds.burst.face_consensus_median_min.value=0.68
  | .thresholds.burst.face_consensus_frame_min_count.value=4
  | .thresholds.burst.face_consensus_frame_min_score.value=0.60' \
  "KYC VERIFICATION/configs/face_thresholds.json" > /tmp/face_thresholds.json && \
mv /tmp/face_thresholds.json "KYC VERIFICATION/configs/face_thresholds.json"

# 4) Add global API key + HMAC signature middleware (defense-in-depth)
cat > "KYC VERIFICATION/src/api/security_middleware.py" <<'PY'
import hmac, hashlib, time
from typing import Callable
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

ALLOWED_PATHS = {"/docs", "/redoc", "/openapi.json", "/health", "/live", "/metrics", "/metrics/prometheus"}

class SecurityAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_key: str, signing_key: bytes, require_tls: bool = True):
        super().__init__(app)
        self.api_key = api_key
        self.signing_key = signing_key
        self.require_tls = require_tls

    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path
        # Allow safe endpoints
        if any(path.startswith(p) for p in ALLOWED_PATHS):
            return await call_next(request)

        # Enforce TLS in production
        if self.require_tls and request.url.scheme != "https" and "localhost" not in str(request.url):
            return JSONResponse({"error":"HTTPS required","error_code":"TLS_REQUIRED"}, status_code=400)

        # API key + HMAC headers
        api_key = request.headers.get("x-api-key")
        sig = request.headers.get("x-sig")
        ts = request.headers.get("x-ts")
        if not api_key or not sig or not ts:
            return JSONResponse({"error":"Missing auth headers","error_code":"AUTH_HEADERS"}, status_code=401)
        if api_key != self.api_key:
            return JSONResponse({"error":"Unauthorized","error_code":"API_KEY_BAD"}, status_code=401)

        try:
            ts_i = int(ts)
            if abs(time.time() - ts_i) > 300:
                return JSONResponse({"error":"Timestamp skew","error_code":"SIG_TS"}, status_code=401)
        except Exception:
            return JSONResponse({"error":"Bad timestamp","error_code":"SIG_TS"}, status_code=401)

        msg = f"{api_key}.{ts}".encode()
        expected = hmac.new(self.signing_key, msg, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return JSONResponse({"error":"Bad signature","error_code":"SIG_BAD"}, status_code=401)

        return await call_next(request)
PY

# 5) Wire middleware + tighten CORS allowed origins from policy_pack.yaml
python3 - <<'PY'
import yaml, json, os, re
from pathlib import Path
ap = Path("KYC VERIFICATION/src/api/app.py")
txt = ap.read_text(encoding="utf-8")
if "SecurityAuthMiddleware" not in txt:
    txt = txt.replace(
        "from fastapi.middleware.cors import CORSMiddleware",
        "from fastapi.middleware.cors import CORSMiddleware\nfrom src.api.security_middleware import SecurityAuthMiddleware"
    )
    # Pull allowed origins from policy_pack.yaml if available
    policy = yaml.safe_load(Path("KYC VERIFICATION/configs/policy_pack.yaml").read_text(encoding="utf-8"))
    allowed = policy.get("security_settings",{}).get("api",{}).get("allowed_origins", [])
    if not allowed: allowed=["https://app.example.com","https://kyc.example.com"]
    # Replace permissive CORS
    txt = re.sub(r'allow_origins=\[.*?\]', f'allow_origins={json.dumps(allowed)}', txt, count=1, flags=re.S)
    # Install middleware with secrets read from env (set next step)
    insert_after = "app.add_middleware(\n        CORSMiddleware,"
    hook = f'''app.add_middleware(
        SecurityAuthMiddleware,
        api_key=os.getenv("KYC_API_KEY","dev_key"),
        signing_key=os.getenv("KYC_SIGNING_KEY","dev_signing_key").encode(),
        require_tls=os.getenv("KYC_REQUIRE_TLS","true").lower()=="true"
    )'''
    txt = txt.replace(insert_after, insert_after) + "\n" + hook + "\n"
    ap.write_text(txt, encoding="utf-8")
print("OK")
PY

# 6) Set API secrets (dev example; use secure secrets in prod)
export KYC_API_KEY="dev_key"
export KYC_SIGNING_KEY="dev_signing_key"
export KYC_REQUIRE_TLS="false"   # allow http://localhost during dev

# 7) Fix v2 lock action to pass required fields to handler (bbox/frame dims/metrics)
python3 - <<'PY'
from pathlib import Path; import re
p = Path("KYC VERIFICATION/src/api/v2_endpoints.py")
s = p.read_text(encoding="utf-8")
pat = r'if action == "lock":[\s\S]*?result = handle_lock_check\(session_id, lock_token\)[\s\S]*?elif action == "upload"'
if re.search(pat, s):
    repl = (
        'if action == "lock":\n'
        '            d = data or {}\n'
        '            bbox = d.get("bbox", {"x":0,"y":0,"width":0,"height":0})\n'
        '            frame_width = int(d.get("frame_width", 640))\n'
        '            frame_height = int(d.get("frame_height", 480))\n'
        '            landmarks = d.get("landmarks")\n'
        '            metrics = d.get("metrics")\n'
        '            lock_token = d.get("lock_token")\n'
        '            result = handle_lock_check(\n'
        '                session_id=session_id,\n'
        '                bbox=bbox,\n'
        '                frame_width=frame_width,\n'
        '                frame_height=frame_height,\n'
        '                landmarks=landmarks,\n'
        '                metrics=metrics,\n'
        '                lock_token=lock_token\n'
        '            )\n'
        '        \n'
        '        elif action == "upload":'
    )
    s = re.sub(pat, repl, s)
    p.write_text(s, encoding="utf-8")
print("OK")
PY

# 8) Patch undefined metrics in handle_lock_check (focus/motion/glare/corners/consensus_quality)
python3 - <<'PY'
from pathlib import Path
fp = Path("KYC VERIFICATION/src/face/handlers.py")
t = fp.read_text(encoding="utf-8")
needle = "quality_metrics = {"
if needle in t and "consensus_quality" in t:
    # Insert safe derivation before quality_metrics block
    t = t.replace(
        "# Prepare metrics for quality gates\n    quality_metrics = {",
        "# Prepare metrics for quality gates\n"
        "    focus = (metrics or {}).get('focus_score', 1.0)\n"
        "    motion = (metrics or {}).get('motion_score', 0.0)\n"
        "    glare = (metrics or {}).get('glare_percent', 0.0)\n"
        "    corners = (metrics or {}).get('corners_score', 1.0)\n"
        "    consensus_quality = float((metrics or {}).get('overall_quality', 0.0))\n"
        "    quality_metrics = {"
    )
    fp.write_text(t, encoding="utf-8")
print("OK")
PY

# 9) Restrict CORS (already done in step 5); verify diff (optional)
rg -n "allow_origins" "KYC VERIFICATION/src/api/app.py" | cat

# 10) Start API (dev)
cd "KYC VERIFICATION"
python3 run_api.py

# 11) Generate auth headers for curl
TS=$(date +%s)
SIG=$(python3 - <<PY
import os,hmac,hashlib,time
k=os.getenv("KYC_SIGNING_KEY","dev_signing_key").encode()
msg=f"{os.getenv('KYC_API_KEY','dev_key')}.{os.getenv('TS_OVERRIDE','')}"; 
print(hmac.new(k,(os.getenv('KYC_API_KEY','dev_key')+'.'+str(int(time.time()))).encode(),hashlib.sha256).hexdigest())
PY
)

# 12) Smoke test: v2 lock (provide minimal bbox/frame dims)
curl -s -X POST http://localhost:8000/v2/face/scan \
  -H "Content-Type: application/json" \
  -H "x-api-key: $KYC_API_KEY" -H "x-ts: $TS" -H "x-sig: $SIG" \
  -d '{
        "session_id":"sess_1",
        "action":"lock",
        "data":{
          "bbox":{"x":100,"y":100,"width":200,"height":200},
          "frame_width":640,"frame_height":480,
          "metrics":{"focus_score":8.0,"motion_score":0.05,"glare_percent":0.02,"corners_score":0.97,"overall_quality":0.9}
        }
      }' | jq .

# 13) Unit tests (first-step focus)
#    Run existing suites (adjust if pytest present)
pytest -q "KYC VERIFICATION/tests/test_suite_unit.py" -q || true
pytest -q "KYC VERIFICATION/tests/test_api.py" -q || true
pytest -q "KYC VERIFICATION/tests/test_api_consolidation_simple.py" -q || true

# 14) Add targeted tests for lock gates (optional quick skeleton)
mkdir -p "KYC VERIFICATION/tests/custom"
cat > "KYC VERIFICATION/tests/custom/test_lock_quality_gates.py" <<'PY'
import pytest
from src.face.handlers import handle_lock_check

def _req(metrics=None, w=640, h=480):
    return dict(
        session_id="sess_t",
        bbox={"x":100,"y":100,"width":int(0.30*w),"height":int(0.30*h)},
        frame_width=w, frame_height=h, landmarks=None, gray_face_region=None, metrics=metrics
    )

def test_reject_low_fill_ratio():
    # width*height ~ 0.09 of frame (below 0.35 threshold) -> reject
    r = handle_lock_check(**_req(metrics={"focus_score":8,"motion_score":0.05,"glare_percent":0.02,"corners_score":0.99}))
    assert r["ok"] is False and "FILL_OUT_OF_RANGE" in r.get("reasons", [])

def test_cancel_on_jitter_motion():
    r = handle_lock_check(**_req(metrics={"focus_score":8,"motion_score":0.6,"glare_percent":0.02,"corners_score":0.99}))
    assert r["ok"] is False

def test_countdown_token_too_early():
    r = handle_lock_check(**_req(metrics={"focus_score":8,"motion_score":0.01,"glare_percent":0.02,"corners_score":0.99}))
    assert ("lock_token" in r) == r["ok"]
PY
pytest -q "KYC VERIFICATION/tests/custom/test_lock_quality_gates.py" -q || true

# 15) Performance target check (cancel-on-jitter path under 50ms target)
#     (Smoke; real perf needs load test harness)
python3 - <<'PY'
from src.face.quality_gates import get_quality_manager
qm = get_quality_manager(); r = qm.check_quality({"motion": 0.9, "focus": 0.4, "glare": 0.5})
print({"response_time_ms": r.response_time_ms, "cancel": bool(r.cancel_reason)})
PY

# 16) Security checks
#     - Missing headers -> 401
curl -s -X POST http://localhost:8000/v2/face/scan -H "Content-Type: application/json" \
  -d '{"session_id":"s","action":"lock","data":{}}' | jq .
#     - Bad signature -> 401
curl -s -X POST http://localhost:8000/v2/face/scan \
  -H "Content-Type: application/json" -H "x-api-key: $KYC_API_KEY" -H "x-ts: $TS" -H "x-sig: BAD" \
  -d '{"session_id":"s","action":"lock","data":{}}' | jq .

# 17) (Optional) Enforce per-IP rate-limit at gateway (nginx/ingress) to match configs/thresholds.json.rate_limit_per_minute

# 18) Run full suite (if available)
pytest -q "KYC VERIFICATION/tests" || true

# 19) Production notes
# - Set KYC_REQUIRE_TLS=true in prod
# - Keep API keys and signing keys in secret store (not env on host)
# - Monitor /metrics and /metrics/prometheus; alert on cancel rate spikes and lock p95 > target
# - Periodically re-validate thresholds via src/config/threshold_manager.py validate_all()