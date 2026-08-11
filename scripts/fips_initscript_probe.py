"""Runs ON the Databricks cluster (spark_python_task) to test whether the
system-wide non-FIPS openssl.cnf init script lets vLLM start. Tiny model only.
Writes a durable PASS/FAIL to a Volume file."""
import subprocess, sys, time, os, urllib.request

OUT = "/Volumes/defpredict/main/artifacts/FIPS_INITSCRIPT_RESULT.txt"


def w(s):
    with open(OUT, "a") as f:
        f.write(s + "\n")
    print(s, flush=True)


open(OUT, "w").close()
w(f"probe start {time.strftime('%FT%TZ', time.gmtime())}")

# 1) Did the init script make OpenSSL non-FIPS? (should list default, NOT fips)
try:
    p = subprocess.run(["openssl", "list", "-providers"], capture_output=True, text=True, timeout=30)
    w("openssl_providers:\n" + (p.stdout or "") + (p.stderr or ""))
except Exception as e:
    w(f"openssl_list_err {e}")

# 2) install vllm
r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "vllm>=0.11"],
                   capture_output=True, text=True)
w(f"pip_vllm_rc={r.returncode}")
v = subprocess.run([sys.executable, "-c", "import vllm;print(vllm.__version__)"],
                   capture_output=True, text=True)
w(f"vllm_import_rc={v.returncode} ver={v.stdout.strip()} err={v.stderr[-400:]}")

# 3) launch a tiny model server; success = HTTP 200 on /v1/models
srv = subprocess.Popen(
    [sys.executable, "-m", "vllm.entrypoints.openai.api_server",
     "--model", "facebook/opt-125m", "--max-model-len", "2048",
     "--gpu-memory-utilization", "0.5", "--port", "8080"],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

ok = False
deadline = time.time() + 600
while time.time() < deadline:
    if srv.poll() is not None:
        w(f"SERVER_EXITED rc={srv.returncode}")
        break
    try:
        with urllib.request.urlopen("http://localhost:8080/v1/models", timeout=5) as resp:
            if resp.status == 200:
                ok = True
                w("HTTP_200 /v1/models")
                break
    except Exception:
        pass
    time.sleep(10)

if not ok and srv.poll() is None:
    srv.terminate()
try:
    tail = srv.stdout.read()[-1500:] if srv.stdout else ""
    w("server_output_tail:\n" + str(tail))
except Exception:
    pass

w("RESULT=PASS" if ok else "RESULT=FAIL")
w(f"probe end {time.strftime('%FT%TZ', time.gmtime())}")
sys.exit(0 if ok else 1)
