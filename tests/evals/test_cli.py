"""Tests for the eval-harness CI-style CLI (`python -m evals.run`, EVAL-03).

`score`/`gate` never hit an LLM or the network -- these tests exercise exactly those two
subcommands. Live `run` mode (real parse + detect) is exercised manually / in the nightly job,
per the plan's own scope, so it has no test here.

The `gate` tests below pass an explicit `--baseline` (a self-contained temp file) rather than
relying on the default `src/evals/baseline/recall_by_family.json` path: this file is Plan 00-04
Task 3's own deliverable, created *after* this CLI, so a test of the CLI's *mechanics* must not
depend on it. The committed baseline's own found-set is pinned by `tests/evals/test_gate.py`
(Task 3), which runs `gate` against the real default path once that file exists.
"""
from __future__ import annotations

import json

from evals.capture import golden_report
from evals.run import build_parser, main

GOLDEN_CAPTURED = "src/evals/dataset/golden/mvr1381_run3.json"
FOUR_FAMILIES = {
    "absence_of_evidence",
    "derivation_plausibility",
    "cross_reference_integrity",
    "regulatory_framing",
}


def _write_baseline(tmp_path, found_set: list[str]):
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({"found_set": found_set}))
    return path


class TestHelp:
    def test_help_lists_all_three_subcommands(self, capsys):
        code = None
        try:
            main(["--help"])
        except SystemExit as exc:
            code = exc.code
        assert code == 0

        out = capsys.readouterr().out
        assert "score" in out
        assert "gate" in out
        assert "run" in out

    def test_build_parser_returns_an_argument_parser(self):
        parser = build_parser()
        assert parser.prog == "python -m evals.run"


class TestScoreSubcommand:
    def test_score_on_golden_captured_report_exits_zero_and_writes_four_families(self, tmp_path, capsys):
        out_path = tmp_path / "metrics.json"
        code = main(["score", "--captured", GOLDEN_CAPTURED, "--out", str(out_path)])
        assert code == 0

        printed = capsys.readouterr().out
        assert "End-to-end by failure family" in printed

        written = json.loads(out_path.read_text())
        assert set(written["end_to_end_by_family"]) == FOUR_FAMILIES
        assert set(written["recall_by_family"]) == FOUR_FAMILIES

    def test_score_defaults_to_the_golden_fixture_without_captured(self, tmp_path):
        out_path = tmp_path / "metrics.json"
        code = main(["score", "--out", str(out_path)])
        assert code == 0

        written = json.loads(out_path.read_text())
        assert written["end_to_end"]["tp"] == 2
        assert written["end_to_end"]["fn"] == 26


class TestGateSubcommand:
    def test_gate_passes_when_every_baseline_id_is_still_matched(self, tmp_path, capsys):
        baseline_path = _write_baseline(tmp_path, ["C-01", "C-02"])
        code = main(["gate", "--captured", GOLDEN_CAPTURED, "--baseline", str(baseline_path)])
        assert code == 0
        assert "GATE OK" in capsys.readouterr().out

    def test_gate_fails_and_names_the_lost_id_when_a_tp_disappears(self, tmp_path, capsys):
        original = golden_report()
        doctored_faults = [f for f in original.faults if "11477" not in f.evidence]
        doctored = original.model_copy(update={"faults": doctored_faults})
        doctored_path = tmp_path / "doctored.json"
        doctored_path.write_text(doctored.model_dump_json())

        baseline_path = _write_baseline(tmp_path, ["C-01", "C-02"])
        code = main(
            ["gate", "--captured", str(doctored_path), "--baseline", str(baseline_path)]
        )

        assert code == 1
        out = capsys.readouterr().out
        assert "GATE FAILED" in out
        assert "C-01" in out
