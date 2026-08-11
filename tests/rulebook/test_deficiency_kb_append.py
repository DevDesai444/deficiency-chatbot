"""Guarded APPEND path for the flat deficiency_kb (Destination A), local + Databricks.

notebooks/seed_data.py wrote SQLite only, via `df.to_sql(..., if_exists="replace")` -- re-running
it would WIPE the existing 500 TDDS rows. This path APPENDS, refuses to run when the observed
before-count disagrees with --expect-before, and writes the Databricks side too.

ZERO live Databricks calls: _run_sql is monkeypatched. No credentials required.
"""
from __future__ import annotations

import sqlite3

import numpy as np
import openpyxl
import pytest

from databricks import deficiency_kb as kb
from databricks import delta as delta_mod

_KB_COLUMNS = [
    "anda_number", "product_name", "dosage_form", "cmc_section", "deficiency_type",
    "cohort_year", "category", "deficiency_text", "deficiency_response",
]

# Deliberately the SOLID ORAL spellings: load_kb_rows reuses rulebook.precedents._read_rows, so
# the BLOCKER-1 header fix must protect this destination too.
_SOLID_ORAL_HEADER = [
    "ANDA #", "Product Name", "Dosage Form", "CMC Section", "Deficiency Type",
    "Cohort year of the Deficiency", "Catagory of Deficiency", "Deficiency ", "Deficiency Response",
]


def _seeded_db(tmp_path, n: int = 2) -> str:
    db_path = str(tmp_path / "kb.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE deficiency_kb (" + ", ".join(f'"{c}" TEXT' for c in _KB_COLUMNS) + ")"
    )
    for i in range(n):
        conn.execute(
            f"INSERT INTO deficiency_kb ({', '.join(_KB_COLUMNS)}) "
            f"VALUES ({', '.join('?' * len(_KB_COLUMNS))})",
            [f"orig-{i}-{c}" for c in _KB_COLUMNS],
        )
    conn.commit()
    conn.close()
    return db_path


def _make_workbook(tmp_path, rows: list[list], name: str = "wb.xlsx") -> str:
    from rulebook.precedents import _SHEET_NAME

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = _SHEET_NAME
    ws.append(["title row"])
    ws.append(_SOLID_ORAL_HEADER)
    for r in rows:
        ws.append(r)
    path = tmp_path / name
    wb.save(path)
    return str(path)


# --- load_kb_rows ---------------------------------------------------------------------------


def test_load_kb_rows_emits_exactly_the_nine_canonical_string_fields(tmp_path):
    path = _make_workbook(tmp_path, [
        [206392, "Widget", "Tablet", "Drug Product", "Specification/CoA",
         "GD-I - CY-4", "IR", "first deficiency", "2014-09-29"],
        [None, None, None, "Dissolution", "Dissolution",
         None, "IR", "second deficiency", None],
        [206393, "Gadget", "Capsule", "Drug Product", "Stability",
         "GD-II - CY-1", "MI", None, "n/a"],   # empty deficiency -> skipped, as seed_data did
    ])

    rows = kb.load_kb_rows(path)

    assert len(rows) == 2
    for row in rows:
        assert sorted(row) == sorted(_KB_COLUMNS)
        assert "row_ordinal" not in row
        assert all(isinstance(v, str) for v in row.values())

    # openpyxl hands back anda_number as an int; seed_data normalized with str(v).strip()
    assert rows[0]["anda_number"] == "206392"
    assert rows[0]["cohort_year"] == "GD-I - CY-4"
    assert rows[0]["category"] == "IR"          # the BLOCKER-1 columns, on this destination too

    # NOT forward-filled: seed_data did not, so the existing 500 rows carry raw blanks and this
    # destination must stay raw-as-read. The D-PREC forward-fill belongs to Destination B only.
    assert rows[1]["anda_number"] == ""
    assert rows[1]["product_name"] == ""
    assert rows[1]["cohort_year"] == ""


# --- append_local ---------------------------------------------------------------------------


def test_append_local_leaves_existing_rows_byte_identical_and_continues_rowids(tmp_path):
    db_path = _seeded_db(tmp_path, n=2)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    before_rows = [dict(r) for r in conn.execute("SELECT rowid, * FROM deficiency_kb ORDER BY rowid")]
    conn.close()

    new_rows = [{c: f"new-{i}-{c}" for c in _KB_COLUMNS} for i in range(3)]
    report = kb.append_local(new_rows, expect_before=2, db_path=db_path)

    assert report["before"] == 2
    assert report["appended"] == 3
    assert report["after"] == 5
    assert report["first_new_rowid"] == 3
    assert report["max_rowid"] == 5

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    after_rows = [dict(r) for r in conn.execute("SELECT rowid, * FROM deficiency_kb ORDER BY rowid")]
    conn.close()

    assert after_rows[:2] == before_rows          # originals untouched, byte for byte
    assert after_rows[2]["deficiency_text"] == "new-0-deficiency_text"
    assert after_rows[4]["deficiency_text"] == "new-2-deficiency_text"


def test_append_local_preserves_workbook_order(tmp_path):
    """SQLite rowid 501..5596 must stay positionally aligned with Databricks id 501..5596:
    notebooks/build_index.py keys the FAISS map on rowid and databricks/vector.py joins the
    remote embeddings on id."""
    db_path = _seeded_db(tmp_path, n=0)
    new_rows = [{**{c: "" for c in _KB_COLUMNS}, "deficiency_text": f"d{i}"} for i in range(10)]
    kb.append_local(new_rows, expect_before=0, db_path=db_path)

    conn = sqlite3.connect(db_path)
    got = conn.execute("SELECT deficiency_text FROM deficiency_kb ORDER BY rowid").fetchall()
    conn.close()
    assert [g[0] for g in got] == [f"d{i}" for i in range(10)]


def test_append_local_refuses_when_before_count_disagrees(tmp_path):
    """The idempotency guard for a monotonic append: a second run sees 5,596 != 500 and aborts
    instead of duplicating 5,096 rows."""
    db_path = _seeded_db(tmp_path, n=2)
    with pytest.raises(RuntimeError) as exc:
        kb.append_local([{c: "x" for c in _KB_COLUMNS}], expect_before=999, db_path=db_path)
    assert "999" in str(exc.value)

    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM deficiency_kb").fetchone()[0] == 2
    conn.close()


def test_append_local_inserts_by_column_name_not_position(tmp_path):
    """The table was created by pandas to_sql, so its column ORDER is the spreadsheet's, not
    this module's. Insert by name or the values land in the wrong columns."""
    db_path = str(tmp_path / "reordered.db")
    reordered = list(reversed(_KB_COLUMNS))
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE deficiency_kb (" + ", ".join(f'"{c}" TEXT' for c in reordered) + ")")
    conn.commit()
    conn.close()

    kb.append_local([{c: f"v-{c}" for c in _KB_COLUMNS}], expect_before=0, db_path=db_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = dict(conn.execute("SELECT * FROM deficiency_kb").fetchone())
    conn.close()
    assert row == {c: f"v-{c}" for c in _KB_COLUMNS}


# --- append_databricks ----------------------------------------------------------------------


def _fake_result(columns: list[str], data: list[list]) -> dict:
    return {
        "manifest": {"schema": {"columns": [{"name": c} for c in columns]}},
        "result": {"data_array": data},
    }


# The fake warehouse's mutable state, module-level so a test can swap the reported DDL after
# the `dbx` fixture has already been constructed.
dbx_state: dict = {}


@pytest.fixture
def dbx(monkeypatch):
    """A STATEFUL fake warehouse: COUNT(*) reflects the rows the fake has actually 'inserted',
    so the before/after report in the return value is exercised for real."""
    statements: list[str] = []
    # module-level so a test can swap the DDL AFTER the fixture has been built
    dbx_state.clear()
    dbx_state.update({
        "deficiency_kb": 500, "deficiency_embeddings": 500, "max_id": 500,
        # a PLAIN bigint id by default; the identity-guard test swaps this in
        "ddl": "CREATE TABLE cat.sch.deficiency_kb (\n  id BIGINT,\n  anda_number STRING)",
    })
    state = dbx_state

    def _tuple_count(stmt: str) -> int:
        return stmt.split("VALUES ", 1)[1].count("), (") + 1

    def fake_run_sql(stmt: str):
        statements.append(stmt)
        upper = stmt.upper()
        if upper.startswith("INSERT INTO CAT.SCH.DEFICIENCY_KB"):
            n = _tuple_count(stmt)
            state["deficiency_kb"] += n
            state["max_id"] += n
            return {}
        if upper.startswith("INSERT INTO CAT.SCH.DEFICIENCY_EMBEDDINGS"):
            state["deficiency_embeddings"] += _tuple_count(stmt)
            return {}
        if "COUNT(*)" in upper and "DEFICIENCY_EMBEDDINGS" in upper:
            return _fake_result(["n"], [[str(state["deficiency_embeddings"])]])
        if "COUNT(*)" in upper and "DEFICIENCY_KB" in upper:
            return _fake_result(["n", "max_id"], [[str(state["deficiency_kb"]), str(state["max_id"])]])
        if "RESPONSE_DATE" in upper and "SELECT" in upper:
            return _fake_result(["response_date"], [[None]])
        if upper.startswith("SHOW CREATE TABLE"):
            return _fake_result(["createtab_stmt"], [[state["ddl"]]])
        return {}

    monkeypatch.setattr(delta_mod, "_run_sql", fake_run_sql)
    monkeypatch.setattr(kb, "_run_sql", fake_run_sql)
    monkeypatch.setattr(delta_mod, "_table", lambda name: f"cat.sch.{name}")
    monkeypatch.setattr(kb, "_table", lambda name: f"cat.sch.{name}")
    return statements


def test_append_databricks_refuses_an_identity_id_column_before_writing_anything(dbx):
    """The real defpredict.main.deficiency_kb declares
    `id BIGINT GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1)`, so Delta rejects the
    explicit ids this writer must assign. Without this pre-flight the FIRST batch fails with
    DELTA_IDENTITY_COLUMNS_EXPLICIT_INSERT_NOT_SUPPORTED -- and on a different batch boundary
    some rows could already have landed in a shared table. Identity values are never reused, so
    a speculative attempt permanently burns the id range it fails to claim.
    """
    dbx_state["ddl"] = (
        "CREATE TABLE cat.sch.deficiency_kb (\n"
        "  id BIGINT GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1),\n"
        "  anda_number STRING COLLATE UTF8_BINARY)"
    )

    with pytest.raises(RuntimeError) as exc:
        kb.append_databricks([{c: "x" for c in _KB_COLUMNS}], expect_before=500)

    assert "IDENTITY" in str(exc.value)
    assert not [s for s in dbx if s.startswith("INSERT INTO")], "wrote rows despite the guard"


def test_identity_columns_parses_the_generated_always_marker(dbx):
    dbx_state["ddl"] = (
        "CREATE TABLE cat.sch.deficiency_kb (\n"
        "  id BIGINT GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1),\n"
        "  record_id BIGINT,\n"
        "  anda_number STRING)"
    )
    assert kb._identity_columns("cat.sch.deficiency_kb") == {"id"}


def test_append_databricks_assigns_ids_from_max_plus_one_in_list_order(dbx):
    rows = [{**{c: "" for c in _KB_COLUMNS}, "deficiency_text": f"d{i}"} for i in range(3)]
    report = kb.append_databricks(rows, expect_before=500)

    assert report["before"] == 500
    assert report["appended"] == 3
    assert report["after"] == 503
    assert report["ids"] == [501, 502, 503]

    inserts = [s for s in dbx if s.startswith("INSERT INTO cat.sch.deficiency_kb")]
    assert len(inserts) == 1
    body = inserts[0]
    # ids render as bare bigints, in list order, each next to its own row's text
    assert body.index("501") < body.index("502") < body.index("503")
    assert body.index("'d0'") < body.index("'d1'") < body.index("'d2'")


def test_append_databricks_refuses_when_before_count_disagrees(dbx):
    with pytest.raises(RuntimeError):
        kb.append_databricks([{c: "x" for c in _KB_COLUMNS}], expect_before=1234)
    assert not [s for s in dbx if s.startswith("INSERT INTO")]


def test_append_embeddings_uses_build_index_text_and_matching_record_ids(dbx, monkeypatch):
    seen: list[list[str]] = []

    def fake_embed(texts, **kwargs):
        seen.append(list(texts))
        return np.zeros((len(texts), 4), dtype=np.float32)

    monkeypatch.setattr("retrieval.vector_search.embed_texts", fake_embed)

    rows = [{
        **{c: "" for c in _KB_COLUMNS},
        "product_name": "Widget", "deficiency_type": "Stability",
        "cmc_section": "Drug Product", "deficiency_text": "text one",
    }]
    report = kb.append_embeddings_databricks(rows, ids=[501], expect_before=500)

    # notebooks/build_index.py's exact join -- the embedding text must match or the two indices
    # describe different vectors for the same record
    assert seen == [["Widget | Stability | Drug Product | text one"]]
    assert report["appended"] == 1
    assert report["after"] == 501
    inserts = [s for s in dbx if s.startswith("INSERT INTO cat.sch.deficiency_embeddings")]
    assert len(inserts) == 1
    assert "501" in inserts[0]
    assert "[0.0, 0.0, 0.0, 0.0]" in inserts[0]
