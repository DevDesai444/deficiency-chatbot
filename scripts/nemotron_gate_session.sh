#!/usr/bin/env bash
# Phase-6 supervised metered gate session (reviewer GO, 2026-08-10).
#
# Sequence: prove observer (cheap endpoint) -> deploy FP8 [Fallback Rider armed]
#   --use-version 1 -> wait READY -> deepeval/pytest gate per thinking mode (timed,
#   token-observed) -> EXPLICIT teardown (minimize idle H100) -> no-endpoint checks.
# Teardown is ALSO trapped on EXIT/INT/TERM as an idempotent backstop: the endpoint
# comes down whether the gate passes, fails, errors, or the session is interrupted.
#
# Emits grep-able RAW markers (RAW::...) — NO verdicts. The ruling is the reviewer's.
set -uo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PROF="amneal-dev"
# One interpreter with the full stack (openai+mlflow+requests+structlog+pydantic+pytest).
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY="python3"
SESS_DIR=".planning/phases/06-on-prem-verifier-model-weak-model-reliability/session"
mkdir -p "$SESS_DIR"
export TOKEN_OBSERVER_JSONL="$ROOT/$SESS_DIR/tokens.jsonl"
: > "$TOKEN_OBSERVER_JSONL"            # fresh append-only file
export ENVIRONMENT=databricks
export DEEPEVAL_TELEMETRY_OPT_OUT=YES
export PYTHONPATH="$ROOT/src:$ROOT"

# --- Auth into env (never echoed) ---
export DATABRICKS_HOST="$(databricks auth env --profile "$PROF" 2>/dev/null | python3 -c 'import sys,json;
try: print(json.load(sys.stdin).get("env",{}).get("DATABRICKS_HOST",""))
except Exception: print("")' )"
[ -z "${DATABRICKS_HOST:-}" ] && DATABRICKS_HOST="$(awk '/^\[amneal-dev\]/{f=1;next} /^\[/{f=0} f&&/^host/{print $3; exit}' ~/.databrickscfg)"
export DATABRICKS_HOST
export DATABRICKS_TOKEN="$(databricks auth token --profile "$PROF" 2>/dev/null | python3 -c 'import sys,json;
try: print(json.load(sys.stdin)["access_token"])
except Exception: print("")' )"
if [ -z "${DATABRICKS_HOST:-}" ] || [ -z "${DATABRICKS_TOKEN:-}" ]; then
  echo "RAW::FATAL auth not resolved (host or token empty) — aborting before any deploy"; exit 1
fi
echo "RAW::AUTH host=${DATABRICKS_HOST} token=<redacted len=${#DATABRICKS_TOKEN}>"

DEPLOY="$PY notebooks/deploy_nemotron.py"

teardown() {
  echo "RAW::TEARDOWN start $(date -u +%FT%TZ)"
  $DEPLOY --teardown 2>&1 | sed 's/^/RAW::TEARDOWN | /'
  # read-only confirmation
  local state
  state="$(databricks serving-endpoints get defpredict-nemotron 2>&1 | python3 -c 'import sys,json;
try: print(json.load(sys.stdin).get("state",{}).get("ready","GONE"))
except Exception: print("GONE_OR_NOTFOUND")' )"
  echo "RAW::TEARDOWN endpoint_state_after=${state} $(date -u +%FT%TZ)"
}
trap teardown EXIT INT TERM

# ================= STEP 0: PROVE OBSERVER BEFORE H100 CLOCK =================
echo "RAW::STEP0 observer proof (cheap pay-per-token endpoint) $(date -u +%FT%TZ)"
if ! $PY scripts/observe_proof.py 2>&1 | sed 's/^/RAW::PROOF | /'; then
  echo "RAW::FATAL observer proof FAILED — NOT deploying (no idle H100)"; exit 1
fi
# scripts/observe_proof.py exits nonzero on fail; pipefail captures it via PIPESTATUS
if [ "${PIPESTATUS[0]}" -ne 0 ]; then
  echo "RAW::FATAL observer proof exit!=0 — NOT deploying"; exit 1
fi
echo "RAW::STEP0 observer proven live"

# ================= STEP 1: DEPLOY (FP8, Fallback Rider armed) =================
echo "RAW::STEP1 deploy --deploy-only --use-version 1 (FP8/H100 Row1; rider armed) $(date -u +%FT%TZ)"
DEPLOY_T0=$SECONDS
if ! $DEPLOY --deploy-only --use-version 1 --timeout-minutes 45 2>&1 | sed 's/^/RAW::DEPLOY | /'; then
  echo "RAW::FATAL deploy/wait-ready failed (see RAW::DEPLOY rows for Fallback Rider row selection)"; exit 1
fi
echo "RAW::STEP1 deploy READY after $((SECONDS-DEPLOY_T0))s $(date -u +%FT%TZ)"

# ================= STEP 2: GATE per thinking mode (timed, token-observed) =====
GATE_RC=0
run_mode() {
  local mode="$1"
  export PROBE_MODE="$mode"
  local log="$SESS_DIR/gate_${mode}.log"
  echo "RAW::GATE[$mode] start $(date -u +%FT%TZ)"
  local t0=$SECONDS
  $PY -m pytest \
    "tests/evals/test_verifier_probe.py::test_verifier_conformance_and_discrimination[$mode]" \
    -o addopts="" -v -s > "$log" 2>&1
  local rc=$?
  local dur=$((SECONDS-t0))
  echo "RAW::GATE[$mode] pytest_exit=$rc wallclock_s=$dur $(date -u +%FT%TZ)"
  # Extract the metric structlog lines (emitted by measure() before any assert)
  grep -E "conformance_rate|discrimination_accuracy|constant_verdict_tripwire" "$log" | tail -5 \
    | sed "s/^/RAW::GATE[$mode] metric | /"
  # Per-mode token totals from the observer JSONL
  python3 - "$TOKEN_OBSERVER_JSONL" "$mode" <<'PY' | sed "s/^/RAW::GATE[$mode] tokens | /"
import json,sys
path,mode=sys.argv[1],sys.argv[2]
pt=ct=n=0
for line in open(path):
    line=line.strip()
    if not line: continue
    r=json.loads(line)
    if r.get("mode")==mode:
        n+=1; pt+=r.get("prompt_tokens",0); ct+=r.get("completion_tokens",0)
print(f"calls={n} prompt_tokens={pt} completion_tokens={ct} total_tokens={pt+ct}")
PY
  [ $rc -ne 0 ] && GATE_RC=1
  return 0
}
run_mode on
run_mode off
echo "RAW::STEP2 gate complete gate_rc=$GATE_RC"

# ================= STEP 3: EXPLICIT teardown ASAP (before no-endpoint checks) =
teardown
trap - EXIT INT TERM   # already torn down; disarm so we don't double-run at exit

# ================= STEP 4: no-endpoint checks (endpoint already down) =========
echo "RAW::STEP4 no-endpoint checks $(date -u +%FT%TZ)"
$PY -m pytest tests/evals/test_reliability_baseline.py tests/unit/test_on_prem_guard.py tests/unit/ -q \
  2>&1 | tail -8 | sed 's/^/RAW::CHECKS | /'
echo "RAW::CHECKS exit=${PIPESTATUS[0]}"

# ================= STEP 5: session token/cost summary =========================
python3 - "$TOKEN_OBSERVER_JSONL" <<'PY' | sed 's/^/RAW::SESSION | /'
import json,sys
from collections import defaultdict
path=sys.argv[1]
agg=defaultdict(lambda:[0,0,0])
for line in open(path):
    line=line.strip()
    if not line: continue
    r=json.loads(line)
    a=agg[r.get("mode","?")]; a[0]+=1; a[1]+=r.get("prompt_tokens",0); a[2]+=r.get("completion_tokens",0)
tot=[0,0,0]
for m,(n,p,c) in sorted(agg.items()):
    print(f"mode={m} calls={n} prompt={p} completion={c} total={p+c}")
    tot[0]+=n; tot[1]+=p; tot[2]+=c
print(f"SESSION_TOTAL calls={tot[0]} prompt={tot[1]} completion={tot[2]} total_tokens={tot[1]+tot[2]}")
PY
echo "RAW::DONE $(date -u +%FT%TZ)"
