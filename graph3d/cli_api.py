"""Small helpers that bridge CLI argv handling and the Python API.

This module is intentionally narrow: it exposes stable, testable helpers without
pulling large command bodies out of ``graph3d.__main__``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from graph3d.detect import _CORPUS_PROFILES, _normalise_profile


def valid_corpus_profiles() -> tuple[str, ...]:
    """Return supported corpus profile names in deterministic display order."""
    return tuple(sorted(_CORPUS_PROFILES))


def parse_corpus_profile(profile: str | None) -> str | None:
    """Normalize and validate a corpus profile name for API or CLI callers.

    ``None`` and blank strings preserve detect()'s legacy full-corpus behavior.
    Non-empty names are case-insensitive and must be one of
    :func:`valid_corpus_profiles`.
    """
    return _normalise_profile(profile)


@dataclass(frozen=True)
class ExtractProfileArgs:
    """Result of extracting ``graph3d extract`` profile flags from argv."""

    profile: str | None
    args: tuple[str, ...]


def parse_extract_profile_args(args: Sequence[str]) -> ExtractProfileArgs:
    """Extract ``--profile`` from ``graph3d extract`` args.

    Unknown arguments are preserved exactly for the existing dispatcher logic.
    If ``--profile`` appears more than once, the last value wins, matching common
    command-line override behavior.
    """
    remaining: list[str] = []
    profile: str | None = None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--profile":
            if i + 1 >= len(args) or not str(args[i + 1]).strip():
                raise ValueError("--profile requires a non-empty value")
            profile = parse_corpus_profile(args[i + 1])
            i += 2
        elif arg.startswith("--profile="):
            raw_profile = arg.split("=", 1)[1]
            if not raw_profile.strip():
                raise ValueError("--profile requires a non-empty value")
            profile = parse_corpus_profile(raw_profile)
            i += 1
        else:
            remaining.append(arg)
            i += 1
    return ExtractProfileArgs(profile=profile, args=tuple(remaining))
