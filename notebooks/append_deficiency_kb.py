"""
APPEND a precedent workbook's deficiency rows to the flat deficiency_kb (Destination A).

This is the append-only counterpart to notebooks/seed_data.py, which uses
`to_sql(if_exists="replace")` and would WIPE every existing row. Nothing here ever replaces.

Usage:
    PYTHONPATH=src uv run python notebooks/append_deficiency_kb.py \
        --xlsm "Sample Data/ANDA-Solid-Oral-Deficiency-RoadMap.xlsm" --target local --dry-run
    PYTHONPATH=src uv run python notebooks/append_deficiency_kb.py \
        --xlsm "Sample Data/ANDA-Solid-Oral-Deficiency-RoadMap.xlsm" \
        --target local --expect-before 500

--expect-before is REQUIRED for any real write: it is the idempotency guard for a monotonic
append. A second run sees the post-append count, disagrees, and aborts instead of duplicating.
"""
from __future__ import annotations

import argparse
import sqlite3

DB_PATH = "data/defpredict.db"


def _local_before(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM deficiency_kb").fetchone()[0]
    finally:
        conn.close()


def _print_table(title: str, pairs: list[tuple[str, object, object]]) -> None:
    print(f"\n{title}")
    print(f"  {'target':<40} {'before':>10} {'after':>10}")
    for name, before, after in pairs:
        print(f"  {name:<40} {before:>10} {after:>10}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Append deficiency rows (never replace)")
    parser.add_argument("--xlsm", required=True, help="Path to the .xlsm workbook")
    parser.add_argument("--target", choices=("local", "databricks", "both"), default="local")
    parser.add_argument("--db", default=DB_PATH, help="SQLite path (local target)")
    parser.add_argument("--expect-before", type=int, default=None,
                        help="Observed row count before the append; required unless --dry-run")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report row counts and the planned id range; write nothing")
    args = parser.parse_args()

    if not args.dry_run and args.expect_before is None:
        parser.error("--expect-before is required unless --dry-run")

    from databricks.deficiency_kb import (
        append_databricks,
        append_embeddings_databricks,
        append_local,
        load_kb_rows,
        remote_counts,
    )

    rows = load_kb_rows(args.xlsm)
    print(f"Loaded {len(rows)} rows from {args.xlsm}")

    wants_local = args.target in ("local", "both")
    wants_dbx = args.target in ("databricks", "both")

    if args.dry_run:
        if wants_local:
            before = _local_before(args.db)
            print(f"\n[dry-run] local deficiency_kb before = {before}")
            print(f"[dry-run] would append {len(rows)} rows -> after {before + len(rows)}, "
                  f"rowids {before + 1}..{before + len(rows)}")
        if wants_dbx:
            remote = remote_counts()
            print(f"\n[dry-run] databricks deficiency_kb before = {remote['deficiency_kb']} "
                  f"(max id {remote['max_id']})")
            print(f"[dry-run] databricks deficiency_embeddings before = "
                  f"{remote['deficiency_embeddings']}")
            print(f"[dry-run] would assign ids {remote['max_id'] + 1}.."
                  f"{remote['max_id'] + len(rows)}")
        print("\n[dry-run] nothing written.")
        return 0

    results: list[tuple[str, object, object]] = []

    if wants_local:
        rep = append_local(rows, expect_before=args.expect_before, db_path=args.db)
        results.append(("local deficiency_kb", rep["before"], rep["after"]))
        print(f"\nlocal: appended {rep['appended']} rows; rowids "
              f"{rep['first_new_rowid']}..{rep['max_rowid']}")

    if wants_dbx:
        kb_rep = append_databricks(rows, expect_before=args.expect_before)
        results.append(("databricks deficiency_kb", kb_rep["before"], kb_rep["after"]))
        print(f"\ndatabricks kb: appended {kb_rep['appended']} rows as ids "
              f"{kb_rep['first_id']}..{kb_rep['last_id']} in {kb_rep['statements']} statement(s); "
              f"response_date convention mirrored as {kb_rep['response_date_convention']!r}")

        emb_rep = append_embeddings_databricks(
            rows, ids=kb_rep["ids"], expect_before=args.expect_before,
        )
        results.append(("databricks deficiency_embeddings", emb_rep["before"], emb_rep["after"]))
        print(f"databricks embeddings: appended {emb_rep['appended']} rows in "
              f"{emb_rep['statements']} statement(s)")

    _print_table("before -> after", results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
