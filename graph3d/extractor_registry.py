"""Small registry for mapping files to structural extractors.

The registry is intentionally lightweight: legacy callers can keep using the
plain suffix dispatch table while new ingesters can register either suffixes or
filename predicates for cases where an extension is too broad.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any


Extractor = Callable[[Path], Any]
FilenamePredicate = Callable[[Path], bool]


@dataclass(frozen=True)
class FilenameRoute:
    """A filename predicate route checked before suffix lookup."""

    name: str
    predicate: FilenamePredicate
    extractor: Extractor


class ExtractorRegistry:
    """Lookup table for suffix and filename-predicate extractors."""

    def __init__(self, suffix_extractors: MutableMapping[str, Extractor] | None = None) -> None:
        self._suffix_extractors: MutableMapping[str, Extractor] = (
            suffix_extractors if suffix_extractors is not None else {}
        )
        self._filename_routes: list[FilenameRoute] = []

    def register_suffix(self, suffix: str, extractor: Extractor) -> Extractor:
        """Register ``extractor`` for ``suffix`` and return it.

        ``suffix`` may be provided with or without the leading dot. Case is
        preserved to match ``Path.suffix`` and the historical _DISPATCH behavior.
        """
        self._suffix_extractors[_normalize_suffix(suffix)] = extractor
        return extractor

    def register_filename_predicate(
        self,
        predicate: FilenamePredicate,
        extractor: Extractor,
        *,
        name: str | None = None,
        prepend: bool = False,
    ) -> Extractor:
        """Register ``extractor`` for paths where ``predicate(path)`` is true.

        Predicate routes are evaluated before suffix lookup, preserving special
        filename handling such as MCP config routing before generic JSON.
        """
        route = FilenameRoute(
            name=name or getattr(predicate, "__name__", "<predicate>"),
            predicate=predicate,
            extractor=extractor,
        )
        if prepend:
            self._filename_routes.insert(0, route)
        else:
            self._filename_routes.append(route)
        return extractor

    def lookup(self, path: Path) -> Extractor | None:
        """Return the extractor for ``path`` or None when unsupported."""
        path = Path(path)
        for route in self._filename_routes:
            if route.predicate(path):
                return route.extractor
        return self._suffix_extractors.get(path.suffix)

    def suffixes(self) -> Iterable[str]:
        """Return the currently registered suffixes."""
        return self._suffix_extractors.keys()

    def filename_routes(self) -> tuple[FilenameRoute, ...]:
        """Return filename predicate routes in lookup order."""
        return tuple(self._filename_routes)


def _normalize_suffix(suffix: str) -> str:
    if not suffix:
        raise ValueError("suffix must not be empty")
    return suffix if suffix.startswith(".") else f".{suffix}"
