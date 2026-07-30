"""Thin CLI shell: `python -m ingest <dir>` (D-11).

All logic lives in `ingest_corpus`; this shell only parses argv, calls the library, and prints a
summary (per-status counts + escalation rate). Evals and later phases import the library, not the CLI.
"""
from __future__ import annotations

import argparse

from ingest.corpus import ingest_corpus


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ingest",
        description="Ingest an arbitrary nested directory of PDF+DOCX into a corpus index + coverage manifest.",
    )
    parser.add_argument("dir", help="Root directory to ingest (walked recursively, uncapped).")
    parser.add_argument("--model", default=None, help="Optional classifier LLM model id.")
    parser.add_argument("--cache-dir", dest="cache_dir", default=None,
                        help="Parse-cache directory (default: data/ingest_cache).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    kwargs: dict = {"model": args.model}
    if args.cache_dir:
        kwargs["cache_dir"] = args.cache_dir
    index = ingest_corpus(args.dir, **kwargs)
    print(f"ingested {len(index.manifest.documents)} document(s) from {args.dir}")
    print(f"status counts: {index.manifest.counts}")
    print(f"escalation rate: {index.manifest.escalation_rate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
