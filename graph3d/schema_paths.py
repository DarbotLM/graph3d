"""Schema-path extraction helpers for JSON schemas and SQLite databases."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import urllib.parse
from pathlib import Path
from typing import Any

from graph3d.security import sanitize_label, sanitize_metadata


MAX_JSON_SCHEMA_NODES = 2_000
MAX_SQLITE_ROWS_PER_TABLE = 100
MAX_SQLITE_CELL_CHARS = 2_048
_SQLITE_HEADER = b"SQLite format 3\x00"

_ID_SAFE_RE = re.compile(r"[^\w]+", re.UNICODE)
_JSON_SCHEMA_HINT_KEYS = frozenset({
    "$schema",
    "$defs",
    "definitions",
    "properties",
    "required",
    "type",
    "oneOf",
    "anyOf",
    "allOf",
    "items",
    "inputSchema",
    "outputSchema",
    "parameters",
})


def _make_id(*parts: str) -> str:
    text = "_".join(str(p).strip("_.") for p in parts if p)
    text = _ID_SAFE_RE.sub("_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_").casefold()


def _hash_id(prefix: str, *parts: str) -> str:
    raw = "\0".join(str(part) for part in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8', errors='replace')).hexdigest()[:16]}"


def _add_node(
    nodes: list[dict],
    seen: set[str],
    *,
    node_id: str,
    label: str,
    file_type: str,
    source_file: str,
    source_location: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if not node_id or node_id in seen:
        return
    seen.add(node_id)
    node = {
        "id": node_id,
        "label": sanitize_label(label),
        "file_type": file_type,
        "source_file": source_file,
        "source_location": source_location,
    }
    if metadata:
        node["metadata"] = sanitize_metadata(metadata)
    nodes.append(node)


def _add_edge(
    edges: list[dict],
    seen: set[tuple[str, str, str, str | None]],
    *,
    source: str,
    target: str,
    relation: str,
    source_file: str,
    source_location: str | None = None,
    context: str | None = None,
) -> None:
    if not source or not target or source == target:
        return
    key = (source, target, relation, context)
    if key in seen:
        return
    seen.add(key)
    edge = {
        "source": source,
        "target": target,
        "relation": relation,
        "confidence": "EXTRACTED",
        "confidence_score": 1.0,
        "source_file": source_file,
        "source_location": source_location,
        "weight": 1.0,
    }
    if context:
        edge["context"] = context
    edges.append(edge)


def _path_parts(path: str) -> list[str]:
    if path == "$":
        return ["$"]
    parts = ["$"]
    rest = path[2:] if path.startswith("$.") else path
    for part in rest.split("."):
        if part:
            parts.append(part)
    return parts


def _schema_kind(path: str, value: Any) -> str:
    parts = _path_parts(path)
    last = parts[-1].lower()
    previous = parts[-2].lower() if len(parts) > 1 else ""
    if last in {"$defs", "definitions"}:
        return "schema_definitions"
    if previous in {"$defs", "definitions"}:
        return "schema_definition"
    if previous == "properties":
        return "schema_property"
    if last in {"oneof", "anyof", "allof"}:
        return "schema_union"
    if last == "$ref":
        return "schema_ref"
    if last == "type":
        return "schema_type"
    if isinstance(value, list):
        return "schema_array"
    if isinstance(value, dict):
        return "schema_object"
    return "schema_value"


def _json_schema_pattern(path: str) -> str:
    parts = _path_parts(path)
    normalized: list[str] = []
    wildcard_next_after = {"properties", "definitions", "$defs"}
    for idx, part in enumerate(parts):
        prev = parts[idx - 1] if idx else ""
        if prev in wildcard_next_after:
            normalized.append("*")
        elif part.isdigit():
            normalized.append("[]")
        else:
            normalized.append(part)
    return ".".join(normalized)


def _terminal_key(path: str) -> str:
    parts = [p for p in _path_parts(path) if p not in {"$", "[]"}]
    if not parts:
        return "$"
    return parts[-1]


def _add_pattern_nodes(
    *,
    nodes: list[dict],
    edges: list[dict],
    seen_nodes: set[str],
    seen_edges: set[tuple[str, str, str, str | None]],
    path_node_id: str,
    schema_path: str,
    source_file: str,
    source_location: str | None,
    pattern: str | None = None,
) -> None:
    path_pattern = pattern or _json_schema_pattern(schema_path)
    pattern_id = _hash_id("schema_pattern", path_pattern)
    _add_node(
        nodes,
        seen_nodes,
        node_id=pattern_id,
        label=path_pattern,
        file_type="schema",
        source_file=source_file,
        source_location=source_location,
        metadata={"schema_kind": "schema_pattern", "schema_pattern": path_pattern},
    )
    _add_edge(
        edges,
        seen_edges,
        source=path_node_id,
        target=pattern_id,
        relation="matches_schema_pattern",
        source_file=source_file,
        source_location=source_location,
        context="schema_path",
    )

    terminal = _terminal_key(schema_path)
    terminal_norm = _make_id(terminal)
    if terminal_norm:
        terminal_id = _hash_id("schema_terminal", terminal_norm)
        _add_node(
            nodes,
            seen_nodes,
            node_id=terminal_id,
            label=terminal,
            file_type="schema",
            source_file=source_file,
            source_location=source_location,
            metadata={"schema_kind": "schema_terminal", "terminal_key": terminal_norm},
        )
        _add_edge(
            edges,
            seen_edges,
            source=path_node_id,
            target=terminal_id,
            relation="matches_schema_terminal",
            source_file=source_file,
            source_location=source_location,
            context="schema_path",
        )


def looks_like_json_schema_doc(value: Any) -> bool:
    """Return True when a JSON object looks like a schema or tool schema."""
    if not isinstance(value, dict):
        return False
    if any(key in value for key in _JSON_SCHEMA_HINT_KEYS):
        return True
    for nested_key in ("inputSchema", "outputSchema", "parameters"):
        nested = value.get(nested_key)
        if isinstance(nested, dict) and any(key in nested for key in _JSON_SCHEMA_HINT_KEYS):
            return True
    return False


def extract_json_schema_paths(
    path: Path,
    *,
    file_node_id: str | None = None,
    source_file: str | None = None,
    max_nodes: int = MAX_JSON_SCHEMA_NODES,
) -> dict:
    """Extract schema-path nodes from a JSON Schema or MCP-style tool schema."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"nodes": [], "edges": [], "error": f"json schema read error: {exc}"}
    if not looks_like_json_schema_doc(doc):
        return {"nodes": [], "edges": []}

    str_path = source_file or str(path)
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str, str, str | None]] = set()
    path_to_node: dict[str, str] = {}

    def add_schema_path(schema_path: str, value: Any, parent_path: str | None) -> str | None:
        if len(path_to_node) >= max_nodes:
            return None
        node_id = _hash_id("schema_path", str_path, schema_path)
        kind = _schema_kind(schema_path, value)
        metadata: dict[str, Any] = {
            "schema_kind": kind,
            "schema_path": schema_path,
            "schema_pattern": _json_schema_pattern(schema_path),
        }
        if isinstance(value, (str, int, float, bool)) or value is None:
            metadata["value"] = value
        elif isinstance(value, list):
            metadata["item_count"] = len(value)
        elif isinstance(value, dict):
            metadata["key_count"] = len(value)
        _add_node(
            nodes,
            seen_nodes,
            node_id=node_id,
            label=schema_path,
            file_type="schema",
            source_file=str_path,
            metadata=metadata,
        )
        path_to_node[schema_path] = node_id
        if parent_path and parent_path in path_to_node:
            _add_edge(
                edges,
                seen_edges,
                source=path_to_node[parent_path],
                target=node_id,
                relation="contains_schema_path",
                source_file=str_path,
                context="schema_path",
            )
        elif file_node_id:
            _add_edge(
                edges,
                seen_edges,
                source=file_node_id,
                target=node_id,
                relation="contains_schema_path",
                source_file=str_path,
                context="schema_path",
            )
        _add_pattern_nodes(
            nodes=nodes,
            edges=edges,
            seen_nodes=seen_nodes,
            seen_edges=seen_edges,
            path_node_id=node_id,
            schema_path=schema_path,
            source_file=str_path,
            source_location=None,
        )
        if isinstance(value, str) and _terminal_key(schema_path) == "type":
            type_id = _hash_id("schema_type", value)
            _add_node(
                nodes,
                seen_nodes,
                node_id=type_id,
                label=value,
                file_type="schema",
                source_file=str_path,
                metadata={"schema_kind": "schema_type", "type": value},
            )
            _add_edge(
                edges,
                seen_edges,
                source=node_id,
                target=type_id,
                relation="has_schema_type",
                source_file=str_path,
                context="schema_path",
            )
        if isinstance(value, str) and _terminal_key(schema_path) == "$ref":
            ref_id = _hash_id("schema_ref", value)
            _add_node(
                nodes,
                seen_nodes,
                node_id=ref_id,
                label=value,
                file_type="schema",
                source_file=str_path,
                metadata={"schema_kind": "schema_ref_target", "ref": value},
            )
            _add_edge(
                edges,
                seen_edges,
                source=node_id,
                target=ref_id,
                relation="references_schema",
                source_file=str_path,
                context="schema_path",
            )
        return node_id

    def walk(value: Any, schema_path: str, parent_path: str | None, depth: int) -> None:
        if depth > 12 or len(path_to_node) >= max_nodes:
            return
        add_schema_path(schema_path, value, parent_path)
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, f"{schema_path}.{key}" if schema_path != "$" else f"$.{key}", schema_path, depth + 1)
        elif isinstance(value, list):
            for idx, child in enumerate(value[:100]):
                walk(child, f"{schema_path}.{idx}", schema_path, depth + 1)

    walk(doc, "$", None, 0)
    return {"nodes": nodes, "edges": edges}


def _sqlite_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return f"blob:{len(value)} bytes"
    if isinstance(value, str) and len(value) > MAX_SQLITE_CELL_CHARS:
        return value[:MAX_SQLITE_CELL_CHARS]
    return value


def _sqlite_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def extract_sqlite_schema(
    path: Path,
    *,
    include_content: bool = True,
    max_rows_per_table: int | None = MAX_SQLITE_ROWS_PER_TABLE,
) -> dict:
    """Extract SQLite schema, indexes, views, and bounded row values from a DB file."""
    str_path = str(path)
    file_node_id = _make_id(str_path)
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str, str, str | None]] = set()

    try:
        with path.open("rb") as handle:
            if handle.read(len(_SQLITE_HEADER)) != _SQLITE_HEADER:
                return {"nodes": [], "edges": [], "error": "not a sqlite database"}
    except OSError as exc:
        return {"nodes": [], "edges": [], "error": f"sqlite read error: {exc}"}

    _add_node(
        nodes,
        seen_nodes,
        node_id=file_node_id,
        label=path.name,
        file_type="data",
        source_file=str_path,
        metadata={"schema_kind": "sqlite_database", "schema_path": "sqlite"},
    )

    try:
        db_uri = "file:" + urllib.parse.quote(path.resolve().as_posix(), safe="/:") + "?mode=ro&immutable=1"
        con = sqlite3.connect(db_uri, uri=True)
        con.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        return {"nodes": nodes, "edges": edges, "error": f"sqlite open error: {exc}"}

    try:
        rows = con.execute(
            "SELECT name, type, sql FROM sqlite_master "
            "WHERE type IN ('table','index','view','trigger') "
            "AND name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
        fts_shadow_prefixes: set[str] = set()
        for row in rows:
            sql = row["sql"] or ""
            if row["type"] == "table" and "VIRTUAL TABLE" in sql.upper() and "USING FTS" in sql.upper():
                fts_shadow_prefixes.add(f"{row['name']}_")
        rows = [
            row for row in rows
            if row["sql"] is not None
            and not any(str(row["name"]).startswith(prefix) for prefix in fts_shadow_prefixes)
        ]
        table_names = [
            row["name"] for row in rows
            if row["type"] == "table" and not str(row["name"]).startswith("sqlite_")
        ]

        for row in rows:
            obj_name = str(row["name"])
            obj_type = str(row["type"])
            obj_path = f"sqlite.{obj_type}s.{obj_name}"
            obj_id = _hash_id("sqlite_object", str_path, obj_type, obj_name)
            _add_node(
                nodes,
                seen_nodes,
                node_id=obj_id,
                label=f"{obj_name} ({obj_type})",
                file_type="schema",
                source_file=str_path,
                metadata={
                    "schema_kind": f"sqlite_{obj_type}",
                    "schema_path": obj_path,
                    "sql": row["sql"] or "",
                },
            )
            _add_edge(
                edges,
                seen_edges,
                source=file_node_id,
                target=obj_id,
                relation="contains",
                source_file=str_path,
                context="schema",
            )
            _add_pattern_nodes(
                nodes=nodes,
                edges=edges,
                seen_nodes=seen_nodes,
                seen_edges=seen_edges,
                path_node_id=obj_id,
                schema_path=obj_path,
                source_file=str_path,
                source_location=None,
                pattern=f"sqlite.{obj_type}s.*",
            )

            if obj_type != "table":
                continue

            try:
                columns = con.execute(f"PRAGMA table_info({_sqlite_ident(obj_name)})").fetchall()
            except sqlite3.Error:
                columns = []
            for col in columns:
                col_name = str(col["name"])
                col_path = f"sqlite.tables.{obj_name}.columns.{col_name}"
                col_id = _hash_id("sqlite_column", str_path, obj_name, col_name)
                _add_node(
                    nodes,
                    seen_nodes,
                    node_id=col_id,
                    label=f"{obj_name}.{col_name}",
                    file_type="schema",
                    source_file=str_path,
                    metadata={
                        "schema_kind": "sqlite_column",
                        "schema_path": col_path,
                        "table": obj_name,
                        "column": col_name,
                        "type": col["type"],
                        "notnull": bool(col["notnull"]),
                        "default": col["dflt_value"],
                        "primary_key": bool(col["pk"]),
                    },
                )
                _add_edge(
                    edges,
                    seen_edges,
                    source=obj_id,
                    target=col_id,
                    relation="has_column",
                    source_file=str_path,
                    context="schema",
                )
                _add_pattern_nodes(
                    nodes=nodes,
                    edges=edges,
                    seen_nodes=seen_nodes,
                    seen_edges=seen_edges,
                    path_node_id=col_id,
                    schema_path=col_path,
                    source_file=str_path,
                    source_location=None,
                    pattern="sqlite.tables.*.columns.*",
                )

        if include_content:
            for table in table_names:
                table_id = _hash_id("sqlite_object", str_path, "table", table)
                limit_sql = "" if max_rows_per_table is None else f" LIMIT {int(max_rows_per_table)}"
                try:
                    content_rows = con.execute(f"SELECT rowid, * FROM {_sqlite_ident(table)}{limit_sql}").fetchall()
                except sqlite3.Error:
                    continue
                for idx, content_row in enumerate(content_rows, start=1):
                    values = {key: _sqlite_value(content_row[key]) for key in content_row.keys()}
                    row_label = f"{table} row {values.get('rowid', idx)}"
                    row_id = _hash_id("sqlite_row", str_path, table, json.dumps(values, sort_keys=True, default=str))
                    _add_node(
                        nodes,
                        seen_nodes,
                        node_id=row_id,
                        label=row_label,
                        file_type="data",
                        source_file=str_path,
                        metadata={
                            "schema_kind": "sqlite_row",
                            "schema_path": f"sqlite.tables.{table}.rows.{values.get('rowid', idx)}",
                            "table": table,
                            "values": values,
                            "content_capture": "bounded_full_values",
                        },
                    )
                    _add_edge(
                        edges,
                        seen_edges,
                        source=table_id,
                        target=row_id,
                        relation="has_row",
                        source_file=str_path,
                        context="data",
                    )
    finally:
        con.close()

    return {"nodes": nodes, "edges": edges}
