#!/usr/bin/env bash
# Phase-6 supervised metered gate session — A10G/BF16 variant (2026-08-11).
#
# Adapted from scripts/nemotron_gate_session.sh for the workspace's AVAILABLE tier:
#   GPU_MEDIUM_8 = 8xA10G (Ampere, 192 GB), BF16 (NOT H100/FP8).
#
# Sequence: prove observer (cheap endpoint) -> deploy BF16 --use-version <BF16_VER>
#   on GPU_MEDIUM_8 -> wait READY (up to 45 min) -> pytest gate per thinking mode
#   (timed, token-observed) -> EXPLICIT teardown -> no-endpoint checks.
# If the endpoint reaches FAILED with an OOM/KV signal at max-model-len 16384,
# it retries ONCE at 8192.
# Teardown is trapped on EXIT/INT/TERM as an idempotent backstop.
#
# Emits grep-able RAW markers (RAW::...) — NO verdicts. The ruling is the reviewer's.
#
# Required arg: $1 = BF16 UC model version to deploy (--use-version).
set -uo pipefail

BF16_VER="${1:?RAW::FATAL usage: nemotron_gate_session_a10g.sh <BF16_UC_VERSION>}"

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PROF="amneal-dev"
PY="$ROOT/.venv/bin/python"; [ -x "$PY" ] || PY="python3"
SESS_DIR=".planning/phases/06-on-prem-verifier-model-weak-model-reliability/session-a10g"
mkdir -p "$SESS_DIR"
export TOKEN_OBSERVER_JSONL="$ROOT/$SESS_DIR/tokens.jsonl"
: > "$TOKEN_OBSERVER_JSONL"            # fresh append-only file
export ENVIRONMENT=databricks
export DEEPEVAL_TELEMETRY_OPT_OUT=YES
export PYTHONPATH="$ROOT/src:$ROOT"

# --- A10G/BF16 tier parametrization (drives deploy_nemotron.py) ---
export NEMOTRON_WORKLOAD_TYPE=GPU_MEDIUM_8
export NEMOTRON_DTYPE=bfloat16
export NEMOTRON_MAX_MODEL_LEN="${NEMOTRON_MAX_MODEL_LEN:-16384}"

# --- Auth into env (never echoed) ---
export DATABRICKS_HOST="$(awk '/^\[amneal-dev\]/{f=1;next} /^\[/{f=0} f&&/^host/{print $3; exit}' ~/.databrickscfg)"
export DATABRICKS_TOKEN="$(databricks auth token --profile "$PROF" 2>/dev/null | python3 -c 'import sys,json;
try: print(json.load(sys.stdin)["access_token"])
except Exception: print("")' )"
if [ -z "${DATABRICKS_HOST:-}" ] || [ -z "${DATABRICKS_TOKEN:-}" ]; then
  echo "RAW::FATAL auth not resolved (host or token empty) — aborting before any deploy"; exit 1
fi
echo "RAW::AUTH host=${DATABRICKS_HOST} token=<redacted len=${#DATABRICKS_TOKEN}>"
echo "RAW::TIER workload=${NEMOTRON_WORKLOAD_TYPE} dtype=${NEMOTRON_DTYPE} max_model_len=${NEMOTRON_MAX_MODEL_LEN} use_version=${BF16_VER}"

DEPLOY="$PY notebooks/deploy_nemotron.py"

teardown() {
  echo "RAW::TEARDOWN start $(date -u +%FT%TZ)"
  $DEPLOY --teardown 2>&1 | sed 's/^/RAW::TEARDOWN | /'
  local state
  state="$(databricks serving-endpoints get defpredict-nemotron --profile "$PROF" 2>&1 | python3 -c 'import sys,json;
try: print(json.load(sys.stdin).get("state",{}).get("ready","GONE"))
except Exception: print("GONE_OR_NOTFOUND")' )"
  echo "RAW::TEARDOWN endpoint_state_after=${state} $(date -u +%FT%TZ)"
}
trap teardown EXIT INT TERM

# Read the endpoint's ready/config-update states + any failure message.
endpoint_status() {
  databricks serving-endpoints get defpredict-nemotron --profile "$PROF" 2>&1 | python3 -c 'import sys,json;
try:
    d=json.load(sys.stdin); s=d.get("state",{})
    msg=""
    ce=d.get("config_update") or s.get("config_update")
    print("ready="+str(s.get("ready"))+" config_update="+str(ce))
    pe=(d.get("pending_config") or {}).get("served_entities") or []
    for e in (d.get("config",{}).get("served_entities") or []) + pe:
        st=e.get("state") or {}
        if st: print("  entity_state="+json.dumps(st))
except Exception as ex: print("STATUS_ERR "+str(ex))'
}

# ================= STEP 0: PROVE OBSERVER BEFORE GPU CLOCK =================
echo "RAW::STEP0 observer proof (cheap pay-per-token endpoint) $(date -u +%FT%TZ)"
$PY scripts/observe_proof.py 2>&1 | sed 's/^/RAW::PROOF | /'
if [ "${PIPESTATUS[0]}" -ne 0 ]; then
  echo "RAW::FATAL observer proof exit!=0 — NOT deploying (no idle GPU)"; exit 1
fi
echo "RAW::STEP0 observer proven live"

# ================= STEP 1: DEPLOY (BF16 on GPU_MEDIUM_8) =================
deploy_and_wait() {
  local mml="$1"
  export NEMOTRON_MAX_MODEL_LEN="$mml"
  echo "RAW::STEP1 deploy --deploy-only --use-version ${BF16_VER} (BF16/GPU_MEDIUM_8, max_model_len=${mml}) $(date -u +%FT%TZ)"
  local t0=$SECONDS
  # --no-wait: we manage the wait loop here so we can inspect FAILED + OOM signals.
  $DEPLOY --deploy-only --use-version "$BF16_VER" --no-wait 2>&1 | sed 's/^/RAW::DEPLOY | /'
  if [ "${PIPESTATUS[0]}" -ne 0 ]; then
    echo "RAW::DEPLOY create-call failed at max_model_len=${mml}"
    return 2
  fi
  # Manual READY wait loop (45 min), watching for FAILED.
  local deadline=$(( $(date +%s) + 45*60 ))
  local ready="" laststate=""
  while [ "$(date +%s)" -lt "$deadline" ]; do
    local raw; raw="$(endpoint_status)"
    ready="$(printf '%s' "$raw" | sed -n 's/^ready=\([^ ]*\).*/\1/p' | head -1)"
    if [ "$raw" != "$laststate" ]; then echo "RAW::DEPLOY status | $raw"; laststate="$raw"; fi
    if [ "$ready" = "READY" ]; then
      echo "RAW::STEP1 deploy READY after $((SECONDS-t0))s (max_model_len=${mml}) $(date -u +%FT%TZ)"
      return 0
    fi
    if printf '%s' "$raw" | grep -qiE "FAILED|error"; then
      echo "RAW::DEPLOY FAILED signal at max_model_len=${mml}: $raw"
      return 1
    fi
    sleep 30
  done
  echo "RAW::DEPLOY TIMEOUT (45min) at max_model_len=${mml}, last: $laststate"
  return 1
}

DEPLOY_OK=0
if deploy_and_wait 16384; then
  DEPLOY_OK=1
else
  rc=$?
  echo "RAW::STEP1 deploy at 16384 not READY (rc=$rc) — tearing down and retrying once at 8192"
  $DEPLOY --teardown 2>&1 | sed 's/^/RAW::DEPLOY | (retry-teardown) /'
  sleep 20
  if deploy_and_wait 8192; then
    DEPLOY_OK=1
  else
    echo "RAW::STEP1 deploy at 8192 ALSO not READY — gate will NOT run"
  fi
fi

if [ "$DEPLOY_OK" -ne 1 ]; then
  echo "RAW::GATE gate did not run (deploy failed)"
  echo "RAW::STEP2 gate skipped"
  # teardown runs via trap on exit
  exit 3
fi

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
  grep -E "conformance_rate|discrimination_accuracy|constant_verdict_tripwire" "$log" | tail -6 \
    | sed "s/^/RAW::GATE[$mode] metric | /"
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

# ================= STEP 3: EXPLICIT teardown ASAP =============================
teardown
trap - EXIT INT TERM

# ================= STEP 4: no-endpoint checks =================================
echo "RAW::STEP4 no-endpoint checks $(date -u +%FT%TZ)"
$PY -m pytest tests/evals/test_reliability_baseline.py tests/unit/test_on_prem_guard.py tests/unit/ -q \
  2>&1 | tail -10 | sed 's/^/RAW::CHECKS | /'
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
