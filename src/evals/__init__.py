"""Eval harness identity, recorded in every spike run summary (D-TEL1(i), D-GO1(iii)).

D-GO1(iii) freezes the harness, matcher and baseline that produced the 0.071 reference: any
change invalidates the comparison and requires re-baselining BEFORE the spike, never after.
These constants are the human contract; `matcher_content_sha256` (computed over match.py and
recorded in each run summary) is the thing that cannot be forgotten.
"""

# Bump on any change to the SCORING path: metrics.py / match.py / gate.py / schema.py / capture.py.
#
# `run.py`'s CLI SURFACE is deliberately EXCLUDED from the bump rule -- argument parsing, subcommand
# registration, sibling entry points. It is NOT excluded wholesale, because run.py is not purely a
# CLI shell. Two of its helpers are scoring INPUTS and are the named EXCEPTION -- editing either DOES
# require a bump:
#     _join_source_text  (run.py:60-81)   -- builds the source_text handed to compute_metrics
#     _load_source_text  (run.py:107-127) -- the lazy-import wrapper cmd_score uses for the same
# Both feed `source_text` into compute_metrics (cmd_score:139, cmd_run:280), and `source_text` is
# what `anchor_rate` is computed against. anchor_rate is a COMMITTED baseline value, reported per run
# and compared across arms, so a change to either helper silently moves a cross-arm number.
#
# Under that rule, plan 03-15 adds the `agent-run` subcommand ADDITIVELY (cmd_run, run_detection,
# _join_source_text and _load_source_text all untouched -- asserted by 03-15's acceptance criteria)
# AFTER the baseline arm has been measured, and both arms re-score through the same
# cmd_score / _load_source_text path, so no cross-arm asymmetry is introduced. Bumping for a CLI
# addition would make D-GO1(iii) read the two arms as scored under DIFFERENT harnesses and invalidate
# the comparison over a change that alters nothing about how a finding is scored.
HARNESS_VERSION = "1"
MATCHER_VERSION = "1"   # bump on any change to match.py's tokenization or matching rule
