"""Stage NVIDIA Llama-3.3-Nemotron-Super-49B-v1.5 weights to the Databricks Volume.

Storage-only (NON-METERED — no GPU). Designed to run as a Databricks job
(spark_python_task / notebook) on a small CPU cluster, OR standalone anywhere
with network access to the HuggingFace hub and write access to the target dir.

The model is PUBLIC and UNGATED (`gated:False, private:False`) — download is
ANONYMOUS (no HF token, no secret scope). The NVIDIA Open Model License ships
in-repo; org adoption is recorded in ADR-nemotron-verifier-model.md.

Deliverables in the target dir after a successful run:
  - the full model repo (config, *.safetensors, tokenizer, etc.)
  - llama_nemotron_toolcall_parser_no_streaming.py  (the vLLM tool-parser plugin)
  - STAGING_MANIFEST.json  (file list + per-file size + total size + file count +
    sha256 of the manifest body) — written last, so its presence means "complete".

Idempotent + resumable:
  - snapshot_download resumes partial files (resume_download=True).
  - If STAGING_MANIFEST.json already exists AND re-verification passes, the run
    is a no-op ("already staged").

Usage:
  python stage_nemotron_weights.py [--target /Volumes/.../nemotron-49b] [--force]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

REPO_ID = "nvidia/Llama-3_3-Nemotron-Super-49B-v1_5"
DEFAULT_TARGET = "/Volumes/defpredict/main/artifacts/nemotron-49b"
PARSER_PLUGIN = "llama_nemotron_toolcall_parser_no_streaming.py"
MANIFEST_NAME = "STAGING_MANIFEST.json"


def _log(msg: str) -> None:
    print(f"[stage-nemotron] {time.strftime('%Y-%m-%d %H:%M:%S')} {msg}", flush=True)


def _scan(target: str) -> tuple[list[dict], int]:
    """Return (sorted file records, total bytes) for everything under target,
    excluding the manifest itself and any lingering *.incomplete/*.lock files."""
    records: list[dict] = []
    total = 0
    for root, _dirs, files in os.walk(target):
        for name in files:
            if name == MANIFEST_NAME or name.endswith((".incomplete", ".lock")):
                continue
            fp = os.path.join(root, name)
            try:
                size = os.path.getsize(fp)
            except OSError:
                continue
            rel = os.path.relpath(fp, target)
            records.append({"path": rel, "size": size})
            total += size
    records.sort(key=lambda r: r["path"])
    return records, total


def _write_manifest(target: str) -> dict:
    records, total = _scan(target)
    body = {
        "repo_id": REPO_ID,
        "target": target,
        "file_count": len(records),
        "total_bytes": total,
        "total_gib": round(total / (1024 ** 3), 2),
        "files": records,
        "parser_plugin_present": any(r["path"].endswith(PARSER_PLUGIN) for r in records),
    }
    digest = hashlib.sha256(
        json.dumps(body, sort_keys=True).encode("utf-8")
    ).hexdigest()
    manifest = {"sha256": digest, **body}
    with open(os.path.join(target, MANIFEST_NAME), "w") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest


def _verify(target: str) -> tuple[bool, str]:
    """Re-scan the target and compare against the written manifest."""
    mpath = os.path.join(target, MANIFEST_NAME)
    if not os.path.exists(mpath):
        return False, "manifest absent"
    with open(mpath) as fh:
        manifest = json.load(fh)
    records, total = _scan(target)
    if len(records) != manifest.get("file_count"):
        return False, f"file_count mismatch: on-disk {len(records)} vs manifest {manifest.get('file_count')}"
    if total != manifest.get("total_bytes"):
        return False, f"total_bytes mismatch: on-disk {total} vs manifest {manifest.get('total_bytes')}"
    if not manifest.get("parser_plugin_present"):
        return False, f"{PARSER_PLUGIN} not present in manifest"
    if not any(r["path"].endswith(PARSER_PLUGIN) for r in records):
        return False, f"{PARSER_PLUGIN} not present on disk"
    return True, (
        f"verified {len(records)} files, {manifest.get('total_gib')} GiB, "
        f"parser plugin present"
    )


def stage(target: str = DEFAULT_TARGET, force: bool = False) -> dict:
    from huggingface_hub import snapshot_download  # lazy: cluster installs it

    os.makedirs(target, exist_ok=True)

    # Idempotent short-circuit: already staged + verifies.
    if not force:
        ok, detail = _verify(target)
        if ok:
            _log(f"already staged — {detail} (no-op; pass --force to re-download)")
            with open(os.path.join(target, MANIFEST_NAME)) as fh:
                return json.load(fh)

    _log(f"anonymous snapshot_download {REPO_ID} -> {target} (resumable)")
    t0 = time.time()
    # token=False forces anonymous access; the repo is public/ungated.
    # resume_download makes the ~100GB transfer restartable.
    snapshot_download(
        repo_id=REPO_ID,
        local_dir=target,
        token=False,
        resume_download=True,
        max_workers=8,
    )
    dt = time.time() - t0
    _log(f"download finished in {dt/60:.1f} min")

    # The parser plugin ships in the repo; assert it landed.
    plugin_hits = []
    for root, _d, files in os.walk(target):
        if PARSER_PLUGIN in files:
            plugin_hits.append(os.path.join(root, PARSER_PLUGIN))
    if not plugin_hits:
        raise RuntimeError(
            f"FATAL: {PARSER_PLUGIN} not found under {target} after download — "
            f"vLLM --tool-parser-plugin would be broken. Aborting before manifest."
        )
    _log(f"parser plugin present: {plugin_hits[0]}")

    manifest = _write_manifest(target)
    ok, detail = _verify(target)
    if not ok:
        raise RuntimeError(f"FATAL: post-write manifest verification failed — {detail}")
    _log(
        f"MANIFEST OK — {manifest['file_count']} files, {manifest['total_gib']} GiB, "
        f"sha256={manifest['sha256'][:12]}…"
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Stage Nemotron-49B weights to a Volume (anonymous, idempotent).")
    ap.add_argument("--target", default=DEFAULT_TARGET, help="target dir (default: the Databricks Volume)")
    ap.add_argument("--force", action="store_true", help="re-download even if already staged")
    ap.add_argument("--verify-only", action="store_true", help="only verify an existing staging manifest")
    args = ap.parse_args(argv)

    if args.verify_only:
        ok, detail = _verify(args.target)
        _log(f"verify-only: {'OK' if ok else 'FAIL'} — {detail}")
        return 0 if ok else 1

    manifest = stage(args.target, force=args.force)
    _log(
        f"STAGING COMPLETE: {manifest['file_count']} files / {manifest['total_gib']} GiB at {args.target}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
