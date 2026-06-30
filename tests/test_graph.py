from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import networkx as nx
from networkx.readwrite import json_graph
import pytest

import graph3d.__main__ as mainmod
from graph3d.analyze import (
    _file_category,
    _is_concept_node,
    _is_json_key_node,
    _surprise_score,
    find_import_cycles,
    god_nodes,
    graph_diff,
    surprising_connections,
)
from graph3d.build import (
    build,
    build_from_json,
    build_merge,
    edge_data,
    edge_datas,
    prefix_graph_for_global,
    prune_repo_from_graph,
)
from graph3d.cluster import cluster, cohesion_score, remap_communities_to_previous, score_all
from graph3d.diagnostics import (
    diagnose_extraction,
    diagnose_file,
    format_diagnostic_json,
    format_diagnostic_report,
    scan_producer_suppression_sites,
)
from graph3d.export import attach_hyperedges, to_json
from graph3d.extract import _make_id
from graph3d.multigraph_compat import (
    CapabilityCheck,
    MultigraphCapabilityResult,
    probe_multigraph_capabilities,
    require_multigraph_capabilities,
)
from graph3d.report import generate


FIXTURES = Path(__file__).parent / "fixtures"


def _load_extraction() -> dict:
    return json.loads((FIXTURES / "extraction.json").read_text())


def _fixture_graph() -> nx.Graph:
    return build_from_json(_load_extraction())


def _record(failures: list[str], label: str, predicate: bool, detail: str = "") -> None:
    if not predicate:
        failures.append(f"{label}: {detail or 'failed'}")


def _make_graph(nodes: list[dict], edges: list[dict] | None = None) -> nx.Graph:
    graph = nx.Graph()
    for node in nodes:
        node_id = node["id"]
        graph.add_node(node_id, **{k: v for k, v in node.items() if k != "id"})
    for edge in edges or []:
        graph.add_edge(
            edge["source"],
            edge["target"],
            **{k: v for k, v in edge.items() if k not in ("source", "target")},
        )
    return graph


def _graph_to_json(graph: nx.Graph, path: Path) -> None:
    try:
        data = json_graph.node_link_data(graph, edges="links")
    except TypeError:
        data = json_graph.node_link_data(graph)
    path.write_text(json.dumps(data), encoding="utf-8")


def _parallel_edge_extraction() -> dict:
    return {
        "nodes": [
            {"id": "a", "label": "A", "file_type": "code", "source_file": "a.py"},
            {"id": "b", "label": "B", "file_type": "code", "source_file": "b.py"},
        ],
        "edges": [
            {
                "source": "a",
                "target": "b",
                "relation": "calls",
                "confidence": "EXTRACTED",
                "source_file": "a.py",
                "source_location": "L1",
            },
            {
                "source": "a",
                "target": "b",
                "relation": "imports",
                "confidence": "EXTRACTED",
                "source_file": "a.py",
                "source_location": "L2",
            },
        ],
        "input_tokens": 0,
        "output_tokens": 0,
    }


SAMPLE_EXTRACTION = {
    "nodes": [
        {"id": "BasicAuth", "label": "BasicAuth", "file_type": "code", "source_file": "auth.py"},
        {"id": "DigestAuth", "label": "DigestAuth", "file_type": "code", "source_file": "auth.py"},
        {"id": "Request", "label": "Request", "file_type": "code", "source_file": "http.py"},
        {"id": "Response", "label": "Response", "file_type": "code", "source_file": "http.py"},
        {"id": "BaseClient", "label": "BaseClient", "file_type": "code", "source_file": "client.py"},
    ],
    "edges": [
        {
            "source": "BasicAuth",
            "target": "Request",
            "relation": "uses",
            "confidence": "EXTRACTED",
            "confidence_score": 1.0,
            "source_file": "auth.py",
        },
    ],
    "hyperedges": [
        {
            "id": "auth_flow",
            "label": "Auth Flow",
            "nodes": ["BasicAuth", "DigestAuth", "Request", "Response", "BaseClient"],
            "relation": "participate_in",
            "confidence": "INFERRED",
            "confidence_score": 0.75,
            "source_file": "auth.py",
        }
    ],
    "input_tokens": 10,
    "output_tokens": 5,
}


SAMPLE_DETECTION = {
    "total_files": 3,
    "total_words": 500,
    "files": {"code": ["auth.py", "http.py", "client.py"]},
    "skipped_sensitive": [],
    "warning": None,
}


def _hyper_report(graph: nx.Graph) -> str:
    return generate(
        graph,
        {0: list(graph.nodes())},
        {0: 1.0},
        {0: "All"},
        [{"label": "BasicAuth", "degree": 2}],
        [],
        SAMPLE_DETECTION,
        {"input": 10, "output": 5},
        ".",
    )


def _diagnostic_fixture() -> dict:
    return {
        "nodes": [
            {"id": "a", "label": "A", "file_type": "code", "source_file": "a.py"},
            {"id": "b", "label": "B", "file_type": "code", "source_file": "b.py"},
            {"id": "c", "label": "C", "file_type": "code", "source_file": "c.py"},
        ],
        "edges": [
            {
                "source": "a",
                "target": "b",
                "relation": "calls",
                "confidence": "EXTRACTED",
                "source_file": "a.py",
                "source_location": "L1",
                "context": "call",
            },
            {
                "source": "a",
                "target": "b",
                "relation": "imports",
                "confidence": "EXTRACTED",
                "source_file": "a.py",
                "source_location": "L2",
                "context": "import",
            },
            {
                "source": "a",
                "target": "b",
                "relation": "calls",
                "confidence": "INFERRED",
                "source_file": "a.py",
                "source_location": "L3",
                "context": "call",
            },
            {
                "source": "a",
                "target": "b",
                "relation": "calls",
                "confidence": "EXTRACTED",
                "source_file": "a.py",
                "source_location": "L1",
                "context": "call",
            },
            {"source": "a", "target": "missing", "relation": "calls", "confidence": "EXTRACTED", "source_file": "a.py"},
            {"source": "a", "relation": "calls", "confidence": "EXTRACTED", "source_file": "a.py"},
            {"source": "c", "target": "c", "relation": "references", "confidence": "EXTRACTED", "source_file": "c.py"},
        ],
    }


def _simple_graph(nodes: list[tuple[str, str]], edges: list[tuple[str, str, str, str]]) -> nx.Graph:
    graph = nx.Graph()
    for node_id, label in nodes:
        graph.add_node(node_id, label=label, source_file="test.py")
    for source, target, relation, confidence in edges:
        graph.add_edge(source, target, relation=relation, confidence=confidence)
    return graph


def _make_cross_lang_graph() -> nx.Graph:
    graph = nx.Graph()
    graph.add_node("py_auth", label="AuthError", source_file="backend/auth.py", file_type="code")
    graph.add_node("ts_member", label="Member", source_file="frontend/types.ts", file_type="code")
    graph.add_node("py_a", label="ServiceA", source_file="backend/service.py", file_type="code")
    graph.add_node("py_b", label="ServiceB", source_file="backend/utils.py", file_type="code")
    return graph


def _make_code_doc_graph() -> nx.Graph:
    graph = nx.Graph()
    graph.add_node("py_fn", label="ProcessData", source_file="src/processor.py", file_type="code")
    graph.add_node("md_doc", label="README Section", source_file="docs/readme.md", file_type="document")
    graph.add_node("py_a", label="ServiceA", source_file="src/service.py", file_type="code")
    graph.add_node("py_b", label="ServiceB", source_file="src/utils.py", file_type="code")
    return graph


def _make_file_node(path: str) -> tuple[str, dict]:
    return _make_id(path), {"label": Path(path).name, "source_file": path, "file_type": "code"}


def _make_cycle_graph_directed() -> nx.DiGraph:
    graph = nx.DiGraph()
    a_id, a = _make_file_node("src/a.ts")
    b_id, b = _make_file_node("src/b.ts")
    c_id, c = _make_file_node("src/c.ts")
    d_id, d = _make_file_node("src/d.ts")
    ext_id = _make_id("react")
    graph.add_node(a_id, **a)
    graph.add_node(b_id, **b)
    graph.add_node(c_id, **c)
    graph.add_node(d_id, **d)
    graph.add_node(ext_id, label="react", file_type="code")
    graph.add_edge(a_id, b_id, relation="imports_from", source_file="src/a.ts", confidence="EXTRACTED")
    graph.add_edge(b_id, a_id, relation="imports_from", source_file="src/b.ts", confidence="EXTRACTED")
    graph.add_edge(b_id, c_id, relation="imports_from", source_file="src/b.ts", confidence="EXTRACTED")
    graph.add_edge(c_id, d_id, relation="imports_from", source_file="src/c.ts", confidence="EXTRACTED")
    graph.add_edge(d_id, b_id, relation="imports_from", source_file="src/d.ts", confidence="EXTRACTED")
    graph.add_edge(c_id, c_id, relation="imports_from", source_file="src/c.ts", confidence="EXTRACTED")
    graph.add_edge(a_id, ext_id, relation="calls", source_file="src/a.ts", confidence="INFERRED")
    graph.add_edge(a_id, ext_id, relation="contains", source_file="src/a.ts", confidence="EXTRACTED")
    graph.add_edge(a_id, ext_id, relation="imports_from", source_file="src/a.ts", confidence="EXTRACTED")
    return graph


def test_build_from_json(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    failures: list[str] = []
    graph = _fixture_graph()
    _record(failures, "fixture node count", graph.number_of_nodes() == 4, str(graph.number_of_nodes()))
    _record(failures, "fixture edge count", graph.number_of_edges() == 4, str(graph.number_of_edges()))
    _record(failures, "node label", graph.nodes["n_transformer"]["label"] == "Transformer")
    _record(failures, "edge confidence", graph.edges["n_attention", "n_concept_attn"]["confidence"] == "INFERRED")
    _record(failures, "ambiguous edge", graph.edges["n_layernorm", "n_concept_attn"]["confidence"] == "AMBIGUOUS")

    build_cases = [
        (
            "legacy node source",
            {"nodes": [{"id": "n1", "label": "A", "file_type": "code", "source": "a.py"}], "edges": []},
            lambda g: "source_file" in g.nodes["n1"] and g.nodes["n1"]["source_file"] == "a.py" and "source" not in g.nodes["n1"],
        ),
        (
            "legacy edge from to",
            {
                "nodes": [
                    {"id": "n1", "label": "A", "file_type": "code", "source_file": "a.py"},
                    {"id": "n2", "label": "B", "file_type": "code", "source_file": "b.py"},
                ],
                "edges": [{"from": "n1", "to": "n2", "relation": "calls", "confidence": "EXTRACTED", "source_file": "a.py"}],
            },
            lambda g: g.number_of_edges() == 1,
        ),
        (
            "backslash source normalization",
            {
                "nodes": [
                    {"id": "n1", "label": "A", "file_type": "code", "source_file": r"src\middleware\auth.py"},
                    {"id": "n2", "label": "B", "file_type": "code", "source_file": "src/middleware/auth.py"},
                ],
                "edges": [],
            },
            lambda g: {g.nodes[n]["source_file"] for n in g.nodes()} == {"src/middleware/auth.py"},
        ),
        (
            "invalid file type",
            {"nodes": [{"id": "n1", "label": "Bad", "file_type": "weird_type", "source_file": "a.py"}], "edges": []},
            lambda g: g.nodes["n1"]["file_type"] == "concept",
        ),
        (
            "file type synonyms",
            {
                "nodes": [
                    {"id": "n1", "label": "MD", "file_type": "markdown", "source_file": "a.md"},
                    {"id": "n2", "label": "Tool", "file_type": "tool", "source_file": "b.py"},
                    {"id": "n3", "label": "Pat", "file_type": "pattern", "source_file": "c.md"},
                ],
                "edges": [],
            },
            lambda g: [g.nodes[n]["file_type"] for n in ("n1", "n2", "n3")] == ["document", "code", "concept"],
        ),
    ]
    for label, extraction, check in build_cases:
        _record(failures, label, check(build_from_json(extraction)))

    capsys.readouterr()
    for label, extraction, expected in [
        ("none file type", {"nodes": [{"id": "n1", "label": "Stub", "file_type": None, "source_file": "a.py"}], "edges": []}, "concept"),
        ("missing file type", {"nodes": [{"id": "n1", "label": "Bare", "source_file": "a.py"}], "edges": []}, "concept"),
    ]:
        built = build_from_json(extraction)
        err = capsys.readouterr().err
        _record(failures, label, built.nodes["n1"]["file_type"] == expected and "invalid file_type" not in err and "missing required field" not in err)

    merged = build(
        [
            {"nodes": [{"id": "n1", "label": "A", "file_type": "code", "source_file": "a.py"}], "edges": []},
            {
                "nodes": [{"id": "n2", "label": "B", "file_type": "document", "source_file": "b.md"}],
                "edges": [{"source": "n1", "target": "n2", "relation": "references", "confidence": "INFERRED", "source_file": "b.md"}],
            },
        ]
    )
    _record(failures, "build merges extractions", merged.number_of_nodes() == 2 and merged.number_of_edges() == 1)

    from graph3d.extract import extract_js

    js_file = tmp_path / "x.js"
    js_file.write_text("function b() {}\nfunction a() { b(); }\n", encoding="utf-8")
    extraction = extract_js(js_file)
    call_edges = [edge for edge in extraction["edges"] if edge["relation"] == "calls"]
    _record(failures, "extract one call edge", len(call_edges) == 1)
    truth_src, truth_tgt = call_edges[0]["source"], call_edges[0]["target"]
    graph_path = tmp_path / "graph.json"
    assert to_json(build([extraction], dedup=False), {}, str(graph_path), force=True)
    assert to_json(build_merge([], graph_path, dedup=False), {}, str(graph_path), force=True)
    reloaded_calls = [edge for edge in json.loads(graph_path.read_text()).get("links", []) if edge.get("relation") == "calls"]
    _record(failures, "build_merge preserves calls direction", reloaded_calls[0]["source"] == truth_src and reloaded_calls[0]["target"] == truth_tgt)

    bidirectional = {
        "nodes": [
            {"id": "a_handler", "label": "a", "file_type": "code", "source_file": "a.ts"},
            {"id": "z_emitter", "label": "z", "file_type": "code", "source_file": "z.ts"},
        ],
        "edges": [
            {"source": "a_handler", "target": "z_emitter", "relation": "calls", "confidence": "EXTRACTED", "source_file": "a.ts"},
            {"source": "z_emitter", "target": "a_handler", "relation": "calls", "confidence": "EXTRACTED", "source_file": "z.ts"},
        ],
    }
    bidi_graph = build_from_json(bidirectional)
    _record(failures, "bidirectional collapse count", bidi_graph.number_of_edges() == 1)
    _record(failures, "bidirectional first direction", edge_data(bidi_graph, "a_handler", "z_emitter")["_src"] == "a_handler")

    simple_parallel = build_from_json(_parallel_edge_extraction(), directed=True)
    multi_parallel = build_from_json(_parallel_edge_extraction(), directed=True, multigraph=True)
    _record(failures, "simple graph collapses parallel edges", isinstance(simple_parallel, nx.DiGraph) and simple_parallel.number_of_edges("a", "b") == 1)
    _record(failures, "multigraph preserves parallel edges", isinstance(multi_parallel, nx.MultiDiGraph) and multi_parallel.number_of_edges("a", "b") == 2)
    _record(failures, "multigraph stable keys", set(multi_parallel["a"]["b"].keys()) == set(build_from_json(_parallel_edge_extraction(), directed=True, multigraph=True)["a"]["b"].keys()))
    _record(failures, "build multigraph parameter", build([_parallel_edge_extraction()], directed=True, multigraph=True, dedup=False).number_of_edges("a", "b") == 2)
    graph_path = tmp_path / "parallel.json"
    assert to_json(multi_parallel, {}, str(graph_path), force=True)
    round_trip = build_merge([], graph_path, directed=True, multigraph=True, dedup=False)
    _record(failures, "build_merge multigraph round trip", isinstance(round_trip, nx.MultiDiGraph) and round_trip.number_of_edges("a", "b") == 2 and {d["relation"] for d in edge_datas(round_trip, "a", "b")} == {"calls", "imports"})

    for label, maker, expected_count in [
        ("edge_data simple", lambda: nx.Graph(), 1),
        ("edge_data multigraph", lambda: nx.MultiGraph(), 2),
        ("edge_data multidigraph", lambda: nx.MultiDiGraph(), 2),
    ]:
        edge_graph = maker()
        edge_graph.add_edge("a", "b", relation="calls", confidence="EXTRACTED")
        if expected_count == 2:
            edge_graph.add_edge("a", "b", relation="references", confidence="INFERRED")
        _record(failures, label, isinstance(edge_data(edge_graph, "a", "b"), dict) and len(edge_datas(edge_graph, "a", "b")) == expected_count)

    node_link = {
        "directed": False,
        "multigraph": True,
        "graph": {},
        "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "links": [
            {"source": "a", "target": "b", "relation": "calls"},
            {"source": "a", "target": "b", "relation": "references"},
        ],
    }
    try:
        node_link_graph = json_graph.node_link_graph(node_link, edges="links")
    except TypeError:
        node_link_graph = json_graph.node_link_graph(node_link)
    _record(failures, "node_link multigraph helpers", isinstance(node_link_graph, nx.MultiGraph) and len(edge_datas(node_link_graph, "a", "b")) == 2)

    root = tmp_path / "proj"
    root.mkdir()
    abs_path = str(root / "docs" / "overview.md")
    rel_graph = build_from_json({"nodes": [{"id": "overview_intro", "label": "Intro", "source_file": abs_path, "file_type": "document"}], "edges": []}, root=root)
    _record(failures, "build_from_json relativizes absolute source", rel_graph.nodes["overview_intro"]["source_file"] == "docs/overview.md")
    built_rel = build([{"nodes": [{"id": "main_fn", "label": "main", "source_file": str(root / "src" / "main.py"), "file_type": "code"}], "edges": []}], root=root)
    _record(failures, "build passes root", built_rel.nodes["main_fn"]["source_file"] == "src/main.py")
    unchanged = build_from_json({"nodes": [{"id": "foo_bar", "label": "bar", "source_file": "src/foo.py", "file_type": "code"}], "edges": []}, root=root)
    _record(failures, "relative source unchanged", unchanged.nodes["foo_bar"]["source_file"] == "src/foo.py")

    graph_path = tmp_path / "prune.json"
    chunk = {
        "nodes": [
            {"id": "n1", "label": "login", "file_type": "code", "source_file": "module_a/auth.py"},
            {"id": "n2", "label": "format_date", "file_type": "code", "source_file": "module_b/utils.py"},
        ],
        "edges": [{"source": "n1", "target": "n2", "relation": "calls", "confidence": "EXTRACTED", "source_file": "module_b/utils.py"}],
    }
    graph_path.write_text(json.dumps(nx.node_link_data(build([chunk], dedup=False), edges="edges")), encoding="utf-8")
    pruned = build_merge([], graph_path, prune_sources=[str(root / "module_b" / "utils.py")], dedup=False, root=root)
    _record(failures, "prune absolute path", {d["label"] for _, d in pruned.nodes(data=True)} == {"login"} and pruned.number_of_edges() == 0)
    graph_path.write_text(json.dumps(nx.node_link_data(build([{"nodes": [{"id": "n1", "label": "parse_date", "file_type": "code", "source_file": "module_b/utils.py"}], "edges": []}], dedup=False), edges="edges")), encoding="utf-8")
    pruned = build_merge([], graph_path, prune_sources=[str(root / "module_b" / "utils.py").replace("/", "\\")], dedup=False, root=root)
    _record(failures, "prune backslash path", "parse_date" not in {d["label"] for _, d in pruned.nodes(data=True)})

    for label, action in [
        ("build_merge oversized", lambda: build_merge([], graph_path, dedup=False)),
    ]:
        graph_path.write_text(json.dumps({"nodes": [], "links": []}), encoding="utf-8")
        monkeypatch.setattr("graph3d.security._MAX_GRAPH_FILE_BYTES", 8)
        with pytest.raises(ValueError, match="exceeds"):
            action()
        _record(failures, label, True)

    assert not failures, "\n".join(failures)


def test_cluster_communities(capsys: pytest.CaptureFixture[str]) -> None:
    failures: list[str] = []
    graph = _fixture_graph()
    communities = cluster(graph)
    _record(failures, "cluster returns dict", isinstance(communities, dict))
    _record(failures, "cluster covers nodes", {n for nodes in communities.values() for n in nodes} == set(graph.nodes))
    score_cases = [
        ("complete graph", nx.relabel_nodes(nx.complete_graph(4), {i: str(i) for i in range(4)}), ["0", "1", "2", "3"], 1.0),
        ("single node", nx.Graph(), ["a"], 1.0),
        ("disconnected", nx.Graph(), ["a", "b", "c"], 0.0),
    ]
    score_cases[1][1].add_node("a")
    score_cases[2][1].add_nodes_from(["a", "b", "c"])
    for label, score_graph, nodes, expected in score_cases:
        _record(failures, f"cohesion {label}", cohesion_score(score_graph, nodes) == expected)
    for community_id, nodes in communities.items():
        score = cohesion_score(graph, nodes)
        _record(failures, f"cohesion range {community_id}", 0.0 <= score <= 1.0, str(score))
    _record(failures, "score_all keys", set(score_all(graph, communities)) == set(communities))
    cluster(graph)
    captured = capsys.readouterr()
    _record(failures, "cluster stdout quiet", captured.out == "", repr(captured.out))
    for line in captured.err.splitlines():
        _record(failures, "cluster stderr no ANSI", "\x1b" not in line, repr(line))
    remap_cases = [
        ({10: ["a", "b", "c"], 11: ["d", "e"]}, {"a": 5, "b": 5, "c": 5, "d": 1, "e": 1}, {5: ["a", "b", "c"], 1: ["d", "e"]}),
        ({7: ["x", "y", "z"], 8: ["m"]}, {"a": 3}, {0: ["x", "y", "z"], 1: ["m"]}),
    ]
    for communities_in, previous, expected in remap_cases:
        remapped = remap_communities_to_previous(communities_in, previous)
        _record(failures, f"remap {expected}", remapped == expected, repr(remapped))
    assert not failures, "\n".join(failures)


@pytest.mark.filterwarnings("ignore:Tensorflow not installed; ParametricUMAP will be unavailable:ImportWarning:umap")
@pytest.mark.filterwarnings(r"ignore:Please import `random` from the `scipy\.sparse` namespace.*:DeprecationWarning:hyppo\.independence\.hhg")
@pytest.mark.filterwarnings(r"ignore:The keyword argument 'nopython=False' was supplied.*:Warning:numba\.core\.decorators")
def test_analyze_god_nodes_and_surprises() -> None:
    failures: list[str] = []
    graph = _fixture_graph()
    gods = god_nodes(graph, top_n=10)
    _record(failures, "god_nodes list", isinstance(gods, list) and len(gods) <= 10)
    _record(failures, "god_nodes sorted", [r["degree"] for r in gods] == sorted([r["degree"] for r in gods], reverse=True))
    _record(failures, "god_nodes keys", {"id", "label", "degree"}.issubset(gods[0]))
    communities = cluster(graph)
    surprises = surprising_connections(graph, communities)
    _record(failures, "surprises present", len(surprises) > 0)
    for surprise in surprises:
        _record(failures, "surprise cross source", surprise["source_files"][0] != surprise["source_files"][1], repr(surprise))
        _record(failures, "surprise keys", {"source", "target", "source_files", "confidence"}.issubset(surprise))
        _record(failures, "surprise why", isinstance(surprise.get("why"), str) and len(surprise["why"]) > 0)

    graph_with_concept = _fixture_graph()
    graph_with_concept.add_node("concept_x", label="Abstract Concept", file_type="document", source_file="")
    graph_with_concept.add_edge("n_transformer", "concept_x", relation="relates_to", confidence="INFERRED", source_file="", weight=0.5)
    concept_labels = [s["source"] for s in surprising_connections(graph_with_concept, cluster(graph_with_concept))] + [s["target"] for s in surprising_connections(graph_with_concept, cluster(graph_with_concept))]
    _record(failures, "concept nodes excluded", "Abstract Concept" not in concept_labels)

    single = nx.Graph()
    for prefix, offset in [("a", 0), ("b", 10)]:
        for i in range(5):
            single.add_node(f"{prefix}{i}", label=f"{prefix.upper()}{i}", file_type="code", source_file="single.py", source_location=f"L{i + offset}")
        for i in range(4):
            single.add_edge(f"{prefix}{i}", f"{prefix}{i + 1}", relation="calls", confidence="EXTRACTED", source_file="single.py", weight=1.0)
    single.add_edge("a4", "b0", relation="references", confidence="INFERRED", source_file="single.py", weight=0.5)
    _record(failures, "single-file community bridge", len(surprising_connections(single, cluster(single))) > 0)

    score_cases = []
    score_graph = nx.Graph()
    for node_id, label, source in [("a", "Alpha", "repo1/model.py"), ("b", "Beta", "repo2/train.py"), ("c", "Gamma", "repo1/data.py"), ("d", "Delta", "repo2/eval.py")]:
        score_graph.add_node(node_id, label=label, source_file=source, file_type="code")
    score_graph.add_edge("a", "b", relation="calls", confidence="AMBIGUOUS", weight=1.0, source_file="repo1/model.py")
    score_graph.add_edge("c", "d", relation="calls", confidence="EXTRACTED", weight=1.0, source_file="repo1/data.py")
    score_cases.append(("ambiguous scores higher", score_graph, ("a", "b", "repo1/model.py", "repo2/train.py"), ("c", "d", "repo1/data.py", "repo2/eval.py"), ">"))

    cross_type = nx.Graph()
    for node_id, label, source in [("a", "Transformer", "code/model.py"), ("b", "FlashAttn", "papers/flash.pdf"), ("c", "Trainer", "code/train.py"), ("d", "Dataset", "code/data.py")]:
        cross_type.add_node(node_id, label=label, source_file=source, file_type="code")
    cross_type.add_edge("a", "b", relation="references", confidence="EXTRACTED", weight=1.0, source_file="code/model.py")
    cross_type.add_edge("c", "d", relation="calls", confidence="EXTRACTED", weight=1.0, source_file="code/train.py")
    score_cases.append(("cross type scores higher", cross_type, ("a", "b", "code/model.py", "papers/flash.pdf"), ("c", "d", "code/train.py", "code/data.py"), ">"))

    for label, score_graph, left, right, op in score_cases:
        left_score, reasons = _surprise_score(score_graph, left[0], left[1], score_graph.edges[left[0], left[1]], {"a": 0, "b": 1, "c": 0, "d": 1}, left[2], left[3])
        right_score, _ = _surprise_score(score_graph, right[0], right[1], score_graph.edges[right[0], right[1]], {"a": 0, "b": 1, "c": 0, "d": 1}, right[2], right[3])
        _record(failures, label, left_score > right_score if op == ">" else left_score <= right_score, f"{left_score} vs {right_score}")
        if label == "cross type scores higher":
            _record(failures, "cross type reason", any("code" in reason and "paper" in reason for reason in reasons), repr(reasons))

    precomputed = nx.Graph()
    for node_id, source in [("hub", "repo1/hub.py"), ("leaf", "repo2/leaf.py"), ("n1", "repo1/n1.py"), ("n2", "repo1/n2.py"), ("n3", "repo1/n3.py"), ("n4", "repo1/n4.py")]:
        precomputed.add_node(node_id, label=node_id, source_file=source, file_type="code")
    for node in ("leaf", "n1", "n2", "n3", "n4"):
        precomputed.add_edge("hub", node, relation="calls", confidence="EXTRACTED", weight=1.0)
    args = (precomputed, "hub", "leaf", precomputed.edges["hub", "leaf"], {"hub": 0, "leaf": 1}, "repo1/hub.py", "repo2/leaf.py")
    _record(failures, "precomputed degrees", _surprise_score(*args) == _surprise_score(*args, dict(precomputed.degree())))

    relation_cases = [
        ("cross language inferred calls suppressed", _make_cross_lang_graph(), ("py_auth", "ts_member", "calls", "INFERRED", "backend/auth.py", "frontend/types.ts"), "<="),
        ("cross language inferred uses suppressed", _make_cross_lang_graph(), ("py_auth", "ts_member", "uses", "INFERRED", "backend/auth.py", "frontend/types.ts"), "<="),
        ("cross language semantic not suppressed", _make_cross_lang_graph(), ("py_auth", "ts_member", "semantically_similar_to", "INFERRED", "backend/auth.py", "frontend/types.ts"), ">"),
        ("code doc inferred calls suppressed", _make_code_doc_graph(), ("py_fn", "md_doc", "calls", "INFERRED", "src/processor.py", "docs/readme.md"), "<="),
        ("code doc inferred uses suppressed", _make_code_doc_graph(), ("py_fn", "md_doc", "uses", "INFERRED", "src/processor.py", "docs/readme.md"), "<="),
        ("code doc semantic not suppressed", _make_code_doc_graph(), ("py_fn", "md_doc", "semantically_similar_to", "INFERRED", "src/processor.py", "docs/readme.md"), ">"),
        ("code paper inferred not suppressed", nx.Graph(), ("py_model", "pdf_paper", "calls", "INFERRED", "src/model.py", "papers/vaswani.pdf"), ">"),
        ("unknown extension inferred suppressed", nx.Graph(), ("py_fn", "unk", "calls", "INFERRED", "src/handler.py", "vendor/unknown.xyz"), "<="),
    ]
    for label, rel_graph, spec, op in relation_cases:
        source, target, relation, confidence, source_file, target_file = spec
        if not rel_graph.nodes:
            for node, file_name in [(source, source_file), (target, target_file), ("py_a", "src/a.py"), ("py_b", "src/b.py")]:
                if file_name.endswith(".pdf"):
                    file_type = "paper"
                elif file_name.endswith((".py", ".ts")):
                    file_type = "code"
                else:
                    file_type = "document"
                rel_graph.add_node(node, label=node, source_file=file_name, file_type=file_type)
        rel_graph.add_edge(source, target, relation=relation, confidence=confidence, weight=0.8, source_file=source_file)
        rel_graph.add_edge("py_a", "py_b", relation="calls", confidence="EXTRACTED", weight=1.0, source_file="src/a.py")
        nc = {source: 0, target: 1, "py_a": 0, "py_b": 0}
        score, _ = _surprise_score(rel_graph, source, target, rel_graph.edges[source, target], nc, source_file, target_file)
        baseline, _ = _surprise_score(rel_graph, "py_a", "py_b", rel_graph.edges["py_a", "py_b"], nc, "src/a.py", "src/b.py")
        _record(failures, label, score > baseline if op == ">" else score <= baseline, f"{score} vs {baseline}")
    same_lang = nx.Graph()
    for node, file_name in [("py_a", "src/a.py"), ("py_b", "src/b.py"), ("py_c", "src/c.py"), ("py_d", "src/d.py")]:
        same_lang.add_node(node, label=node, source_file=file_name, file_type="code")
    same_lang.add_edge("py_a", "py_b", relation="calls", confidence="INFERRED", weight=0.8, source_file="src/a.py")
    same_lang.add_edge("py_c", "py_d", relation="calls", confidence="EXTRACTED", weight=1.0, source_file="src/c.py")
    nc_same = {"py_a": 0, "py_b": 1, "py_c": 0, "py_d": 1}
    score_inf, _ = _surprise_score(same_lang, "py_a", "py_b", same_lang.edges["py_a", "py_b"], nc_same, "src/a.py", "src/b.py")
    score_ext, _ = _surprise_score(same_lang, "py_c", "py_d", same_lang.edges["py_c", "py_d"], nc_same, "src/c.py", "src/d.py")
    _record(failures, "same language inferred not suppressed", score_inf > score_ext, f"{score_inf} vs {score_ext}")
    extracted_cases = [
        ("cross language extracted", _make_cross_lang_graph(), ("py_auth", "ts_member", "backend/auth.py", "frontend/types.ts")),
        ("code doc extracted", _make_code_doc_graph(), ("py_fn", "md_doc", "src/processor.py", "docs/readme.md")),
    ]
    for label, rel_graph, spec in extracted_cases:
        source, target, source_file, target_file = spec
        rel_graph.add_edge(source, target, relation="calls", confidence="EXTRACTED", weight=1.0, source_file=source_file)
        score, _ = _surprise_score(rel_graph, source, target, rel_graph.edges[source, target], {source: 0, target: 1}, source_file, target_file)
        _record(failures, label, score >= 1, str(score))

    file_cases = {
        "model.py": "code",
        "flash.pdf": "paper",
        "diagram.png": "image",
        "notes.md": "doc",
        "app.swift": "code",
        "plugin.lua": "code",
        "build.zig": "code",
        "deploy.ps1": "code",
        "server.ex": "code",
        "component.jsx": "code",
        "analysis.jl": "code",
        "view.m": "code",
        "vendor/random.xyz": "doc",
    }
    for file_name, expected in file_cases.items():
        _record(failures, f"file category {file_name}", _file_category(file_name) == expected)
    concept_graph = nx.Graph()
    concept_graph.add_node("c1", source_file="")
    concept_graph.add_node("n1", source_file="model.py")
    _record(failures, "concept empty source", _is_concept_node(concept_graph, "c1") is True)
    _record(failures, "concept real file", _is_concept_node(concept_graph, "n1") is False)

    diff_cases = [
        ("new nodes", _simple_graph([("n1", "Alpha"), ("n2", "Beta")], []), _simple_graph([("n1", "Alpha"), ("n2", "Beta"), ("n3", "Gamma")], []), lambda d: len(d["new_nodes"]) == 1 and d["new_nodes"][0]["id"] == "n3" and "1 new node" in d["summary"]),
        ("removed nodes", _simple_graph([("n1", "Alpha"), ("n2", "Beta"), ("n3", "Gamma")], []), _simple_graph([("n1", "Alpha"), ("n2", "Beta")], []), lambda d: len(d["removed_nodes"]) == 1 and d["removed_nodes"][0]["id"] == "n3" and "removed" in d["summary"]),
        ("new edges", _simple_graph([("n1", "Alpha"), ("n2", "Beta"), ("n3", "Gamma")], [("n1", "n2", "calls", "EXTRACTED")]), _simple_graph([("n1", "Alpha"), ("n2", "Beta"), ("n3", "Gamma")], [("n1", "n2", "calls", "EXTRACTED"), ("n2", "n3", "uses", "INFERRED")]), lambda d: len(d["new_edges"]) == 1 and d["new_edges"][0]["relation"] == "uses" and "new edge" in d["summary"]),
        ("empty diff", _simple_graph([("n1", "Alpha"), ("n2", "Beta")], [("n1", "n2", "calls", "EXTRACTED")]), _simple_graph([("n1", "Alpha"), ("n2", "Beta")], [("n1", "n2", "calls", "EXTRACTED")]), lambda d: d["summary"] == "no changes" and not d["new_nodes"] and not d["removed_nodes"] and not d["new_edges"] and not d["removed_edges"]),
    ]
    for label, old, new, check in diff_cases:
        _record(failures, f"graph_diff {label}", check(graph_diff(old, new)))

    for label, source_file, expected in [
        ("json noise label", "schema.json", True),
        ("non-json file", "model.py", False),
        ("json real label", "schema.json", False),
    ]:
        json_graph_noise = nx.Graph()
        json_graph_noise.add_node("node", label="name" if label != "json real label" else "UserProfile", source_file=source_file)
        _record(failures, f"is_json_key {label}", _is_json_key_node(json_graph_noise, "node") is expected)
    for dep_key in ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies", "bundledDependencies"]:
        dep_graph = nx.Graph()
        dep_graph.add_node("real_node", label="AuthService", source_file="src/auth.py", file_type="code")
        dep_graph.add_node("dep_node", label=dep_key, source_file="frontend/package.json", file_type="code")
        for i in range(20):
            peer = f"pkg_{i}"
            dep_graph.add_node(peer, label=f"package-{i}", source_file="frontend/package.json", file_type="code")
            dep_graph.add_edge("dep_node", peer, relation="contains", confidence="EXTRACTED", source_file="frontend/package.json", weight=1.0)
        dep_graph.add_edge("real_node", "dep_node", relation="imports", confidence="EXTRACTED", source_file="src/auth.py", weight=1.0)
        ids = [item["id"] for item in god_nodes(dep_graph, top_n=10)]
        _record(failures, f"god_nodes excludes {dep_key}", "dep_node" not in ids and "real_node" in ids, repr(ids))
    noise_graph = nx.Graph()
    noise_graph.add_node("real", label="AuthService", source_file="src/auth.py")
    noise_graph.add_node("json_name", label="name", source_file="schema.json")
    for i in range(8):
        node = f"peer{i}"
        noise_graph.add_node(node, label=f"Peer{i}", source_file=f"src/peer{i}.py")
        noise_graph.add_edge("json_name", node)
        noise_graph.add_edge("real", node)
    labels = [item["label"] for item in god_nodes(noise_graph, top_n=10)]
    _record(failures, "god_nodes excludes json noise", "name" not in labels and "AuthService" in labels)
    case_graph = nx.Graph()
    case_graph.add_node("real", label="RealAbstraction", source_file="libs/real.py")
    for i in range(3):
        case_graph.add_node(f"peer{i}", label=f"P{i}", source_file=f"src/p{i}.py")
        case_graph.add_edge("real", f"peer{i}")
    for variant in ("Start", "START", "Name", "ID"):
        node = f"json_{variant.lower()}"
        case_graph.add_node(node, label=variant, source_file="testhelpers/data.json")
        for i in range(15):
            target = f"{node}_t{i}"
            case_graph.add_node(target, label=f"X{i}", source_file="testhelpers/data.json")
            case_graph.add_edge(target, node)
    labels = [item["label"] for item in god_nodes(case_graph, top_n=10)]
    _record(failures, "god_nodes filter case insensitive", all(variant not in labels for variant in ("Start", "START", "Name", "ID")), repr(labels))

    cycle_graph = _make_cycle_graph_directed()
    cycles = find_import_cycles(cycle_graph)
    cycle_sets = [set(c["cycle"]) for c in cycles]
    _record(failures, "cycles structured", isinstance(cycles, list) and cycles and {"cycle", "length", "why"}.issubset(cycles[0]))
    _record(failures, "cycles detect 2 and 3", any({"src/a.ts", "src/b.ts"}.issubset(s) for s in cycle_sets) and any({"src/b.ts", "src/c.ts", "src/d.ts"}.issubset(s) for s in cycle_sets))
    _record(failures, "cycles self loop", any(c["cycle"] == ["src/c.ts"] and c["length"] == 1 for c in cycles))
    _record(failures, "cycles max length", all(c["length"] <= 2 for c in find_import_cycles(cycle_graph, max_cycle_length=2)))
    _record(failures, "cycles skip external", "react" not in " ".join(" ".join(c["cycle"]) for c in cycles))
    undirected = nx.Graph()
    undirected.add_nodes_from(cycle_graph.nodes(data=True))
    undirected.add_edges_from(cycle_graph.edges(data=True))
    _record(failures, "cycles undirected input", bool(find_import_cycles(undirected)))
    no_import = nx.DiGraph()
    a_id, a = _make_file_node("src/a.ts")
    b_id, b = _make_file_node("src/b.ts")
    no_import.add_node(a_id, **a)
    no_import.add_node(b_id, **b)
    no_import.add_edge(a_id, b_id, relation="calls", source_file="src/a.ts", confidence="INFERRED")
    no_import.add_edge(b_id, a_id, relation="contains", source_file="src/b.ts", confidence="EXTRACTED")
    _record(failures, "cycles ignore non-import", find_import_cycles(no_import) == [])
    _record(failures, "cycles empty graph", find_import_cycles(nx.DiGraph()) == [])
    acyclic = nx.DiGraph()
    x_id, x = _make_file_node("x.ts")
    y_id, y = _make_file_node("y.ts")
    acyclic.add_node(x_id, **x)
    acyclic.add_node(y_id, **y)
    acyclic.add_edge(x_id, y_id, relation="imports_from", source_file="x.ts", confidence="EXTRACTED")
    _record(failures, "cycles none", find_import_cycles(acyclic) == [])

    assert not failures, "\n".join(failures)


def test_report_generate() -> None:
    extraction = _load_extraction()
    graph = build_from_json(extraction)
    communities = cluster(graph)
    cohesion = score_all(graph, communities)
    labels = {cid: f"Community {cid}" for cid in communities}
    report = generate(
        graph,
        communities,
        cohesion,
        labels,
        god_nodes(graph),
        surprising_connections(graph),
        {"total_files": 4, "total_words": 62400, "needs_graph": True, "warning": None},
        {"input": extraction["input_tokens"], "output": extraction["output_tokens"]},
        "./project",
    )
    failures: list[str] = []
    for text in ["# Graph Report", "## Corpus Check", "## God Nodes", "## Surprising Connections", "## Communities", "## Ambiguous Edges", "Token cost", "1,200"]:
        _record(failures, f"report contains {text}", text in report)
    raw_report = generate(graph, communities, cohesion, labels, god_nodes(graph), surprising_connections(graph), {"total_files": 4, "total_words": 62400, "needs_graph": True, "warning": None}, {"input": extraction["input_tokens"], "output": extraction["output_tokens"]}, "./project", min_community_size=1)
    _record(failures, "report raw cohesion", "Cohesion:" in raw_report and chr(10003) not in raw_report and chr(9888) not in raw_report)
    assert not failures, "\n".join(failures)


def test_global_graph_merge(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    failures: list[str] = []
    prefixed = prefix_graph_for_global(_make_graph([{"id": "userservice", "label": "UserService", "source_file": "src/user.py"}]), "repoA")
    _record(failures, "prefix preserves label", "repoA::userservice" in prefixed.nodes and prefixed.nodes["repoA::userservice"]["label"] == "UserService")
    _record(failures, "prefix metadata", prefixed.nodes["repoA::userservice"]["repo"] == "repoA" and prefixed.nodes["repoA::userservice"]["local_id"] == "userservice")
    edge_prefixed = prefix_graph_for_global(_make_graph([{"id": "a", "label": "A"}, {"id": "b", "label": "B"}], [{"source": "a", "target": "b"}]), "repo1")
    _record(failures, "prefix rewrites edges", edge_prefixed.has_edge("repo1::a", "repo1::b") and not edge_prefixed.has_edge("a", "b"))
    prune_graph = nx.Graph()
    prune_graph.add_node("repoA::userservice", repo="repoA", label="UserService")
    prune_graph.add_node("repoB::userservice", repo="repoB", label="UserService")
    prune_graph.add_node("repoA::auth", repo="repoA", label="Auth")
    _record(failures, "prune repo removes correct nodes", prune_repo_from_graph(prune_graph, "repoA") == 2 and "repoB::userservice" in prune_graph.nodes and "repoA::auth" not in prune_graph.nodes)
    _record(failures, "prune missing repo zero", prune_repo_from_graph(prune_graph, "missing") == 0)

    def patch_paths(global_dir: Path):
        return patch("graph3d.global_graph._GLOBAL_DIR", global_dir), patch("graph3d.global_graph._GLOBAL_GRAPH", global_dir / "global-graph.json"), patch("graph3d.global_graph._GLOBAL_MANIFEST", global_dir / "global-manifest.json")

    src_graph = tmp_path / "graph.json"
    _graph_to_json(_make_graph([{"id": "userservice", "label": "UserService", "source_file": "src/user.py"}]), src_graph)
    global_dir = tmp_path / ".graph3d"
    p1, p2, p3 = patch_paths(global_dir)
    with p1, p2, p3:
        from graph3d.global_graph import _load_global_graph, global_add, global_list, global_remove

        result = global_add(src_graph, "repoA")
        _record(failures, "global add creates graph", result["skipped"] is False and result["nodes_added"] > 0 and "repoA" in json.loads((global_dir / "global-manifest.json").read_text())["repos"])
        _record(failures, "global add skip unchanged", global_add(src_graph, "repoA")["skipped"] is True)
        removed = global_remove("repoA")
        _record(failures, "global remove", removed > 0 and "repoA" not in global_list())
        with pytest.raises(KeyError):
            global_remove("nonexistent")
        _record(failures, "global remove unknown raises", True)

        g1 = tmp_path / "graph1.json"
        g2 = tmp_path / "graph2.json"
        _graph_to_json(_make_graph([{"id": "userservice", "label": "UserService", "source_file": "src/user.py"}]), g1)
        _graph_to_json(_make_graph([{"id": "userservice", "label": "UserService", "source_file": "src/user.py"}]), g2)
        global_add(g1, "repoA")
        global_add(g2, "repoB")
        loaded = _load_global_graph()
        _record(failures, "global two repos no collision", {"repoA::userservice", "repoB::userservice"}.issubset(loaded.nodes) and loaded.number_of_nodes() == 2)
        global_add(g1, "myrepo")
        global_add(g2, "myrepo")
    captured = capsys.readouterr()
    _record(failures, "global collision warning", "warning" in (captured.out + captured.err).lower())

    from graph3d.dedup import deduplicate_entities

    with pytest.raises(ValueError, match="multiple repos"):
        deduplicate_entities([{"id": "repoA::userservice", "label": "UserService", "repo": "repoA"}, {"id": "repoB::userservice", "label": "UserService", "repo": "repoB"}], [], communities={})
    _record(failures, "dedup cross repo raises", True)
    for label, nodes in [
        ("single repo", [{"id": "repoA::userservice", "label": "UserService", "repo": "repoA"}, {"id": "repoA::auth", "label": "Auth", "repo": "repoA"}]),
        ("no repo attr", [{"id": "userservice", "label": "UserService"}, {"id": "auth", "label": "Auth"}]),
    ]:
        result_nodes, _ = deduplicate_entities(nodes, [], communities={})
        _record(failures, f"dedup {label}", len(result_nodes) == 2)

    repo1 = tmp_path / "repo1" / "graph3d-out"
    repo2 = tmp_path / "repo2" / "graph3d-out"
    repo1.mkdir(parents=True)
    repo2.mkdir(parents=True)
    for repo in (repo1, repo2):
        _graph_to_json(_make_graph([{"id": "userservice", "label": "UserService", "source_file": "src/user.py"}]), repo / "graph.json")
    merged = nx.Graph()
    for graph_path in [repo1 / "graph.json", repo2 / "graph.json"]:
        data = json.loads(graph_path.read_text())
        try:
            loaded = json_graph.node_link_graph(data, edges="links")
        except TypeError:
            loaded = json_graph.node_link_graph(data)
        merged = nx.compose(merged, prefix_graph_for_global(loaded, graph_path.parent.parent.name))
    _record(failures, "merge graphs prefixes ids", {"repo1::userservice", "repo2::userservice"}.issubset(merged.nodes) and merged.number_of_nodes() == 2)
    monkeypatch.setattr("graph3d.security._MAX_GRAPH_FILE_BYTES", 8)
    p1, p2, p3 = patch_paths(tmp_path / "size-graph3d")
    with p1, p2, p3:
        from graph3d.global_graph import global_add

        with pytest.raises(ValueError, match="exceeds"):
            global_add(src_graph, "repoA")
    _record(failures, "global add oversized source rejects", True)
    assert not failures, "\n".join(failures)


def test_hypergraph(tmp_path: Path) -> None:
    failures: list[str] = []
    graph = build_from_json(SAMPLE_EXTRACTION)
    _record(failures, "build stores hyperedges", len(graph.graph.get("hyperedges", [])) == 1 and graph.graph["hyperedges"][0]["id"] == "auth_flow")
    for label, extraction in [
        ("empty hyperedges", {**SAMPLE_EXTRACTION, "hyperedges": []}),
        ("missing hyperedges", {k: v for k, v in SAMPLE_EXTRACTION.items() if k != "hyperedges"}),
    ]:
        _record(failures, f"build {label}", build_from_json(extraction).graph.get("hyperedges", []) == [])
    attach_cases = [
        ("adds new", [{"id": "auth_flow", "label": "Auth Flow", "nodes": ["A", "B", "C"]}], 1),
        ("skips missing id", [{"label": "No ID", "nodes": ["A", "B", "C"]}], 0),
        ("multiple ids", [{"id": "flow_a", "label": "Flow A", "nodes": ["A", "B", "C"]}, {"id": "flow_b", "label": "Flow B", "nodes": ["D", "E", "F"]}], 2),
    ]
    for label, hyperedges, expected in attach_cases:
        attach_graph = nx.Graph()
        attach_hyperedges(attach_graph, hyperedges)
        attach_hyperedges(attach_graph, hyperedges)
        _record(failures, f"attach {label}", len(attach_graph.graph.get("hyperedges", [])) == expected)
    for label, extraction, expected in [
        ("to_json includes hyperedges", SAMPLE_EXTRACTION, 1),
        ("to_json empty hyperedges", {**SAMPLE_EXTRACTION, "hyperedges": []}, 0),
    ]:
        out_path = tmp_path / f"{label.replace(' ', '_')}.json"
        out_graph = build_from_json(extraction)
        to_json(out_graph, {0: list(out_graph.nodes())}, str(out_path))
        data = json.loads(out_path.read_text())
        _record(failures, label, "hyperedges" in data and len(data["hyperedges"]) == expected)
    out_path = tmp_path / "roundtrip.json"
    to_json(graph, {0: list(graph.nodes())}, str(out_path))
    data = json.loads(out_path.read_text())
    round_trip = build_from_json(
        {
            "nodes": [{"id": n["id"], **{k: v for k, v in n.items() if k != "id"}} for n in data["nodes"]],
            "edges": [{"source": e["source"], "target": e["target"], **{k: v for k, v in e.items() if k not in ("source", "target")}} for e in data.get("links", [])],
            "hyperedges": data.get("hyperedges", []),
        }
    )
    _record(failures, "hyperedges roundtrip via json", round_trip.graph.get("hyperedges", [{}])[0].get("id") == "auth_flow")
    report = _hyper_report(graph)
    _record(failures, "report hyperedges section", "## Hyperedges (group relationships)" in report and "Auth Flow" in report and "INFERRED 0.75" in report)
    _record(failures, "report hyperedge node list", "BasicAuth" in report and "DigestAuth" in report)
    for label, extraction in [
        ("report skips empty", {**SAMPLE_EXTRACTION, "hyperedges": []}),
        ("report skips missing", {k: v for k, v in SAMPLE_EXTRACTION.items() if k != "hyperedges"}),
    ]:
        _record(failures, label, "## Hyperedges" not in _hyper_report(build_from_json(extraction)))
    assert not failures, "\n".join(failures)


def test_multigraph_compat() -> None:
    failures: list[str] = []
    result = probe_multigraph_capabilities()
    _record(failures, "probe passes", result.ok, result.error_message())
    _record(failures, "probe versions", bool(result.python_version and result.networkx_version))
    _record(
        failures,
        "probe checks",
        {check.name for check in result.checks}
        == {
            "keyed_parallel_edges",
            "node_link_edges_links_round_trip",
            "duplicate_key_overwrite_semantics",
            "reserved_key_attr_rejected",
            "remove_edges_from_two_tuple_semantics",
            "to_undirected_preserves_multigraph_type",
        },
    )
    _record(failures, "require capabilities", require_multigraph_capabilities().ok)
    message = MultigraphCapabilityResult(
        python_version="3.10.0",
        networkx_version="0.0",
        checks=(CapabilityCheck("node_link_edges_links_round_trip", False, "boom"),),
    ).error_message()
    for text in ["--multigraph requires NetworkX keyed MultiDiGraph node-link", "Default simple graph mode remains available", "node_link_edges_links_round_trip: boom"]:
        _record(failures, f"failure message {text}", text in message)
    graph = nx.MultiDiGraph()
    graph.add_edge("a", "b", key="same", relation="first")
    graph.add_edge("a", "b", key="same", relation="second")
    _record(failures, "duplicate key overwrite trap", graph.number_of_edges("a", "b") == 1 and graph["a"]["b"]["same"]["relation"] == "second")
    assert not failures, "\n".join(failures)


def test_multigraph_diagnostics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    failures: list[str] = []
    summary = diagnose_extraction(_diagnostic_fixture(), directed=True)
    expected = {
        "node_count": 3,
        "raw_edge_count": 7,
        "valid_candidate_edges": 5,
        "missing_endpoint_edges": 1,
        "dangling_endpoint_edges": 1,
        "self_loop_edges": 1,
        "exact_duplicate_edges": 1,
        "directed_unique_endpoint_pairs": 2,
        "directed_same_endpoint_collapsed_edges": 3,
        "same_endpoint_group_count": 1,
        "relation_variant_groups": 1,
        "source_location_variant_groups": 1,
        "post_build_graph_type": "DiGraph",
        "post_build_edge_count": 2,
    }
    for key, value in expected.items():
        _record(failures, f"diagnose {key}", summary[key] == value, repr(summary.get(key)))
    links = _diagnostic_fixture()
    links["links"] = links.pop("edges")
    _record(failures, "diagnose accepts links", diagnose_extraction(links, directed=True)["raw_edge_count"] == 7)
    original = _diagnostic_fixture()
    copied = deepcopy(original)
    diagnose_extraction(original, directed=True)
    _record(failures, "diagnose does not mutate", original == copied)
    malformed = {
        "nodes": [{"id": "a", "label": "A", "file_type": "code", "source_file": "a.py"}, ["not", "node"], {"id": "b", "label": "B", "file_type": "code", "source_file": "b.py"}],
        "edges": [None, ["not", "edge"], {"from": "a", "to": "b", "relation": "legacy_from_to"}, {"source": "a", "target": {"bad": "target"}, "relation": "bad-target"}, {"source": "a", "target": "missing", "relation": "dangling"}, {"source": "", "target": "b", "relation": "missing-source"}],
    }
    malformed_summary = diagnose_extraction(malformed, directed=True)
    for key, value in {"node_count": 2, "raw_edge_count": 6, "non_object_edges": 2, "missing_endpoint_edges": 1, "dangling_endpoint_edges": 2, "valid_candidate_edges": 1}.items():
        _record(failures, f"malformed {key}", malformed_summary[key] == value, repr(malformed_summary.get(key)))
    _record(failures, "malformed post build error", malformed_summary["post_build_error"].startswith("TypeError:"))
    non_list = diagnose_extraction({"nodes": {"id": "a"}, "edges": {"source": "a", "target": "b"}}, directed=True)
    _record(failures, "non-list nodes edges", non_list["node_count"] == 0 and non_list["raw_edge_count"] == 0 and non_list["valid_candidate_edges"] == 0)
    _record(failures, "max examples zero", diagnose_extraction(_diagnostic_fixture(), directed=True, max_examples=0)["examples"] == [])
    extra = _diagnostic_fixture()
    extra["nodes"].append({"id": "d", "label": "D", "file_type": "code", "source_file": "d.py"})
    extra["edges"].extend([{"source": "b", "target": "d", "relation": "imports", "source_file": "b.py"}, {"source": "b", "target": "d", "relation": "calls", "source_file": "b.py"}])
    _record(failures, "max examples limit", len(diagnose_extraction(extra, directed=True, max_examples=1)["examples"]) == 1)

    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(_diagnostic_fixture()), encoding="utf-8")
    file_summary = diagnose_file(graph_path)
    _record(failures, "diagnose_file defaults directed", file_summary["effective_directed"] is True and file_summary["post_build_graph_type"] == "DiGraph")
    report = format_diagnostic_report(diagnose_file(graph_path, directed=True, max_examples=2))
    for text in ["[graph3d] MultiDiGraph edge-collapse diagnostic", "directed_same_endpoint_collapsed_edges: 3", "relation_variant_groups: 1", "producer_suppression_sites:", "examples:", "a -> b"]:
        _record(failures, f"diagnostic report {text}", text in report)
    error_report = format_diagnostic_report(diagnose_extraction({"nodes": [{"id": "a", "label": "A", "file_type": "code", "source_file": "a.py"}, ["not", "node"]], "edges": []}, extract_path=tmp_path / "missing-extract.py"))
    _record(failures, "diagnostic errors in report", "post_build_error: TypeError:" in error_report and "producer_suppression_error: file not found" in error_report)
    payload = format_diagnostic_json(diagnose_file(graph_path, directed=True))
    _record(failures, "diagnostic json serializable", payload["schema_version"] == 1 and payload["summary"]["raw_edge_count"] == 7 and "producer_suppression" in payload)
    json.dumps(payload)
    source = tmp_path / "extract.py"
    source.write_text("seen_call_pairs: set[tuple[str, str]] = set()\nseen_static_ref_pairs: set[tuple[str, str, str]] = set()\nother = set()\n", encoding="utf-8")
    scan = scan_producer_suppression_sites(source)
    _record(failures, "scan seen sets", scan["total_sites"] == 2 and scan["sites"][0]["name"] == "seen_call_pairs" and scan["sites"][1]["tuple_arity"] == 3)
    source.write_text("seen_blank: set[tuple[ ]] = set()\n", encoding="utf-8")
    scan = scan_producer_suppression_sites(source)
    _record(failures, "scan unknown arity", scan["total_sites"] == 1 and scan["sites"][0]["tuple_arity"] == 0)
    _record(failures, "scan missing file", scan_producer_suppression_sites(tmp_path / "missing-extract.py")["error"] == "file not found")
    monkeypatch.setattr("graph3d.security._MAX_GRAPH_FILE_BYTES", 16)
    with pytest.raises(ValueError, match="exceeds"):
        diagnose_file(graph_path)
    _record(failures, "diagnose oversized rejects", True)
    monkeypatch.setattr("graph3d.security._MAX_GRAPH_FILE_BYTES", 100_000_000)
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        diagnose_file(bad_json)
    _record(failures, "diagnose non-object rejects", True)
    payload_dict = _diagnostic_fixture()
    payload_dict["directed"] = False
    graph_path.write_text(json.dumps(payload_dict), encoding="utf-8")
    _record(failures, "diagnose json directed flag", diagnose_file(graph_path)["effective_directed"] is False)
    _record(failures, "diagnose directed override", diagnose_file(graph_path, directed=True)["effective_directed"] is True)

    cli_cases = [
        ("human", ["multigraph", "--graph", str(graph_path)], lambda out: "[graph3d] MultiDiGraph edge-collapse diagnostic" in out and "raw_edges: 7" in out and "effective_directed: False" in out),
        ("undirected", ["multigraph", "--graph", str(graph_path), "--undirected"], lambda out: "effective_directed: False" in out and "post_build_graph_type: Graph" in out),
        ("max zero", ["multigraph", "--graph", str(graph_path), "--max-examples", "0"], lambda out: "\nexamples:" not in out),
    ]
    for label, argv_tail, check in cli_cases:
        monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
        monkeypatch.setattr(mainmod.sys, "argv", ["graph3d", "diagnose", *argv_tail])
        mainmod.main()
        _record(failures, f"cli {label}", check(capsys.readouterr().out))
    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr(mainmod.sys, "argv", ["graph3d", "diagnose", "multigraph", "--graph", str(graph_path), "--json"])
    mainmod.main()
    cli_json = json.loads(capsys.readouterr().out)
    _record(failures, "cli json", cli_json["schema_version"] == 1 and cli_json["summary"]["directed_same_endpoint_collapsed_edges"] == 3)
    usage_cases = [
        ([], "Usage: graph3d diagnose multigraph"),
        (["wrong"], "Usage: graph3d diagnose multigraph"),
        (["multigraph", "--graph"], "error: --graph requires a path"),
        (["multigraph", "--max-examples"], "error: --max-examples requires an integer"),
        (["multigraph", "--max-examples", "many"], "error: --max-examples requires an integer"),
        (["multigraph", "--max-examples", "-1"], "error: --max-examples must be >= 0"),
        (["multigraph", "--unknown"], "error: unknown diagnose option --unknown"),
    ]
    for argv_tail, expected_error in usage_cases:
        monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
        monkeypatch.setattr(mainmod.sys, "argv", ["graph3d", "diagnose", *argv_tail])
        with pytest.raises(SystemExit) as exc_info:
            mainmod.main()
        err = capsys.readouterr().err
        _record(failures, f"cli usage {argv_tail}", exc_info.value.code == 1 and expected_error in err, err)
    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr(mainmod.sys, "argv", ["graph3d", "diagnose", "multigraph", "--graph", str(graph_path), "--directed", "--undirected"])
    with pytest.raises(SystemExit) as exc_info:
        mainmod.main()
    _record(failures, "cli conflicting direction flags", exc_info.value.code == 1 and "--directed and --undirected are mutually exclusive" in capsys.readouterr().err)
    assert not failures, "\n".join(failures)
