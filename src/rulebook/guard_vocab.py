"""Guard vocabulary registry (D-GRD3) — registered general-vocabulary allowlists.

The anti-overfitting NO-CONSTANT scan treats entries in these frozensets as ALLOWED
(general vocabulary, like a stopword list) and flags any OTHER inline literal
(numeric spec values, CTD section paths, doc names, batch IDs). Each entry must be:
  - A common English word or standard abbreviation with no corpus-specific semantics
  - NOT tied to any specific submission, document name, or regulatory context
  - Assertable: 'no entry is a corpus-specific token' (D-GRD3 code gate, not reviewer sign-off)

Design rule: this is a DECLARED, REVIEWED registry — any new vocabulary is added here,
not hardcoded inline in structural.py or references.py. Import as:
  from rulebook.guard_vocab import AGGREGATE_LEXICON, REFERENCE_CUE_WORDS
"""
from __future__ import annotations

# D-GRD3: General aggregate label vocabulary. These are common English words used to
# label aggregate/summary rows in tables across ALL regulatory domains (impurity tables,
# stability data, dissolution tables, bioequivalence data, etc.).
# None of these tokens is specific to any submission, doc name, or FDA form number.
AGGREGATE_LEXICON: frozenset[str] = frozenset({
    "total",
    "sum",
    "maximum",
    "max",
    "minimum",
    "min",
    "average",
    "mean",
})

# D-GRD3: General reference cue words. These are common English words/phrases used to
# introduce cross-references in regulatory documents across all submission types.
# None of these tokens is specific to any submission, section path, or document name.
REFERENCE_CUE_WORDS: frozenset[str] = frozenset({
    "see",
    "refer",
    "table",
    "section",
    "module",
    "figure",
    "appendix",
    "as described in",
    "as stated in",
    "per",
    "referenced in",
})
