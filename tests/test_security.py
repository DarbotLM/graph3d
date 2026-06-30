"""Table-driven security, validation, and filename-cap regression tests."""
from __future__ import annotations

import json
import re
import socket
import urllib.error
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import networkx as nx
import pytest

from graph3d.export import to_canvas, to_obsidian
from graph3d.security import (
    _MAX_FETCH_BYTES,
    _MAX_GRAPH_FILE_BYTES,
    _MAX_TEXT_BYTES,
    _METADATA_MAX_LIST_ITEMS,
    _METADATA_MAX_VALUE_LEN,
    _sanitize_metadata_string,
    _sanitize_metadata_value,
    check_graph_file_size_cap,
    safe_fetch,
    safe_fetch_text,
    sanitize_label,
    sanitize_metadata,
    validate_graph_path,
    validate_url,
)
from graph3d.validate import (
    GRAPH3D_EXPORT_SCHEMA_KIND,
    GRAPH3D_EXPORT_SCHEMA_VERSION,
    VALID_CONFIDENCES,
    VALID_FILE_TYPES,
    assert_valid,
    validate_extraction,
    validate_graph_export,
    validate_provenance_metadata,
    validate_relation_endpoints,
    validate_schema_path_metadata,
    validate_source_refs,
)

FIXTURES = Path(__file__).parent / "fixtures"
VALID = {
    "nodes": [
        {"id": "n1", "label": "Foo", "file_type": "code", "source_file": str(FIXTURES / "sample.py")},
        {"id": "n2", "label": "Bar", "file_type": "document", "source_file": str(FIXTURES / "sample.md")},
    ],
    "edges": [
        {
            "source": "n1",
            "target": "n2",
            "relation": "references",
            "confidence": "EXTRACTED",
            "source_file": str(FIXTURES / "sample.py"),
            "weight": 1.0,
        },
    ],
}


def _mock_response(content: bytes, status: int = 200) -> MagicMock:
    response = MagicMock()
    response.__enter__ = lambda s: s
    response.__exit__ = MagicMock(return_value=False)
    response.status = status
    response.code = status
    response.read.side_effect = [content[i : i + 65_536] for i in range(0, len(content), 65_536)] + [b""]
    return response


def _expect_error(label: str, func: Any, pattern: str | None = None) -> str | None:
    try:
        func()
    except Exception as exc:  # noqa: BLE001 - aggregated test assertion includes the actual error.
        if pattern and not re.search(pattern, str(exc)):
            return f"{label}: {exc!r} did not match {pattern!r}"
        return None
    return f"{label}: expected an exception"


def _graph(labels: list[str]) -> tuple[nx.Graph, dict[int, list[str]]]:
    graph = nx.Graph()
    ids = []
    for index, label in enumerate(labels):
        node_id = f"n{index}"
        graph.add_node(node_id, label=label, file_type="code", source_file="x.py", community=0)
        ids.append(node_id)
    for source, target in zip(ids, ids[1:]):
        graph.add_edge(source, target, relation="calls", confidence="EXTRACTED")
    return graph, {0: ids}


def _max_name_bytes(out_dir: Path) -> int:
    return max(len(path.name.encode("utf-8")) for path in out_dir.glob("*.md"))


def test_input_sanitization(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    failures: list[str] = []

    def fake_getaddrinfo(host: str, *args: Any, **kwargs: Any) -> list[tuple[Any, ...]]:
        address = {
            "127.0.0.1": "127.0.0.1",
            "10.0.0.5": "10.0.0.5",
            "169.254.169.254": "169.254.169.254",
            "localhost": "127.0.0.1",
            "cgn.example": "100.64.0.1",
        }.get(host, "93.184.216.34")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]

    monkeypatch.setattr("graph3d.security.socket.getaddrinfo", fake_getaddrinfo)

    for label, url in [
        ("http", "http://example.com/page"),
        ("https", "https://arxiv.org/abs/1706.03762"),
        ("argument metacharacters stay data", "https://example.com/search?q=$(whoami);rm+-rf+/"),
    ]:
        try:
            assert validate_url(url) == url
        except Exception as exc:  # noqa: BLE001
            failures.append(f"validate_url {label}: unexpected {exc!r}")

    for label, url, pattern in [
        ("file local read", "file:///etc/passwd", "file"),
        ("ftp", "ftp://files.example.com/data.zip", "ftp"),
        ("data script", "data:text/html,<script>alert(1)</script>", "data"),
        ("missing scheme", "//no-scheme.example.com", "Blocked URL scheme"),
        ("localhost", "http://localhost/admin", "private|internal"),
        ("loopback ip", "http://127.0.0.1:8000/", "private|internal"),
        ("rfc1918", "http://10.0.0.5/", "private|internal"),
        ("metadata ip", "http://169.254.169.254/latest/meta-data/", "private|internal"),
        ("metadata host", "http://metadata.google.internal/", "metadata"),
        ("carrier grade nat", "http://cgn.example/", "private|internal"),
    ]:
        if failure := _expect_error(label, lambda url=url: validate_url(url), pattern):
            failures.append(failure)

    for label, url, pattern in [
        ("safe_fetch file", "file:///etc/passwd", "file"),
        ("safe_fetch ftp", "ftp://example.com/file.zip", "ftp"),
    ]:
        if failure := _expect_error(label, lambda url=url: safe_fetch(url), pattern):
            failures.append(failure)

    for label, response, expected in [("bytes", b"hello world", b"hello world"), ("empty", b"", b"")]:
        with patch("graph3d.security._build_opener") as opener_factory:
            opener = MagicMock()
            opener.open.return_value = _mock_response(response)
            opener_factory.return_value = opener
            try:
                observed = safe_fetch("https://example.com/")
                if observed != expected:
                    failures.append(f"safe_fetch {label}: {observed!r} != {expected!r}")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"safe_fetch {label}: unexpected {exc!r}")

    with patch("graph3d.security._build_opener") as opener_factory:
        opener = MagicMock()
        opener.open.return_value = _mock_response(b"Not Found", status=404)
        opener_factory.return_value = opener
        try:
            safe_fetch("https://example.com/missing")
            failures.append("safe_fetch non-2xx: expected HTTPError")
        except urllib.error.HTTPError:
            pass

    with patch("graph3d.security._build_opener") as opener_factory:
        response = MagicMock()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)
        response.status = 200
        response.code = 200
        response.read.side_effect = [b"x" * 65_537, b"x" * 65_537, b""]
        opener = MagicMock()
        opener.open.return_value = response
        opener_factory.return_value = opener
        if failure := _expect_error(
            "safe_fetch size cap",
            lambda: safe_fetch("https://example.com/huge", max_bytes=65_536),
            "size limit",
        ):
            failures.append(failure)

    for label, content, predicate in [
        ("utf8", "hello world".encode("utf-8"), lambda text: text == "hello world"),
        ("bad bytes", b"hello \xff world", lambda text: "hello" in text and "world" in text and "\xff" not in text),
    ]:
        with patch("graph3d.security._build_opener") as opener_factory:
            opener = MagicMock()
            opener.open.return_value = _mock_response(content)
            opener_factory.return_value = opener
            try:
                text = safe_fetch_text("https://example.com/")
                if not predicate(text):
                    failures.append(f"safe_fetch_text {label}: unexpected {text!r}")
            except Exception as exc:  # noqa: BLE001
                failures.append(f"safe_fetch_text {label}: unexpected {exc!r}")

    base = tmp_path / "graph3d-out"
    base.mkdir()
    graph_file = base / "graph.json"
    graph_file.write_text("{}", encoding="utf-8")
    path_checks = [
        ("inside", lambda: validate_graph_path(str(graph_file), base=base) == graph_file.resolve()),
        (
            "traversal",
            lambda: _expect_error(
                "traversal",
                lambda: validate_graph_path(str(base / ".." / "etc_passwd"), base=base),
                "escapes",
            )
            is None,
        ),
        (
            "missing base",
            lambda: _expect_error(
                "missing base",
                lambda: validate_graph_path(str(tmp_path / "missing" / "graph.json"), base=tmp_path / "missing"),
                "does not exist",
            )
            is None,
        ),
        (
            "missing file",
            lambda: _expect_error(
                "missing file",
                lambda: validate_graph_path(str(base / "missing.json"), base=base),
                "Graph file not found",
            )
            is None,
        ),
    ]
    for label, check in path_checks:
        try:
            if not check():
                failures.append(f"validate_graph_path {label}: predicate failed")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"validate_graph_path {label}: unexpected {exc!r}")

    for label, raw, expected in [
        ("html passthrough", "<script>", "<script>"),
        ("amp passthrough", "foo & bar", "foo & bar"),
        ("control chars", "hello\x00\x1fworld", "helloworld"),
        ("class", "MyClass", "MyClass"),
        ("function", "extract_python", "extract_python"),
        ("none", None, ""),
    ]:
        observed = sanitize_label(raw)
        if observed != expected:
            failures.append(f"sanitize_label {label}: {observed!r} != {expected!r}")
    if len(sanitize_label("a" * 300)) > 256:
        failures.append("sanitize_label long label was not capped at 256")

    if _MAX_GRAPH_FILE_BYTES != 512 * 1024 * 1024:
        failures.append(f"_MAX_GRAPH_FILE_BYTES changed: {_MAX_GRAPH_FILE_BYTES}")
    if _MAX_FETCH_BYTES <= _MAX_TEXT_BYTES:
        failures.append(f"fetch caps are inconsistent: {_MAX_FETCH_BYTES} <= {_MAX_TEXT_BYTES}")
    small = tmp_path / "small_graph.json"
    small.write_text('{"nodes": [], "links": []}', encoding="utf-8")
    try:
        check_graph_file_size_cap(small)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"graph size cap under limit: {exc!r}")
    monkeypatch.setattr("graph3d.security._MAX_GRAPH_FILE_BYTES", 8)
    oversized = tmp_path / "oversized_graph.json"
    oversized.write_text("AAAAAAAAAAAAAAAA", encoding="utf-8")
    try:
        check_graph_file_size_cap(oversized)
        failures.append("graph size cap over limit: expected ValueError")
    except ValueError as exc:
        message = str(exc)
        for token in ("16", "8", "byte"):
            if token not in message.lower():
                failures.append(f"graph size error missing {token!r}: {message!r}")
    boundary = tmp_path / "boundary_graph.json"
    boundary.write_text("A" * 32, encoding="utf-8")
    monkeypatch.setattr("graph3d.security._MAX_GRAPH_FILE_BYTES", 32)
    try:
        check_graph_file_size_cap(boundary)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"graph size cap boundary equal raised {exc!r}")
    monkeypatch.setattr("graph3d.security._MAX_GRAPH_FILE_BYTES", 31)
    if failure := _expect_error("graph size cap boundary reject", lambda: check_graph_file_size_cap(boundary), "exceeds"):
        failures.append(failure)
    if check_graph_file_size_cap(tmp_path / "does_not_exist.json") is not None:
        failures.append("graph size cap missing file did not return None")
    with monkeypatch.context() as stat_patch:
        stat_patch.setattr(Path, "stat", lambda self: (_ for _ in ()).throw(PermissionError("denied")))
        if check_graph_file_size_cap(small) is not None:
            failures.append("graph size cap unreadable file did not return None")

    class Custom:
        def __str__(self) -> str:
            return "custom-repr"

    string_checks = [
        ("control", _sanitize_metadata_string("hello\x00\x1fworld"), lambda value: value == "helloworld"),
        ("html", _sanitize_metadata_string("<script>alert('x')</script>"), lambda value: "&lt;" in value and "&gt;" in value and "<script>" not in value),
        ("quotes", _sanitize_metadata_string("a\"b'c"), lambda value: "&quot;" in value and ("&#x27;" in value or "&apos;" in value)),
        ("cap", _sanitize_metadata_string("a" * (_METADATA_MAX_VALUE_LEN + 100)), lambda value: len(value) <= _METADATA_MAX_VALUE_LEN),
        ("custom", _sanitize_metadata_string(Custom()), lambda value: value == "custom-repr"),
    ]
    for label, observed, predicate in string_checks:
        if not predicate(observed):
            failures.append(f"metadata string {label}: {observed!r}")

    value_checks = [
        ("int", _sanitize_metadata_value(42), 42),
        ("float", _sanitize_metadata_value(3.14), 3.14),
        ("true", _sanitize_metadata_value(True), True),
        ("false", _sanitize_metadata_value(False), False),
        ("none", _sanitize_metadata_value(None), None),
        ("tuple", _sanitize_metadata_value(("a", "b")), ["a", "b"]),
    ]
    for label, observed, expected in value_checks:
        if observed != expected or type(observed) is not type(expected):
            failures.append(f"metadata value {label}: {observed!r} != {expected!r}")
    dict_out = _sanitize_metadata_value({"k": "<script>x</script>"})
    if not isinstance(dict_out, dict) or "&lt;" not in str(dict_out.get("k")):
        failures.append(f"metadata dict recursion failed: {dict_out!r}")
    list_out = _sanitize_metadata_value(["<a>", "<b>", "<c>"])
    if not isinstance(list_out, list) or not all("&lt;" in str(item) for item in list_out):
        failures.append(f"metadata list recursion failed: {list_out!r}")
    capped = _sanitize_metadata_value(list(range(_METADATA_MAX_LIST_ITEMS * 3)))
    if not isinstance(capped, list) or len(capped) != _METADATA_MAX_LIST_ITEMS:
        failures.append(f"metadata list cap failed: {capped!r}")
    if sanitize_metadata(None) != {}:
        failures.append("sanitize_metadata(None) did not return {}")
    dropped = sanitize_metadata({"\x00": "v", "k": "v2"})
    if dropped != {"k": "v2"}:
        failures.append(f"sanitize_metadata empty key drop failed: {dropped!r}")
    keyed = sanitize_metadata({"<bad>": "v"})
    if "<bad>" in keyed or not any("&lt;" in key for key in keyed):
        failures.append(f"sanitize_metadata key escaping failed: {keyed!r}")
    nested = sanitize_metadata({"outer": {"inner": "<script>x</script>", "list": ["a", "<b>", 99, None, True]}, "scalar": 42})
    if not isinstance(nested.get("outer"), dict):
        failures.append(f"sanitize_metadata nested type failed: {nested!r}")
    else:
        outer = nested["outer"]
        if "&lt;" not in str(outer.get("inner")) or outer.get("list") != ["a", "&lt;b&gt;", 99, None, True]:
            failures.append(f"sanitize_metadata nested values failed: {nested!r}")
    bools = sanitize_metadata({"flag_t": True, "flag_f": False, "num": 1})
    if bools.get("flag_t") is not True or bools.get("flag_f") is not False or bools.get("num") != 1:
        failures.append(f"sanitize_metadata bool preservation failed: {bools!r}")

    assert not failures, "\n".join(failures)


def test_validate_schema_valid_and_invalid() -> None:
    failures: list[str] = []

    extraction_cases = [
        ("valid", VALID, []),
        ("not dict", [], ["JSON object"]),
        ("missing nodes", {"edges": []}, ["nodes"]),
        ("missing edges", {"nodes": []}, ["edges"]),
        ("nodes not list", {"nodes": "bad", "edges": []}, ["nodes", "list"]),
        ("edges not list", {"nodes": [], "edges": "bad"}, ["edges", "list"]),
        ("node not object", {"nodes": ["bad"], "edges": []}, ["Node 0", "object"]),
        ("edge not object", {"nodes": VALID["nodes"], "edges": ["bad"]}, ["Edge 0", "object"]),
    ]
    for label, data, tokens in extraction_cases:
        errors = validate_extraction(data)
        if tokens:
            for token in tokens:
                if not any(token in error for error in errors):
                    failures.append(f"extraction {label}: missing {token!r} in {errors!r}")
        elif errors:
            failures.append(f"extraction {label}: {errors!r}")

    valid_export = {
        "graph3d_schema": {"kind": GRAPH3D_EXPORT_SCHEMA_KIND, "version": GRAPH3D_EXPORT_SCHEMA_VERSION},
        "nodes": [{"id": "n1", "label": "A", "file_type": "code", "source_file": "a.py"}],
        "links": [],
        "graph3d_metadata": {
            "schema_kind": GRAPH3D_EXPORT_SCHEMA_KIND,
            "schema_version": GRAPH3D_EXPORT_SCHEMA_VERSION,
            "source_documents": {
                "source_files": ["a.py"],
                "source_file_count": 1,
                "file_type_counts": {"code": 1},
                "documents": [{"source_file": "a.py", "node_count": 1, "link_count": 0}],
            },
            "validation": {"node_count": 1, "link_count": 0, "hyperedge_count": 0, "dangling_link_count": 0},
        },
    }
    export_cases = [
        ("legacy node-link", {"directed": False, "multigraph": False, "graph": {}, "nodes": [{"id": "n1", "label": "Legacy"}], "links": []}, []),
        ("legacy bad endpoints", {"nodes": [{"id": "n1", "label": "Legacy"}], "links": [{"source": 1, "target": "n1"}]}, []),
        ("valid schema-core", valid_export, []),
        ("not dict", [], ["JSON object"]),
        ("nodes not list", {"nodes": "bad", "links": []}, ["nodes", "list"]),
        ("links not list", {"nodes": [], "links": "bad"}, ["links", "list"]),
        ("schema not object", {"graph3d_schema": "bad"}, ["graph3d_schema", "object"]),
        ("schema missing fields", {"graph3d_schema": {}}, ["version", "kind"]),
        ("metadata not object", {"graph3d_metadata": "bad"}, ["graph3d_metadata", "object"]),
        ("source refs missing", {"nodes": [{"id": "n1", "label": "A", "file_type": "code", "source_file": "a.py"}], "links": [], "graph3d_metadata": {"source_documents": {"source_files": [], "source_file_count": 0, "file_type_counts": {"code": 1}}}}, ["source_files"]),
        ("bad endpoint with metadata", {"nodes": [{"id": "n1", "label": "A", "file_type": "code", "source_file": "a.py"}], "links": [{"source": 1, "target": "n1", "relation": "references"}], "graph3d_metadata": {}}, ["links[0].source", "string"]),
        ("bad schema metadata", {"nodes": [{"id": "n1", "label": "Schema", "file_type": "schema", "source_file": "schema.json", "metadata": {"schema_path": 123}}], "links": [], "graph3d_metadata": {}}, ["metadata.schema_path"]),
        ("source count mismatch", {"nodes": [{"id": "n1", "source_file": "a.py", "file_type": "code"}], "links": [], "graph3d_metadata": {"source_documents": {"source_files": ["a.py"], "source_file_count": 2}}}, ["source_file_count"]),
        ("file type mismatch", {"nodes": [{"id": "n1", "source_file": "a.py", "file_type": "code"}], "links": [], "graph3d_metadata": {"source_documents": {"source_files": ["a.py"], "source_file_count": 1, "file_type_counts": {"document": 1}}}}, ["file_type_counts"]),
        ("bad document summary", {"nodes": [], "links": [], "graph3d_metadata": {"source_documents": {"documents": [{"node_count": -1}]}}}, ["source_file", "node_count"]),
        ("bad validation summary", {"nodes": [], "links": [], "graph3d_metadata": {"validation": {"node_count": -1}}}, ["validation.node_count"]),
    ]
    for label, data, tokens in export_cases:
        errors = validate_graph_export(data)
        if tokens:
            for token in tokens:
                if not any(token in error for error in errors):
                    failures.append(f"export {label}: missing {token!r} in {errors!r}")
        elif errors:
            failures.append(f"export {label}: {errors!r}")

    assert not failures, "\n".join(failures)


def test_validate_enums_and_required_fields() -> None:
    failures: list[str] = []

    if VALID_FILE_TYPES != {"code", "document", "paper", "image", "rationale", "concept", "schema", "data"}:
        failures.append(f"VALID_FILE_TYPES changed: {VALID_FILE_TYPES!r}")
    if VALID_CONFIDENCES != {"EXTRACTED", "INFERRED", "AMBIGUOUS"}:
        failures.append(f"VALID_CONFIDENCES changed: {VALID_CONFIDENCES!r}")
    for file_type in sorted(VALID_FILE_TYPES):
        errors = validate_extraction({"nodes": [{"id": file_type, "label": file_type, "file_type": file_type, "source_file": f"{file_type}.txt"}], "edges": []})
        if errors:
            failures.append(f"valid file_type {file_type}: {errors!r}")
    errors = validate_extraction({"nodes": [{"id": "n1", "label": "X", "file_type": "video", "source_file": "x.mp4"}], "edges": []})
    if not any("file_type" in error for error in errors):
        failures.append(f"invalid file_type was not rejected: {errors!r}")
    for confidence in sorted(VALID_CONFIDENCES):
        errors = validate_extraction({"nodes": VALID["nodes"], "edges": [{"source": "n1", "target": "n2", "relation": "calls", "confidence": confidence, "source_file": "a.py"}]})
        if errors:
            failures.append(f"valid confidence {confidence}: {errors!r}")
    errors = validate_extraction({"nodes": VALID["nodes"], "edges": [{"source": "n1", "target": "n2", "relation": "calls", "confidence": "CERTAIN", "source_file": "a.py"}]})
    if not any("confidence" in error for error in errors):
        failures.append(f"invalid confidence was not rejected: {errors!r}")

    for field in ("id", "label", "file_type", "source_file"):
        node = {"id": "n1", "label": "A", "file_type": "code", "source_file": "a.py"}
        node.pop(field)
        errors = validate_extraction({"nodes": [node], "edges": []})
        if not any(field in error for error in errors):
            failures.append(f"missing node field {field}: {errors!r}")
    for field in ("source", "target", "relation", "confidence", "source_file"):
        edge = {"source": "n1", "target": "n2", "relation": "calls", "confidence": "EXTRACTED", "source_file": "a.py"}
        edge.pop(field)
        errors = validate_extraction({"nodes": VALID["nodes"], "edges": [edge]})
        if not any(field in error for error in errors):
            failures.append(f"missing edge field {field}: {errors!r}")

    for label, data, tokens in [
        ("dangling source", {"nodes": [VALID["nodes"][0]], "edges": [{"source": "missing_id", "target": "n1", "relation": "calls", "confidence": "EXTRACTED", "source_file": "a.py"}]}, ["source", "missing_id"]),
        ("dangling target", {"nodes": [VALID["nodes"][0]], "edges": [{"source": "n1", "target": "ghost", "relation": "calls", "confidence": "EXTRACTED", "source_file": "a.py"}]}, ["target", "ghost"]),
    ]:
        errors = validate_extraction(data)
        for token in tokens:
            if not any(token in error for error in errors):
                failures.append(f"{label}: missing {token!r} in {errors!r}")

    try:
        assert_valid(VALID)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"assert_valid valid raised {exc!r}")
    try:
        assert_valid({"nodes": "bad", "edges": []})
        failures.append("assert_valid invalid did not raise")
    except ValueError as exc:
        if "error" not in str(exc):
            failures.append(f"assert_valid message missing error: {exc!r}")

    for label, node, tokens in [
        ("full", {"metadata": {"schema_path": "$.properties.name", "schema_kind": "schema_property", "schema_pattern": "$.properties.*"}}, []),
        ("other", {"metadata": {"other": "value"}}, []),
        ("absent", {}, []),
        ("node not object", [], ["object"]),
        ("metadata not object", {"metadata": "bad"}, ["metadata", "object"]),
        ("bad types", {"metadata": {"schema_path": ["$"], "schema_kind": "", "schema_pattern": 3}}, ["schema_path", "schema_kind", "schema_pattern"]),
    ]:
        errors = validate_schema_path_metadata(node)
        if tokens:
            for token in tokens:
                if not any(token in error for error in errors):
                    failures.append(f"schema metadata {label}: missing {token!r} in {errors!r}")
        elif errors:
            failures.append(f"schema metadata {label}: {errors!r}")

    source_metadata = {"source_refs": [{"source_file": "docs/a.md", "source_location": "L10-L12", "node_id": "n1", "confidence_score": 0.9}]}
    for label, container, tokens in [
        ("metadata", source_metadata, []),
        ("export", {"graph3d_metadata": source_metadata}, []),
        ("container not object", [], ["object"]),
        ("graph metadata not object", {"graph3d_metadata": "bad"}, ["graph3d_metadata", "object"]),
        ("bad list", {"source_refs": {"source_file": "a.py"}}, ["source_refs", "list"]),
        ("ref not object", {"source_refs": ["bad"]}, ["object"]),
        ("missing identifier", {"source_refs": [{}]}, ["source identifier"]),
        ("bad string", {"source_refs": [{"source_file": 3}]}, ["source_file", "string"]),
        ("bad line", {"source_refs": [{"source_file": "a.py", "line": -1}]}, ["line", "non-negative"]),
        ("bad confidence", {"source_refs": [{"source_file": "a.py", "confidence": "CERTAIN"}]}, ["confidence"]),
        ("bad confidence score", {"source_refs": [{"source_file": "a.py", "confidence_score": 1.5}]}, ["confidence_score"]),
    ]:
        errors = validate_source_refs(container)
        if tokens:
            for token in tokens:
                if not any(token in error for error in errors):
                    failures.append(f"source refs {label}: missing {token!r} in {errors!r}")
        elif errors:
            failures.append(f"source refs {label}: {errors!r}")

    for label, relation, node_ids, tokens in [
        ("target missing id", {"source": "n1", "target": "ghost", "relation": "calls"}, {"n1", "n2"}, ["target", "ghost"]),
        ("source not string", {"source": 123, "target": "n2"}, None, ["source", "string"]),
        ("missing endpoint", {"source": "n1"}, None, ["target"]),
        ("empty relation", {"source": "n1", "target": "n2", "relation": ""}, None, ["relation", "non-empty"]),
        ("relation not object", [], None, ["object"]),
    ]:
        errors = validate_relation_endpoints(relation, node_ids)
        for token in tokens:
            if not any(token in error for error in errors):
                failures.append(f"relation {label}: missing {token!r} in {errors!r}")

    for label, metadata, tokens in [
        ("source only", {"source_file": "a.py"}, []),
        ("not object", [], ["object"]),
        ("bad string", {"schema_kind": 3}, ["schema_kind", "string"]),
        ("bad confidence_score", {"confidence_score": 1.5}, ["confidence_score"]),
    ]:
        errors = validate_provenance_metadata(metadata)
        if tokens:
            for token in tokens:
                if not any(token in error for error in errors):
                    failures.append(f"provenance {label}: missing {token!r} in {errors!r}")
        elif errors:
            failures.append(f"provenance {label}: {errors!r}")

    assert not failures, "\n".join(failures)


def test_obsidian_filename_caps(tmp_path: Path) -> None:
    failures: list[str] = []

    for label, labels, predicate in [
        ("long_ascii", ["a" * 300, "short"], lambda out: _max_name_bytes(out) <= 255),
        ("long_cjk", ["中" * 300, "ok"], lambda out: _max_name_bytes(out) <= 255),
        (
            "distinct_prefix",
            ["z" * 250 + "_ALPHA", "z" * 250 + "_BETA"],
            lambda out: len([path for path in out.glob("*.md") if not path.name.startswith("_COMMUNITY_")]) == 2
            and _max_name_bytes(out) <= 255,
        ),
    ]:
        out_dir = tmp_path / label
        graph, communities = _graph(labels)
        try:
            to_obsidian(graph, communities, str(out_dir))
            if not predicate(out_dir):
                failures.append(f"obsidian {label}: predicate failed for {[path.name for path in out_dir.glob('*.md')]!r}")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"obsidian {label}: unexpected {exc!r}")

    wikilink_dir = tmp_path / "wikilink"
    graph, communities = _graph(["w" * 300, "neighbor"])
    try:
        to_obsidian(graph, communities, str(wikilink_dir))
        neighbor_note = (wikilink_dir / "neighbor.md").read_text(encoding="utf-8")
        targets = re.findall(r"\[\[([^\]]+)\]\]", neighbor_note)
        if not targets:
            failures.append("obsidian wikilink: no wikilink found")
        for target in targets:
            if not (wikilink_dir / f"{target}.md").exists():
                failures.append(f"obsidian wikilink: dangling target {target!r}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"obsidian wikilink: unexpected {exc!r}")

    canvas_file = tmp_path / "graph.canvas"
    graph, communities = _graph(["c" * 300, "ok"])
    try:
        to_canvas(graph, communities, str(canvas_file))
        data = json.loads(canvas_file.read_text(encoding="utf-8"))
        for node in data.get("nodes", []):
            if node.get("type") == "file" and len(node["file"].encode("utf-8")) > 255:
                failures.append(f"canvas file reference too long: {node['file']!r}")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"canvas filename cap: unexpected {exc!r}")

    assert not failures, "\n".join(failures)
