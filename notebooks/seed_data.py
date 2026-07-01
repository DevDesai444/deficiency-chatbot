"""
Load deficiency records from .xlsm into local SQLite (or Databricks Delta table).

Usage (local):
    uv run python notebooks/seed_data.py --xlsm "path/to/ANDA-TDDS-Deficiency Roadmap.xlsm"

On Databricks, run as a notebook — the same logic writes to Delta instead of SQLite.
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import openpyxl
import pandas as pd


def load_xlsm(path: str) -> pd.DataFrame:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)

    records: list[dict] = []
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) < 2:
            continue

        header_idx = None
        for ri, row in enumerate(rows[:10]):
            cells = [str(c or "").strip().lower() for c in row]
            if any("deficien" in c for c in cells) and any("anda" in c or "product" in c for c in cells):
                header_idx = ri
                break

        if header_idx is None:
            continue

        headers = [str(h or "").strip() for h in rows[header_idx]]

        for row in rows[header_idx + 1:]:
            if all(cell is None for cell in row):
                continue
            record = {}
            for h, val in zip(headers, row, strict=False):
                if h:
                    record[h.strip()] = str(val).strip() if val is not None else ""
            records.append(record)

    wb.close()

    if not records:
        raise ValueError(f"No deficiency records found in {path}")

    df = pd.DataFrame(records)
    df.columns = [c.lower().replace(" ", "_") for c in df.columns]
    return df


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map common column name variants to standard schema."""
    rename_map: dict[str, str] = {}
    for col in df.columns:
        lower = col.lower()
        if "anda" in lower and ("#" in lower or "number" in lower):
            rename_map[col] = "anda_number"
        elif "product" in lower and "name" in lower:
            rename_map[col] = "product_name"
        elif "dosage" in lower:
            rename_map[col] = "dosage_form"
        elif "section" in lower and "cmc" in lower:
            rename_map[col] = "cmc_section"
        elif "deficiency" in lower and "type" in lower:
            rename_map[col] = "deficiency_type"
        elif lower in ("category", "category_of_deficiency"):
            rename_map[col] = "category"
        elif "cohort" in lower:
            rename_map[col] = "cohort_year"
        elif lower == "deficiency" or (
            "deficiency" in lower and ("text" in lower or "description" in lower or "detail" in lower)
        ):
            rename_map[col] = "deficiency_text"
        elif "deficiency" in lower and "response" in lower:
            rename_map[col] = "deficiency_response"
        elif "response" in lower and "date" in lower:
            rename_map[col] = "response_date"

    if rename_map:
        df = df.rename(columns=rename_map)

    return df


def write_to_sqlite(df: pd.DataFrame, db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    df.to_sql("deficiency_kb", conn, if_exists="replace", index=False)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS analysis_jobs (
            job_id TEXT PRIMARY KEY,
            document_name TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            completed_at TEXT,
            intermediate_report TEXT,
            flaw_report TEXT,
            recommendations TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            timestamp TEXT,
            layer TEXT,
            event_type TEXT,
            agent_name TEXT,
            message TEXT
        )
    """)

    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM deficiency_kb").fetchone()[0]
    conn.close()
    return count


def main():
    parser = argparse.ArgumentParser(description="Load deficiency data")
    parser.add_argument("--xlsm", required=True, help="Path to .xlsm file")
    parser.add_argument("--db", default="data/defpredict.db", help="SQLite output path")
    args = parser.parse_args()

    print(f"Loading records from {args.xlsm}...")
    df = load_xlsm(args.xlsm)
    df = _normalize_columns(df)
    print(f"Found {len(df)} records with columns: {list(df.columns)}")

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    count = write_to_sqlite(df, args.db)
    print(f"Wrote {count} records to {args.db}")

    categories = df["deficiency_type"].unique() if "deficiency_type" in df.columns else []
    if len(categories) > 0:
        print(f"\nDeficiency types ({len(categories)}):")
        for cat in sorted(categories):
            if cat:
                print(f"  - {cat}")


if __name__ == "__main__":
    main()
