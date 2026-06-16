from __future__ import annotations

import builtins
import json
import sqlite3
from pathlib import Path
from unittest import mock

from graph3d.build import build_from_json
from graph3d.detect import FileType, classify_file, count_words
from graph3d.extract import _make_id, extract, extract_json
from graph3d.schema_paths import extract_json_schema_paths, extract_sqlite_schema
from graph3d.validate import validate_extraction


def _schema_paths(result: dict) -> set[str]:
    paths = set()
    for node in result["nodes"]:
        metadata = node.get("metadata", {})
        path = metadata.get("schema_path")
        if path:
            paths.add(path)
    return paths


def _nodes_by_kind(result: dict, kind: str) -> list[dict]:
    return [
        node for node in result["nodes"]
        if node.get("metadata", {}).get("schema_kind") == kind
    ]


def test_json_schema_paths_are_added_to_json_extraction(tmp_path):
    schema_file = tmp_path / "session.schema.json"
    schema_file.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "definitions": {
                    "SessionEvent": {
                        "type": "object",
                        "properties": {
                            "session_id": {"type": "string"},
                            "turn_index": {"type": "integer"},
                        },
                        "required": ["session_id"],
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    result = extract_json(schema_file)

    paths = _schema_paths(result)
    assert "$.definitions.SessionEvent.properties.session_id.type" in paths
    assert "$.definitions.SessionEvent.properties.turn_index.type" in paths
    assert any(edge["relation"] == "has_schema_type" for edge in result["edges"])
    assert any(edge["relation"] == "matches_schema_terminal" for edge in result["edges"])

    errors = validate_extraction(result)
    assert not [error for error in errors if "does not match any node id" not in error]
    graph = build_from_json(result)
    assert graph.number_of_nodes() > 0


def test_json_schema_helper_ignores_plain_json(tmp_path):
    plain = tmp_path / "package.json"
    plain.write_text(json.dumps({"name": "demo", "version": "1.0.0"}), encoding="utf-8")

    result = extract_json_schema_paths(plain)

    assert result == {"nodes": [], "edges": []}


def test_sqlite_schema_extracts_tables_columns_and_rows(tmp_path):
    db_path = tmp_path / "session-store.db"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, summary TEXT)")
    con.execute(
        "CREATE TABLE turns (session_id TEXT NOT NULL, turn_index INTEGER, user_message TEXT)"
    )
    con.execute("CREATE INDEX idx_turns_session ON turns(session_id)")
    con.execute("INSERT INTO sessions(id, summary) VALUES ('s1', 'hello world')")
    con.execute("INSERT INTO turns(session_id, turn_index, user_message) VALUES ('s1', 1, 'hi')")
    con.commit()
    con.close()

    result = extract_sqlite_schema(db_path)

    labels = {node["label"] for node in result["nodes"]}
    assert "sessions (table)" in labels
    assert "turns (table)" in labels
    assert "sessions.summary" in labels
    assert "idx_turns_session (index)" in labels
    assert any(edge["relation"] == "has_column" for edge in result["edges"])
    assert any(edge["relation"] == "has_row" for edge in result["edges"])

    row_nodes = _nodes_by_kind(result, "sqlite_row")
    assert row_nodes
    assert any(
        node.get("metadata", {}).get("values", {}).get("summary") == "hello world"
        for node in row_nodes
    )

    errors = validate_extraction(result)
    assert not [error for error in errors if "does not match any node id" not in error]


def test_sqlite_non_database_returns_error(tmp_path):
    db_path = tmp_path / "not-real.db"
    db_path.write_bytes(b"NOTSQLITE")

    result = extract_sqlite_schema(db_path)

    assert result["nodes"] == []
    assert result["edges"] == []
    assert "not a sqlite database" in result["error"]


def test_sqlite_file_node_uses_extract_path_id(tmp_path):
    db_path = tmp_path / "session-store.db"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
    con.commit()
    con.close()

    result = extract_sqlite_schema(db_path)

    assert result["nodes"][0]["id"] == _make_id(str(db_path))


def test_sqlite_fts_shadow_tables_are_excluded(tmp_path):
    db_path = tmp_path / "search.db"
    con = sqlite3.connect(db_path)
    con.execute("CREATE VIRTUAL TABLE search_index USING fts5(content)")
    con.execute("INSERT INTO search_index(content) VALUES ('hello world')")
    con.commit()
    con.close()

    result = extract_sqlite_schema(db_path)

    labels = {node["label"] for node in result["nodes"]}
    assert "search_index (table)" in labels
    assert not any("search_index_data" in label for label in labels)
    assert not any("search_index_idx" in label for label in labels)
    assert not any("search_index_content" in label for label in labels)
    assert not any("search_index_docsize" in label for label in labels)
    assert not any("search_index_config" in label for label in labels)


def test_sqlite_blob_values_are_not_decoded(tmp_path):
    db_path = tmp_path / "embeddings.db"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE embeddings (id TEXT, embedding BLOB)")
    con.execute("INSERT INTO embeddings(id, embedding) VALUES (?, ?)", ("e1", b"\x00secret-bytes\xff"))
    con.commit()
    con.close()

    result = extract_sqlite_schema(db_path)
    payload = json.dumps(result, ensure_ascii=False)

    assert "secret-bytes" not in payload
    assert "blob:" in payload


def test_sqlite_row_content_is_capped_and_sanitized(tmp_path):
    db_path = tmp_path / "turns.db"
    long_message = "hello\x00" + ("x" * 5_000)
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE turns (id INTEGER PRIMARY KEY, user_message TEXT)")
    con.execute("INSERT INTO turns(user_message) VALUES (?)", (long_message,))
    con.commit()
    con.close()

    result = extract_sqlite_schema(db_path)

    row = _nodes_by_kind(result, "sqlite_row")[0]
    captured = row["metadata"]["values"]["user_message"]
    assert "\x00" not in captured
    assert len(captured) <= 512


def test_sqlite_row_cap_is_enforced(tmp_path):
    db_path = tmp_path / "many.db"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, type TEXT)")
    con.executemany("INSERT INTO events(type) VALUES (?)", [(f"event-{i}",) for i in range(20)])
    con.commit()
    con.close()

    result = extract_sqlite_schema(db_path, max_rows_per_table=3)

    assert len(_nodes_by_kind(result, "sqlite_row")) == 3


def test_extract_dispatches_sqlite_files(tmp_path):
    db_path = tmp_path / "events.sqlite"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, type TEXT)")
    con.execute("INSERT INTO events(type) VALUES ('assistant.message')")
    con.commit()
    con.close()

    result = extract([db_path], cache_root=tmp_path, parallel=False)

    assert any(
        node.get("metadata", {}).get("schema_kind") == "sqlite_table"
        for node in result["nodes"]
    )
    assert any(node["file_type"] == "data" for node in result["nodes"])


def test_sqlite_dispatch_does_not_require_sql_text_extra(tmp_path):
    db_path = tmp_path / "events.sqlite"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, type TEXT)")
    con.commit()
    con.close()

    real_import = builtins.__import__

    def patched_import(name, *args, **kwargs):
        if name == "tree_sitter_sql":
            raise ImportError("optional sql extra absent")
        return real_import(name, *args, **kwargs)

    with mock.patch("builtins.__import__", side_effect=patched_import):
        result = extract([db_path], cache_root=tmp_path, parallel=False)

    assert any(
        node.get("metadata", {}).get("schema_kind") == "sqlite_table"
        for node in result["nodes"]
    )


def test_detect_classifies_sqlite_as_structural_code():
    assert classify_file(Path("session-store.db")) == FileType.CODE
    assert classify_file(Path("events.sqlite")) == FileType.CODE


def test_detect_counts_sqlite_as_zero_words(tmp_path):
    db_path = tmp_path / "session-store.db"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, summary TEXT)")
    con.execute("INSERT INTO sessions(id, summary) VALUES ('s1', 'many words in content')")
    con.commit()
    con.close()

    assert count_words(db_path) == 0


def test_schema_terminal_correlates_json_and_sqlite(tmp_path):
    schema_file = tmp_path / "api.schema.json"
    schema_file.write_text(
        json.dumps({"type": "object", "properties": {"session_id": {"type": "string"}}}),
        encoding="utf-8",
    )
    db_path = tmp_path / "session.db"
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE turns (session_id TEXT NOT NULL)")
    con.commit()
    con.close()

    json_result = extract_json(schema_file)
    sqlite_result = extract_sqlite_schema(db_path, include_content=False)

    json_terminals = {
        node["id"] for node in _nodes_by_kind(json_result, "schema_terminal")
        if node["label"] == "session_id"
    }
    sqlite_terminals = {
        node["id"] for node in _nodes_by_kind(sqlite_result, "schema_terminal")
        if node["label"] == "session_id"
    }

    assert json_terminals
    assert json_terminals == sqlite_terminals
