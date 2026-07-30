# Phase 0 — Plan-Checker Notes (apply during execution)

Plans **PASSED** verification (no blockers). The following 5 warnings were deferred to execution (user decision: commit-as-is, fix-at-execution). The executor of `/gsd-execute-phase 0` MUST apply W1, W2, W3, W5. W4 is handled by isolated-worktree execution.

Priority order: **W1 and W2 first** — this phase is the measurement instrument every later phase is graded against, so its metrics and ground truth must be real and canonical.

## W1 — Make `anchor_rate` a real number, not a permanent "n/a" sentinel  (plans 00-03, 00-04)
`anchor_rate` is one of the 5 SC2 per-stage metrics and IS computable at Phase 0 with no LLM. But `score` (00-04) and baseline generation (00-04) both call `compute_metrics` WITHOUT `source_text`, so it renders `"n/a_no_source"` in tests, the CI path, and the committed baseline.
**Fix:** in `score` + baseline generation, parse the non-held-out PDF once (`extract_pdf` → join block text + table-cell text) and pass it as `source_text` to `compute_metrics` so `anchor_rate` records a real number.

## W2 — Make the 28-item ground-truth set canonical  (plan 00-01, Task 2)
`gt_A(14) + gt_B(9) + gt_C(7) = 30` already exceeds the pinned target of 28 before any `gt_D` items. Acceptance pins count=28 / families=4 / tp_required=2 (anchors `11477` / `0.15` — solid), but the identity/family of the 26 non-hit items is soft, so per-family denominators are fuzzy.
**Fix:** add an explicit 30→28 reconciliation — identify the cross-file duplicate(s) within A/B/C (checker suspects `gt_D` Finding 1 = C-01, and a Table-19 overlap with `gt_C`) and enumerate the final 28 with each item's gt-source + family mapping.

## W3 — Surface all 5 per-stage metrics in CLI output  (plan 00-03, Task 3)
`format_table` renders only the by-family table; SC2 requires all 5 per-stage metrics (parse_fidelity, anchor_rate, retrieval_recall_at_k, verifier, + end-to-end) reported SEPARATELY. They exist in `metrics.json` but a human running `score` may not see them.
**Fix:** have `format_table` (or `score` stdout) also print the 4 per-stage metric rows.

## W4 — Wave-2 concurrency (handled by execution isolation)
Plan 03 reads `documents.json` which Plan 02 writes (append). They share no written file and 03's assertions are doc_id-scoped (order-independent), but a truly concurrent run risks a torn read.
**Fix:** confirm 00-02 and 00-03 run in separate worktrees (standard GSD isolated execution). No plan change needed.

## W5 — Include table cells in the held-out anchor-resolution check  (plan 00-02, Task 2)
The anchor-resolution acceptance command concatenates only `blocks[].text`, not `tables[]` cells. For the heavily-tabular 32s41 spec PDF, the natural deficiency anchors (spec-limit cells) live in tables and won't resolve — pushing the executor to the synthetic fallback and weakening the "real held-out corpus" intent.
**Fix:** extend the acceptance command's text join to also include table-cell text (`d['pages'][*]['tables']`).

---
*Source: gsd-plan-checker verification of Phase 0 plans (2026-07-30). Verdict: PASSED with 5 warnings, 0 blockers.*
