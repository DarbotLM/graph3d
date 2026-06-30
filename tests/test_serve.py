"""Consolidated table-driven tests for serve, MCP ingest, CLI, and schema paths."""
from __future__ import annotations

import builtins
import json
import sqlite3
from pathlib import Path
from unittest import mock

import networkx as nx
import pytest
from networkx.readwrite import json_graph

import graph3d.__main__ as mainmod
from graph3d import terminology
from graph3d.build import build_from_json
from graph3d.detect import FileType, classify_file, count_words
from graph3d.extract import _get_extractor, _make_id, extract, extract_json
from graph3d.mcp_ingest import MCP_CONFIG_FILENAMES, extract_mcp_config, is_mcp_config_path
from graph3d.schema_paths import extract_json_schema_paths, extract_sqlite_schema
from graph3d.serve import (
    _bfs,
    _communities_from_graph,
    _compute_idf,
    _dfs,
    _filter_graph_by_context,
    _filter_graph_by_relations,
    _find_node,
    _infer_context_filters,
    _load_graph,
    _normalize_context_filters,
    _pick_seeds,
    _query_graph_text,
    _query_terms,
    _resolve_context_filters,
    _score_nodes,
    _subgraph_to_text,
    build_query_subgraph,
    make_view_state,
)
from graph3d.validate import validate_extraction


FIXTURES = Path(__file__).parent / "fixtures"


def _graph() -> nx.DiGraph:
    graph = nx.DiGraph()
    for node_id, label, source, loc, community in [
        ("n1", "extract", "extract.py", "L10", 0),
        ("n2", "cluster", "cluster.py", "L5", 0),
        ("n3", "build", "build.py", "L1", 1),
        ("n4", "report", "report.py", "L1", 1),
        ("n5", "isolated", "other.py", "L1", 2),
    ]:
        graph.add_node(node_id, label=label, source_file=source, source_location=loc, community=community)
    graph.add_edge("n1", "n2", relation="calls", confidence="INFERRED", context="call")
    graph.add_edge("n2", "n3", relation="imports", confidence="EXTRACTED", context="import")
    graph.add_edge("n3", "n4", relation="uses", confidence="EXTRACTED")
    return graph


def _noisy_graph() -> nx.DiGraph:
    graph = nx.DiGraph()
    for idx in range(20):
        graph.add_node(f"err{idx}", label=f"error_handler_{idx}", source_file=f"err{idx}.py", community=0)
        if idx:
            graph.add_edge(f"err{idx - 1}", f"err{idx}", relation="calls", confidence="EXTRACTED")
    graph.add_node("fbs", label="FooBarService", source_file="service.py", community=1)
    graph.add_node("fbs_dep", label="ServiceClient", source_file="client.py", community=1)
    graph.add_edge("fbs", "fbs_dep", relation="uses", confidence="EXTRACTED")
    return graph


def _write_json(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _by_kind(result: dict, key: str, kind: str) -> list[str]:
    return [n["label"] for n in result["nodes"] if n.get("metadata", {}).get(key) == kind]


def _schema_nodes(result: dict, kind: str) -> list[dict]:
    return [n for n in result["nodes"] if n.get("metadata", {}).get("schema_kind") == kind]


def _run_main(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr(mainmod.sys, "argv", argv)
    mainmod.main()


def test_terminology_relations() -> None:
    failures = []
    expected_keys = {"dataflow", "call", "import", "containment", "reference", "schema", "hierarchy", "rationale"}
    if not expected_keys.issubset(terminology.PREDICATE_GROUPS):
        failures.append(f"missing predicate keys: {sorted(expected_keys - set(terminology.PREDICATE_GROUPS))}")
    cases = [
        ("dataflow", {"calls", "imports", "imports_from"}, set()),
        ("flow", {"calls", "imports"}, set()),
        ("call-flow", {"calls", "method", "imports"}, set()),
        ("call", {"calls", "method"}, {"imports"}),
        ("imports", {"imports", "imports_from", "re_exports"}, {"calls"}),
        ("schema-path", {"contains_schema_path", "has_schema_type"}, set()),
        ("unknown-word", set(), {"calls", "imports", "contains"}),
    ]
    for word, includes, excludes in cases:
        resolved = terminology.resolve_relations(word)
        missing = includes - resolved
        unexpected = excludes & resolved
        if missing or unexpected:
            failures.append(f"{word}: missing={sorted(missing)} unexpected={sorted(unexpected)} got={sorted(resolved)}")
    if terminology.resolve_relations("not-a-group") != set():
        failures.append("unknown words must resolve to an empty set")
    query_cases = [
        ("call graph and imports", {"calls", "method", "imports", "imports_from"}),
        ("show data flow lineage", {"calls", "imports", "reads_from"}),
        ("schema path for session_id", {"contains_schema_path", "matches_schema_terminal", "has_schema_type"}),
        ("plain label search only", set()),
    ]
    for question, includes in query_cases:
        resolved = terminology.relations_in_query(question)
        if not includes.issubset(resolved):
            failures.append(f"{question}: missing {sorted(includes - resolved)} from {sorted(resolved)}")
    assert not failures, "\n".join(failures)


def test_query_helpers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    failures = []
    graph = _graph()
    if _communities_from_graph(graph) != {0: ["n1", "n2"], 1: ["n3", "n4"], 2: ["n5"]}:
        failures.append(f"bad communities: {_communities_from_graph(graph)}")
    score_cases = [
        ("exact", ["extract"], "n1", {"n1"}),
        ("source", ["cluster"], "n2", {"n2"}),
        ("punctuation", ["extract?"], "n1", {"n1"}),
        ("none", ["xyzzy"], None, set()),
    ]
    for name, terms, top, contains in score_cases:
        scored = _score_nodes(graph, terms)
        ids = [nid for _, nid in scored]
        if top and (not ids or ids[0] != top):
            failures.append(f"{name}: expected top {top}, got {ids[:3]}")
        if top is None and scored:
            failures.append(f"{name}: expected no match, got {ids}")
        if not contains.issubset(ids):
            failures.append(f"{name}: missing ids {contains - set(ids)}")
    if _find_node(graph, "extract?") != ["n1"]:
        failures.append("_find_node should ignore trailing punctuation")
    if _query_terms("what calls extract?") != ["what", "calls", "extract"]:
        failures.append("_query_terms punctuation handling regressed")

    class FakeJieba:
        def cut(self, text: str) -> list[str]:
            return {
                "前端": ["前端"],
                "依赖": ["依赖"],
                "安装": ["安装"],
                "包管理器": ["包", "管理器"],
                "项目约定": ["项目", "约定"],
                "a前": ["a", "前"],
                "页面路由": ["页面", "路由"],
            }[text]

    import graph3d.serve as serve_mod

    monkeypatch.setattr(serve_mod, "_jieba", FakeJieba())
    expected_terms = [
        "前端",
        "dependency",
        "依赖",
        "install",
        "安装",
        "包",
        "管理器",
        "包管理器",
        "项目",
        "约定",
        "项目约定",
        "前",
        "a前",
    ]
    terms = _query_terms("前端 dependency 依赖 install 安装 to of 包管理器 项目约定 a前")
    if terms != expected_terms:
        failures.append(f"Chinese mixed terms mismatch: {terms}")
    if _query_terms("页面路由") != ["页面", "路由", "页面路由"]:
        failures.append("jieba segmentation should keep original term")
    if serve_mod._has_chinese("かなカナ한글") or serve_mod._query_terms("かなカナ한글") != ["かなカナ한글"]:
        failures.append("non-Chinese scripts should be kept but not segmented")
    monkeypatch.setattr(serve_mod, "_jieba", None)
    fallback = serve_mod._query_terms("页面路由")
    if not {"页面", "路由", "页面路由"}.issubset(fallback) or len(fallback) != 4:
        failures.append(f"Chinese fallback mismatch: {fallback}")

    traversal_cases = [
        ("bfs1", _bfs, ["n1"], 1, {"n1", "n2"}, {"n3"}),
        ("bfs2", _bfs, ["n1"], 2, {"n3"}, set()),
        ("bfs isolated", _bfs, ["n5"], 3, {"n5"}, {"n1"}),
        ("dfs1", _dfs, ["n1"], 1, {"n1", "n2"}, {"n3"}),
        ("dfs chain", _dfs, ["n1"], 5, {"n1", "n2", "n3", "n4"}, set()),
    ]
    for name, func, seeds, depth, includes, excludes in traversal_cases:
        visited, edges = func(graph, seeds, depth)
        if not includes.issubset(visited) or excludes & visited:
            failures.append(f"{name}: visited={sorted(visited)}")
        if name == "bfs1" and not any(u == "n1" or v == "n1" for u, v in edges):
            failures.append("bfs should return traversed edges")
    filtered = _filter_graph_by_context(graph, ["call"])
    visited, edges = _bfs(filtered, ["n1"], 2)
    if "n2" not in visited or "n3" in visited or edges != [("n1", "n2")]:
        failures.append(f"context filter mismatch: {visited}, {edges}")
    if _infer_context_filters("who calls extract") != ["call"]:
        failures.append("call heuristic should infer call context")
    if _resolve_context_filters("who calls extract", ["field"]) != (["field"], "explicit"):
        failures.append("explicit context should override heuristic")
    aliases = {
        "param": "parameter_type",
        "parameter": "parameter_type",
        "return": "return_type",
        "returns": "return_type",
        "generic": "generic_arg",
        "generics": "generic_arg",
        "annotation": "attribute",
        "decorator": "attribute",
        "field": "field",
    }
    for raw, expected in aliases.items():
        if _normalize_context_filters([raw]) != [expected]:
            failures.append(f"context alias {raw} did not become {expected}")

    text = _subgraph_to_text(graph, {"n1", "n2"}, [("n1", "n2")])
    for needle in ("extract", "cluster", "EDGE", "calls", "context=call"):
        if needle not in text:
            failures.append(f"subgraph text missing {needle}: {text}")
    truncated = _subgraph_to_text(graph, {"n1", "n2", "n3", "n4"}, [("n1", "n2")], token_budget=1)
    if "truncated" not in truncated or not ("get_node" in truncated or "context_filter" in truncated):
        failures.append(f"bad truncation hint: {truncated}")

    noisy = _noisy_graph()
    if _score_nodes(noisy, ["foobarservice", "error"])[0][1] != "fbs":
        failures.append("IDF should rank rare identifier first")
    _score_nodes(graph, ["extract"])
    if "extract" not in graph.graph.get("_idf_cache", {}):
        failures.append("IDF should cache on graph")
    if "_idf_cache" in _graph().graph:
        failures.append("new graph should not share IDF cache")
    if _compute_idf(_graph(), ["extract"])["extract"] <= 1.0:
        failures.append("rare IDF should be greater than 1")
    common = nx.Graph()
    for idx in range(20):
        common.add_node(f"n{idx}", label=f"handle_{idx}", source_file=f"f{idx}.py")
    if _compute_idf(common, ["handle"])["handle"] >= 1.0:
        failures.append("common IDF should be less than 1")
    seed_cases = [
        ([(1000.0, "fbs"), (1.0, "err1"), (0.9, "err2")], None, ["fbs"]),
        ([(10.0, "a"), (9.0, "b"), (8.5, "c")], None, ["a", "b", "c"]),
        ([], None, []),
        ([(5.0, "x")], None, ["x"]),
        ([(10.0, f"n{idx}") for idx in range(10)], 3, ["n0", "n1", "n2"]),
    ]
    for scored, max_k, expected in seed_cases:
        got = _pick_seeds(scored, max_k=max_k) if max_k is not None else _pick_seeds(scored)
        if got != expected:
            failures.append(f"pick seeds mismatch: got {got}, expected {expected}")

    query_cases = [
        (graph, "extract", {"extract", "cluster"}, {"No matching nodes found."}, {}),
        (graph, "who calls extract", {"Context: call (heuristic)", "cluster"}, {"build"}, {}),
        (graph, "extract", {"Context: call (explicit)", "cluster"}, {"build"}, {"context_filters": ["call"]}),
        (noisy, "FooBarService error handling", {"FooBarService", "ServiceClient"}, set(), {}),
    ]
    for case_graph, question, includes, excludes, kwargs in query_cases:
        output = _query_graph_text(case_graph, question, mode="bfs", depth=2, token_budget=2000, **kwargs)
        if not all(item in output for item in includes) or any(item in output for item in excludes):
            failures.append(f"query mismatch for {question}: {output}")
    chinese = nx.Graph()
    chinese.add_node("parent", label="页面路由规范", source_file="doc.md", source_location="L1", community=0)
    chinese.add_node("child", label="路由桥接核对表", source_file="doc.md", source_location="L10", community=0)
    chinese.add_edge("parent", "child", relation="contains", confidence="EXTRACTED")
    if "路由" not in _query_graph_text(chinese, "页面路由", mode="bfs", depth=2):
        failures.append("Chinese query text should find routing nodes")
    chinese_ids = [nid for _, nid in _score_nodes(chinese, ["路由"])]
    if chinese_ids[0] != "child" or set(chinese_ids) != {"parent", "child"}:
        failures.append(f"Chinese substring scoring mismatch: {chinese_ids}")

    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(json_graph.node_link_data(_graph(), edges="links")), encoding="utf-8")
    if _load_graph(str(graph_path)).number_of_nodes() != _graph().number_of_nodes():
        failures.append("_load_graph roundtrip mismatch")
    with pytest.raises(SystemExit):
        _load_graph(str(tmp_path / "missing.json"))
    monkeypatch.setattr("graph3d.security._MAX_GRAPH_FILE_BYTES", 16)
    with pytest.raises(SystemExit):
        _load_graph(str(graph_path))
    err = capsys.readouterr().err
    if "exceeds" not in err or "byte cap" not in err:
        failures.append(f"oversize load error mismatch: {err}")
    monkeypatch.setattr("graph3d.security._MAX_GRAPH_FILE_BYTES", 10 * 1024 * 1024)
    first_key = (graph_path.stat().st_mtime_ns, graph_path.stat().st_size)
    _write_json(graph_path, json_graph.node_link_data(nx.DiGraph([("a", "b")]), edges="links"))
    second_key = (graph_path.stat().st_mtime_ns, graph_path.stat().st_size)
    if first_key == second_key:
        failures.append("graph stat key should change after content changes")
    assert not failures, "\n".join(failures)


def test_build_query_subgraph_fallback_and_explicit() -> None:
    graph = nx.DiGraph()
    for node_id, label in [("api", "APIService"), ("helper", "Helper"), ("call_api", "CallAPI"), ("worker", "Worker"), ("module", "Module")]:
        graph.add_node(node_id, label=label, source_file=f"{node_id}.py", community=0)
    graph.add_edge("api", "helper", relation="uses", confidence="EXTRACTED")
    graph.add_edge("call_api", "worker", relation="calls", confidence="EXTRACTED")
    graph.add_edge("worker", "module", relation="imports", confidence="EXTRACTED")
    failures = []
    cases = [
        ("inferred fallback", "dataflow APIService", 1, None, {"api", "helper"}, ["api"], 1),
        ("explicit calls", "APIService", 1, {"calls"}, {"api"}, ["api"], 0),
        ("explicit uses", "APIService", 1, {"uses"}, {"api", "helper"}, ["api"], 1),
        ("inferred dataflow", "dataflow CallAPI", 2, None, {"call_api", "worker", "module"}, ["call_api"], 2),
    ]
    for name, question, depth, relations, expected_nodes, expected_seeds, expected_edges in cases:
        subgraph, seeds = build_query_subgraph(graph, question, depth=depth, relations=relations)
        if set(subgraph.nodes()) != expected_nodes or seeds != expected_seeds or subgraph.number_of_edges() != expected_edges:
            failures.append(f"{name}: nodes={sorted(subgraph.nodes())}, seeds={seeds}, edges={subgraph.number_of_edges()}")
    capped, seeds = build_query_subgraph(graph, "dataflow CallAPI", depth=2, max_nodes=2)
    if not set(seeds).issubset(capped.nodes()) or capped.number_of_nodes() != 2:
        failures.append(f"max_nodes should keep seeds: seeds={seeds}, nodes={sorted(capped.nodes())}")
    filtered = _filter_graph_by_relations(graph, {"calls", "imports"})
    if {d.get("relation") for _, _, d in filtered.edges(data=True)} != {"calls", "imports"}:
        failures.append("relation filter kept wrong edge set")
    if filtered.number_of_nodes() != graph.number_of_nodes():
        failures.append("relation filter should retain all nodes")
    if _filter_graph_by_relations(graph, set()) is not graph or _filter_graph_by_relations(graph, None) is not graph:
        failures.append("empty relation filter should return original graph")
    assert not failures, "\n".join(failures)


def test_make_view_state() -> None:
    required = {"schema", "focus_node", "focus_depth", "cluster_only", "slice", "highlight_path", "hidden_patterns", "camera", "lod_level"}
    cases = [
        ("minimal", {}, None, None, {"mode": "all", "layer": 50, "thickness": 18}),
        (
            "full",
            {
                "focus": "node-1",
                "focus_depth": 3,
                "cluster_only": "7",
                "slice_mode": "layer",
                "layer": 12,
                "thickness": 5,
                "source": "a",
                "dest": "b",
                "hidden_patterns": ["test_*"],
                "lod_level": "high",
            },
            "node-1",
            {"source": "a", "dest": "b"},
            {"mode": "layer", "layer": 12, "thickness": 5},
        ),
        ("source-only", {"source": "a"}, None, None, {"mode": "all", "layer": 50, "thickness": 18}),
        ("dest-only", {"dest": "b"}, None, None, {"mode": "all", "layer": 50, "thickness": 18}),
    ]
    failures = []
    for name, kwargs, focus, highlight, slice_state in cases:
        state = make_view_state(**kwargs)
        if set(state) != required:
            failures.append(f"{name}: keys mismatch {sorted(state)}")
        if state["schema"] != "graph3d.viewstate/1":
            failures.append(f"{name}: schema mismatch")
        if state["focus_node"] != focus or state["highlight_path"] != highlight or state["slice"] != slice_state:
            failures.append(f"{name}: structure mismatch {state}")
        if name == "full" and (state["hidden_patterns"] != ["test_*"] or state["lod_level"] != "high"):
            failures.append(f"{name}: hidden/lod mismatch {state}")
    assert not failures, "\n".join(failures)


def test_query_graph_text_relation_narrowing() -> None:
    graph = nx.DiGraph()
    for node_id, label in [("runner", "Runner"), ("worker", "Worker"), ("module", "Module"), ("helper", "Helper"), ("payload", "Payload"), ("factory", "PayloadFactory")]:
        graph.add_node(node_id, label=label, source_file=f"{node_id}.py", community=0)
    graph.add_edge("runner", "worker", relation="calls", confidence="EXTRACTED", context="call")
    graph.add_edge("worker", "module", relation="imports", confidence="EXTRACTED", context="import")
    graph.add_edge("runner", "helper", relation="uses", confidence="EXTRACTED")
    graph.add_edge("runner", "payload", relation="references", context="parameter_type", confidence="EXTRACTED")
    graph.add_edge("runner", "factory", relation="calls", context="call", confidence="EXTRACTED")
    cases = [
        ("inferred call", "call graph Runner", {"depth": 2}, {"Relations:", "calls", "method", "Worker", "PayloadFactory"}, {"Module", "Helper"}),
        ("fallback", "schema Runner", {"depth": 1}, {"Worker", "Helper", "Payload"}, {"Relations:"}),
        ("explicit", "Runner", {"depth": 1, "relations": {"has_schema_type"}}, {"Relations: has_schema_type", "1 nodes found", "Runner"}, {"Worker", "Helper", "Payload"}),
        ("context", "who accepts Payload", {"depth": 2, "context_filters": ["parameter_type"]}, {"Context: parameter_type (explicit)", "Payload"}, {"PayloadFactory"}),
    ]
    failures = []
    for name, question, kwargs, includes, excludes in cases:
        text = _query_graph_text(graph, question, mode="bfs", token_budget=2000, **kwargs)
        if not all(needle in text for needle in includes) or any(needle in text for needle in excludes):
            failures.append(f"{name}: text mismatch\n{text}")
    assert not failures, "\n".join(failures)


def test_mcp_ingest(tmp_path: Path) -> None:
    failures = []
    detection = [(Path("x") / n, True) for n in (".mcp.json", "claude_desktop_config.json", "mcp.json", "mcp_servers.json")]
    detection += [(Path(n), False) for n in ("package.json", "config.json", "tsconfig.json")]
    for path, expected in detection:
        if is_mcp_config_path(path) is not expected:
            failures.append(f"detection mismatch for {path}")
    if not isinstance(MCP_CONFIG_FILENAMES, frozenset) or ".mcp.json" not in MCP_CONFIG_FILENAMES:
        failures.append("MCP_CONFIG_FILENAMES contract changed")
    fixture = extract_mcp_config(FIXTURES / "sample.mcp.json")
    checks = [
        (not fixture.get("error") and fixture["nodes"] and fixture["edges"], "fixture should parse"),
        (set(_by_kind(fixture, "mcp_kind", "mcp_server")) == {"filesystem", "fetch", "github", "time"}, "server labels"),
        (set(_by_kind(fixture, "mcp_kind", "mcp_command")) == {"npx", "uvx"}, "command labels"),
        ({"@modelcontextprotocol/server-filesystem", "@modelcontextprotocol/server-github", "mcp-server-fetch", "mcp-server-time"}.issubset(_by_kind(fixture, "mcp_kind", "mcp_package")), "package labels"),
        ("@modelcontextprotocol/server-github@0.6.2" not in _by_kind(fixture, "mcp_kind", "mcp_package"), "version stripped"),
        ({"FILESYSTEM_ROOT", "GITHUB_PERSONAL_ACCESS_TOKEN"}.issubset(_by_kind(fixture, "mcp_kind", "env_var")), "env labels"),
        ({"contains", "references", "requires_env"}.issubset({e["relation"] for e in fixture["edges"]}), "relations"),
    ]
    failures.extend(msg for ok, msg in checks if not ok)
    payload = json.dumps(fixture, ensure_ascii=False)
    for forbidden in ("ghp_PLACEHOLDER_NOT_A_REAL_TOKEN", "/tmp/workspace"):
        if forbidden in payload:
            failures.append(f"sensitive value leaked: {forbidden}")
    node_ids = {n["id"] for n in fixture["nodes"]}
    if any(e["source"] not in node_ids or e["target"] not in node_ids for e in fixture["edges"]):
        failures.append("fixture has dangling edges")
    if any(e.get("confidence") != "EXTRACTED" or e.get("confidence_score") != 1.0 or e.get("weight") != 1.0 for e in fixture["edges"]):
        failures.append("fixture edges missing confidence fields")
    config_a = _write_json(tmp_path / "a" / ".mcp.json", {"mcpServers": {"same": {"command": "npx", "args": ["@scope/server-a"], "env": {"OPENAI_API_KEY": "v1"}}}})
    config_b = _write_json(tmp_path / "b" / "claude_desktop_config.json", {"mcpServers": {"same": {"command": "npx", "args": ["@scope/server-b"], "env": {"OPENAI_API_KEY": "v2"}}}})
    result_a, result_b = extract_mcp_config(config_a), extract_mcp_config(config_b)
    for kind, should_match in (("mcp_command", True), ("env_var", True), ("mcp_server", False)):
        id_a = next(n["id"] for n in result_a["nodes"] if n["metadata"]["mcp_kind"] == kind)
        id_b = next(n["id"] for n in result_b["nodes"] if n["metadata"]["mcp_kind"] == kind)
        if (id_a == id_b) is not should_match:
            failures.append(f"cross-config ids wrong for {kind}: {id_a}, {id_b}")
    malformed = tmp_path / "bad" / ".mcp.json"
    malformed.parent.mkdir()
    malformed.write_text("{not valid json", encoding="utf-8")
    oversize = tmp_path / "big" / ".mcp.json"
    oversize.parent.mkdir()
    oversize.write_text('{"mcpServers":{"x":{"command":"npx","args":["' + ("a" * 2_000_000) + '"]}}}', encoding="utf-8")
    error_cases = [
        (_write_json(tmp_path / "missing" / ".mcp.json", {"unrelated": "shape"}), "no mcpServers map"),
        (malformed, "json error"),
        (_write_json(tmp_path / "list" / ".mcp.json", [1, 2, 3]), "root is not an object"),
        (oversize, "too large"),
    ]
    for path, expected in error_cases:
        result = extract_mcp_config(path)
        if result["nodes"] != [] or result["edges"] != [] or expected not in result.get("error", ""):
            failures.append(f"error case mismatch for {path}: {result}")
    nested = extract_mcp_config(_write_json(tmp_path / "nested" / ".mcp.json", {"mcp": {"servers": {"x": {"command": "node", "args": ["dist/index.js"]}}}}))
    if nested.get("error") or "x" not in _by_kind(nested, "mcp_kind", "mcp_server") or "node" not in _by_kind(nested, "mcp_kind", "mcp_command"):
        failures.append(f"nested shape failed: {nested}")
    mixed = extract_mcp_config(_write_json(tmp_path / "mixed" / ".mcp.json", {"mcpServers": {"valid": {"command": "npx", "args": ["@scope/pkg"]}, "broken": ["not"]}}))
    if "valid" not in _by_kind(mixed, "mcp_kind", "mcp_server") or "broken" in _by_kind(mixed, "mcp_kind", "mcp_server"):
        failures.append("non-dict server should be skipped")
    package_cases = [
        ({"x": {"command": "npx", "args": ["-y", "@scope/server-x"]}}, {"@scope/server-x"}, set()),
        ({"x": {"command": "node", "args": ["./local-script.js", "--verbose"]}}, set(), {"mcp_package"}),
        ({"x": {"args": ["@scope/server-x"]}}, {"x"}, {"mcp_command"}),
    ]
    for idx, (servers, required_labels, absent_kinds) in enumerate(package_cases):
        result = extract_mcp_config(_write_json(tmp_path / f"pkg{idx}" / ".mcp.json", {"mcpServers": servers}))
        labels = {n["label"] for n in result["nodes"]}
        kinds = {n["metadata"]["mcp_kind"] for n in result["nodes"]}
        if not required_labels.issubset(labels) or absent_kinds & kinds:
            failures.append(f"package case {idx} mismatch labels={labels} kinds={kinds}")
    if _get_extractor(_write_json(tmp_path / "dispatch" / ".mcp.json", {"mcpServers": {}})) is not extract_mcp_config:
        failures.append("MCP dispatch failed")
    if _get_extractor(_write_json(tmp_path / "dispatch" / "package.json", {"name": "x"})) is not extract_json:
        failures.append("generic JSON dispatch failed")
    assert not failures, "\n".join(failures)


def test_query_and_path_cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    failures = []
    query_graph = tmp_path / "query-graph.json"
    query_graph.write_text(json.dumps(json_graph.node_link_data(_graph(), edges="links")), encoding="utf-8")
    query_cases = [
        (["graph3d", "query", "extract", "--context", "call", "--graph", str(query_graph)], {"Context: call (explicit)", "cluster"}, {"build"}, False),
        (["graph3d", "query", "who calls extract", "--graph", str(query_graph)], {"Context: call (heuristic)", "cluster"}, {"build"}, False),
        (["graph3d", "query", "extract", "--graph", str(query_graph)], {"extract"}, set(), True),
    ]
    for argv, includes, excludes, oversize in query_cases:
        if oversize:
            monkeypatch.setattr("graph3d.security._MAX_GRAPH_FILE_BYTES", 16)
            with pytest.raises(SystemExit):
                _run_main(monkeypatch, argv)
            err = capsys.readouterr().err
            if "exceeds" not in err or "byte cap" not in err:
                failures.append(f"query oversize mismatch: {err}")
            monkeypatch.setattr("graph3d.security._MAX_GRAPH_FILE_BYTES", 10 * 1024 * 1024)
            continue
        _run_main(monkeypatch, argv)
        out = capsys.readouterr().out
        if not all(x in out for x in includes) or any(x in out for x in excludes):
            failures.append(f"query output mismatch: {out}")
    path_data = {
        "directed": False,
        "multigraph": False,
        "graph": {},
        "nodes": [
            {"id": "create_patch", "label": "createPatchHandler()", "source_file": "server/create-patch-handler.ts", "community": 0},
            {"id": "validate", "label": "validateSanitySession()", "source_file": "server/sanity-validate-session.ts", "community": 0},
        ],
        "links": [{"source": "create_patch", "target": "validate", "relation": "calls", "confidence": "EXTRACTED"}],
    }
    path_graph = _write_json(tmp_path / "path-graph.json", path_data)
    path_cases = [
        (["graph3d", "path", "createPatchHandler", "validateSanitySession", "--graph", str(path_graph)], "createPatchHandler() --calls [EXTRACTED]--> validateSanitySession()", "createPatchHandler() <--calls [EXTRACTED]-- validateSanitySession()"),
        (["graph3d", "path", "validateSanitySession", "createPatchHandler", "--graph", str(path_graph)], "validateSanitySession() <--calls [EXTRACTED]-- createPatchHandler()", "validateSanitySession() --calls [EXTRACTED]--> createPatchHandler()"),
    ]
    for argv, expected, forbidden in path_cases:
        _run_main(monkeypatch, argv)
        out = capsys.readouterr().out
        if "Shortest path (1 hops):" not in out or expected not in out or forbidden in out:
            failures.append(f"path direction mismatch: {out}")
    assert not failures, "\n".join(failures)


def test_schema_paths(tmp_path: Path) -> None:
    failures = []
    schema_file = _write_json(
        tmp_path / "session.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "definitions": {
                "SessionEvent": {
                    "type": "object",
                    "properties": {"session_id": {"type": "string"}, "turn_index": {"type": "integer"}},
                    "required": ["session_id"],
                }
            },
        },
    )
    json_result = extract_json(schema_file)
    paths = {n.get("metadata", {}).get("schema_path") for n in json_result["nodes"] if n.get("metadata", {}).get("schema_path")}
    if not {"$.definitions.SessionEvent.properties.session_id.type", "$.definitions.SessionEvent.properties.turn_index.type"}.issubset(paths):
        failures.append(f"JSON schema paths missing: {paths}")
    if not any(e["relation"] == "has_schema_type" for e in json_result["edges"]):
        failures.append("missing has_schema_type")
    if not any(e["relation"] == "matches_schema_terminal" for e in json_result["edges"]):
        failures.append("missing matches_schema_terminal")
    json_errors = [e for e in validate_extraction(json_result) if "does not match any node id" not in e]
    if json_errors or build_from_json(json_result).number_of_nodes() <= 0:
        failures.append(f"JSON validation/build failed: {json_errors}")
    if extract_json_schema_paths(_write_json(tmp_path / "package.json", {"name": "demo"})) != {"nodes": [], "edges": []}:
        failures.append("plain JSON should not emit schema paths")

    db = tmp_path / "session-store.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, summary TEXT)")
    con.execute("CREATE TABLE turns (session_id TEXT NOT NULL, turn_index INTEGER, user_message TEXT)")
    con.execute("CREATE INDEX idx_turns_session ON turns(session_id)")
    con.execute("INSERT INTO sessions(id, summary) VALUES ('s1', 'hello world')")
    con.execute("INSERT INTO turns(session_id, turn_index, user_message) VALUES ('s1', 1, 'hi')")
    con.commit()
    con.close()
    sqlite_result = extract_sqlite_schema(db)
    labels = {n["label"] for n in sqlite_result["nodes"]}
    if not {"sessions (table)", "turns (table)", "sessions.summary", "idx_turns_session (index)"}.issubset(labels):
        failures.append(f"SQLite labels missing: {labels}")
    if not any(e["relation"] == "has_column" for e in sqlite_result["edges"]) or not any(e["relation"] == "has_row" for e in sqlite_result["edges"]):
        failures.append("SQLite edges missing column or row relation")
    if not any(n.get("metadata", {}).get("values", {}).get("summary") == "hello world" for n in _schema_nodes(sqlite_result, "sqlite_row")):
        failures.append("SQLite row value not captured")
    sqlite_errors = [e for e in validate_extraction(sqlite_result) if "does not match any node id" not in e]
    if sqlite_errors:
        failures.append(f"SQLite validation failed: {sqlite_errors}")
    not_db = tmp_path / "not-real.db"
    not_db.write_bytes(b"NOTSQLITE")
    result = extract_sqlite_schema(not_db)
    if result["nodes"] != [] or result["edges"] != [] or "not a sqlite database" not in result.get("error", ""):
        failures.append(f"non-SQLite error mismatch: {result}")
    id_db = tmp_path / "id.db"
    con = sqlite3.connect(id_db)
    con.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY)")
    con.commit()
    con.close()
    if extract_sqlite_schema(id_db)["nodes"][0]["id"] != _make_id(str(id_db)):
        failures.append("SQLite file node id mismatch")
    fts_db = tmp_path / "search.db"
    con = sqlite3.connect(fts_db)
    con.execute("CREATE VIRTUAL TABLE search_index USING fts5(content)")
    con.execute("INSERT INTO search_index(content) VALUES ('hello world')")
    con.commit()
    con.close()
    fts_labels = {n["label"] for n in extract_sqlite_schema(fts_db)["nodes"]}
    shadows = ("search_index_data", "search_index_idx", "search_index_content", "search_index_docsize", "search_index_config")
    if "search_index (table)" not in fts_labels or any(s in label for label in fts_labels for s in shadows):
        failures.append(f"FTS shadow filtering mismatch: {fts_labels}")
    blob_db = tmp_path / "embeddings.db"
    con = sqlite3.connect(blob_db)
    con.execute("CREATE TABLE embeddings (id TEXT, embedding BLOB)")
    con.execute("INSERT INTO embeddings(id, embedding) VALUES (?, ?)", ("e1", b"\x00secret-bytes\xff"))
    con.commit()
    con.close()
    blob_payload = json.dumps(extract_sqlite_schema(blob_db), ensure_ascii=False)
    if "secret-bytes" in blob_payload or "blob:" not in blob_payload:
        failures.append("BLOB values should not be decoded")
    turns_db = tmp_path / "turns.db"
    long_message = "hello\x00" + ("x" * 5_000)
    con = sqlite3.connect(turns_db)
    con.execute("CREATE TABLE turns (id INTEGER PRIMARY KEY, user_message TEXT)")
    con.execute("INSERT INTO turns(user_message) VALUES (?)", (long_message,))
    con.commit()
    con.close()
    captured = _schema_nodes(extract_sqlite_schema(turns_db), "sqlite_row")[0]["metadata"]["values"]["user_message"]
    if "\x00" in captured or len(captured) > 512:
        failures.append(f"SQLite row content was not sanitized/capped: len={len(captured)}")
    many_db = tmp_path / "many.db"
    con = sqlite3.connect(many_db)
    con.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, type TEXT)")
    con.executemany("INSERT INTO events(type) VALUES (?)", [(f"event-{i}",) for i in range(20)])
    con.commit()
    con.close()
    if len(_schema_nodes(extract_sqlite_schema(many_db, max_rows_per_table=3), "sqlite_row")) != 3:
        failures.append("SQLite row cap not enforced")
    extracted = extract([many_db], cache_root=tmp_path, parallel=False)
    if not any(n.get("metadata", {}).get("schema_kind") == "sqlite_table" for n in extracted["nodes"]):
        failures.append("extract should dispatch SQLite files")
    optional_db = tmp_path / "optional.sqlite"
    con = sqlite3.connect(optional_db)
    con.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, type TEXT)")
    con.commit()
    con.close()
    real_import = builtins.__import__

    def patched_import(name: str, *args, **kwargs):
        if name == "tree_sitter_sql":
            raise ImportError("optional sql extra absent")
        return real_import(name, *args, **kwargs)

    with mock.patch("builtins.__import__", side_effect=patched_import):
        optional = extract([optional_db], cache_root=tmp_path, parallel=False)
    if not any(n.get("metadata", {}).get("schema_kind") == "sqlite_table" for n in optional["nodes"]):
        failures.append("SQLite dispatch should not require tree_sitter_sql")
    if classify_file(Path("session-store.db")) != FileType.CODE or classify_file(Path("events.sqlite")) != FileType.CODE:
        failures.append("SQLite detect classification mismatch")
    if count_words(db) != 0:
        failures.append("SQLite count_words should be zero")
    api_schema = _write_json(tmp_path / "api.schema.json", {"type": "object", "properties": {"session_id": {"type": "string"}}})
    session_db = tmp_path / "session.db"
    con = sqlite3.connect(session_db)
    con.execute("CREATE TABLE turns (session_id TEXT NOT NULL)")
    con.commit()
    con.close()
    json_terminals = {n["id"] for n in _schema_nodes(extract_json(api_schema), "schema_terminal") if n["label"] == "session_id"}
    sqlite_terminals = {n["id"] for n in _schema_nodes(extract_sqlite_schema(session_db, include_content=False), "schema_terminal") if n["label"] == "session_id"}
    if not json_terminals or json_terminals != sqlite_terminals:
        failures.append(f"schema terminal mismatch: json={json_terminals} sqlite={sqlite_terminals}")
    assert not failures, "\n".join(failures)
