"""The Phase-3 drive loop (AGENT-01/03/04) -- a model-driven tool loop over the six Phase-2
navigation tools plus run_oracles, with budgets, circuit breaker, diminishing-returns stop and
the AGENT-04 continuation floor enforced IN CODE, never as prompt instructions.

Mirrors `src/agents/detection/` file-for-file so the evolution is legible
(.planning/research/ARCHITECTURE.md). `agents/detection/` is left entirely intact: it is the
BASELINE ARM (D-LOOP1 requires it stay runnable; D-LOOP2 re-runs it 3x to produce the governing
reference). Nothing in this package modifies it.

The public entry point `run_review` lands in plan 03-13.
"""
