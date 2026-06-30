from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import networkx as nx
import pytest
from networkx.readwrite import json_graph

from graph3d.analyze import god_nodes, surprising_connections
from graph3d.bitdot_cube import _bitdot_edges, _bitdot_nodes, _node_shape, _pattern_summary, to_bitdot_cube_html
from graph3d.build import build_from_json
from graph3d.callflow_html import derive_sections_from_communities, write_callflow_html
from graph3d.cluster import cluster, score_all
from graph3d.export import backup_if_protected, to_canvas, to_cypher, to_graphml, to_html, to_json
from graph3d.validate import GRAPH3D_EXPORT_SCHEMA_KIND, GRAPH3D_EXPORT_SCHEMA_VERSION, validate_graph_export

PYTHON = sys.executable
REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


def _make_graph() -> nx.Graph:
    data = json.loads((FIXTURES / "extraction.json").read_text(encoding="utf-8"))
    return build_from_json(data)


def _run(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    run_env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + run_env.get("PYTHONPATH", "")
    if env:
        run_env.update(env)
    return subprocess.run([PYTHON, "-m", "graph3d", *args], cwd=cwd, capture_output=True, text=True, env=run_env, check=False)


def _make_cli_graph(tmp_path: Path) -> Path:
    out = tmp_path / "graph3d-out"
    out.mkdir()
    graph = _make_graph()
    communities = cluster(graph)
    to_json(graph, communities, str(out / "graph.json"))
    analysis = {
        "communities": {str(k): v for k, v in communities.items()},
        "cohesion": {str(k): v for k, v in score_all(graph, communities).items()},
        "gods": god_nodes(graph),
        "surprises": surprising_connections(graph, communities),
    }
    (out / ".graph3d_analysis.json").write_text(json.dumps(analysis), encoding="utf-8")
    (out / ".graph3d_labels.json").write_text(json.dumps({str(k): f"Community {k}" for k in communities}), encoding="utf-8")
    return out


def _custom_bitdot_graph() -> tuple[nx.DiGraph, dict[int, list[str]], dict[int, str]]:
    graph = nx.DiGraph()
    nodes = [
        ("caller", "Caller", "code", "src/caller.py", 0),
        ("callee", "Callee", "code", "src/callee.py", 0),
        ("iface", "Interface", "schema", "schema.yml", 1),
        ("impl", "Implementation", "code", "src/impl.py", 1),
        ("owner", "Owner", "document", "README.md", 2),
    ]
    for node_id, label, file_type, source_file, community in nodes:
        graph.add_node(node_id, label=label, file_type=file_type, source_file=source_file, community=community)
    for source, target, relation in [("caller", "callee", "calls"), ("impl", "iface", "implements"), ("owner", "impl", "contains")]:
        graph.add_edge(source, target, relation=relation, confidence="EXTRACTED")
    return graph, {0: ["caller", "callee"], 1: ["iface", "impl"], 2: ["owner"]}, {0: "Runtime", 1: "Schema", 2: "Docs"}


def _make_callflow_out(tmp_path: Path) -> Path:
    out = tmp_path / "graph3d-out"
    out.mkdir()
    graph = {
        "directed": False,
        "multigraph": False,
        "graph": {},
        "nodes": [
            {"id": "api", "label": "ApiClient", "source_file": "src/api.py", "file_type": "code", "community": 0},
            {"id": "run", "label": "run()", "source_file": "src/main.py", "file_type": "code", "community": 0},
            {"id": "export", "label": "write_html()", "source_file": "src/export.py", "file_type": "code", "community": 1},
            {"id": "evil", "label": "<script>alert(1)</script>", "source_file": "src/evil.py", "file_type": "code", "community": 1},
        ],
        "links": [
            {"source": "run", "target": "api", "relation": "calls", "confidence": "EXTRACTED", "confidence_score": 1.0},
            {"source": "api", "target": "export", "relation": "uses", "confidence": "EXTRACTED", "confidence_score": 1.0},
            {"source": "export", "target": "evil", "relation": "calls", "confidence": "EXTRACTED", "confidence_score": 1.0},
        ],
        "hyperedges": [],
        "built_at_commit": "abcdef123456",
    }
    (out / "graph.json").write_text(json.dumps(graph), encoding="utf-8")
    (out / ".graph3d_labels.json").write_text(json.dumps({"0": "Runtime", "1": "Export"}), encoding="utf-8")
    report = ["# Graph Report - sample", "", "## Summary", "- 3 nodes - 2 edges - 1 communities detected", "", "## God Nodes (most connected - your core abstractions)", "1. `Transformer` - 2 edges"]
    (out / "GRAPH_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    return out


def test_to_html_and_core_exports(tmp_path: Path) -> None:
    graph = _make_graph()
    communities = cluster(graph)
    failures: list[str] = []
    graph_json = tmp_path / "graph.json"
    to_json(graph, communities, str(graph_json), built_at_commit="abc123")
    data = json.loads(graph_json.read_text(encoding="utf-8"))
    try:
        roundtrip = json_graph.node_link_graph(data, edges="links")
    except TypeError:
        roundtrip = json_graph.node_link_graph(data)
    metadata = data["graph3d_metadata"]
    checks = [
        ("json exists", graph_json.exists()),
        ("nodes", "nodes" in data and bool(data["nodes"])),
        ("links", "links" in data and bool(data["links"])),
        ("node community", all("community" in node for node in data["nodes"])),
        ("commit", data.get("built_at_commit") == "abc123"),
        ("schema", data.get("graph3d_schema") == {"kind": GRAPH3D_EXPORT_SCHEMA_KIND, "version": GRAPH3D_EXPORT_SCHEMA_VERSION}),
        ("validate", validate_graph_export(data) == []),
        ("roundtrip nodes", roundtrip.number_of_nodes() == graph.number_of_nodes()),
        ("roundtrip edges", roundtrip.number_of_edges() == graph.number_of_edges()),
        ("metadata kind", metadata["schema_kind"] == GRAPH3D_EXPORT_SCHEMA_KIND),
        ("metadata version", metadata["schema_version"] == GRAPH3D_EXPORT_SCHEMA_VERSION),
        ("metadata commit", metadata["built_at_commit"] == "abc123"),
        ("source files", metadata["source_documents"]["source_files"] == ["model.py", "paper.md"]),
        ("source count", metadata["source_documents"]["source_file_count"] == 2),
        ("file counts", metadata["source_documents"]["file_type_counts"] == {"code": 3, "document": 1}),
        ("validation nodes", metadata["validation"]["node_count"] == len(data["nodes"])),
        ("validation links", metadata["validation"]["link_count"] == len(data["links"])),
    ]
    failures.extend(f"core export failed: {name}" for name, ok in checks if not ok)
    labels = {cid: f"Group {cid}" for cid in communities}
    cases = [
        ("cypher", tmp_path / "cypher.txt", lambda p: to_cypher(graph, str(p)), ["MERGE"], []),
        ("graphml", tmp_path / "graph.graphml", lambda p: to_graphml(graph, communities, str(p)), ["<graphml", "<node", "community"], []),
        ("html", tmp_path / "graph.html", lambda p: to_html(graph, communities, str(p), community_labels=labels, member_counts={cid: len(m) for cid, m in communities.items()}), ["vis-network", "vis-network@9.1.6/standalone/umd/vis-network.min.js", "integrity=\"sha384-Ux6phic9PEHJ38YtrijhkzyJ8yQlH8i/+buBR8s3mAZOJrP1gwyvAcIYl3GWtpX1\"", "crossorigin=\"anonymous\"", "search", "Group 0", "RAW_NODES", "RAW_EDGES"], ["https://unpkg.com/vis-network/standalone"]),
        ("canvas", tmp_path / "graph.canvas", lambda p: to_canvas(graph, communities, str(p)), [], []),
    ]
    for name, path, writer, required, rejected in cases:
        try:
            writer(path)
            content = path.read_text(encoding="utf-8")
            if not path.exists() or path.stat().st_size <= 0:
                failures.append(f"{name} did not create a non-empty file")
            for needle in required:
                haystack = content.lower() if needle == "search" else content
                if needle not in haystack:
                    failures.append(f"{name} missing {needle!r}")
            for needle in rejected:
                if needle in content:
                    failures.append(f"{name} unexpectedly contained {needle!r}")
        except Exception as exc:
            failures.append(f"{name} raised {type(exc).__name__}: {exc}")
    canvas_data = json.loads((tmp_path / "graph.canvas").read_text(encoding="utf-8"))
    file_nodes = [node for node in canvas_data["nodes"] if node.get("type") == "file"]
    if not file_nodes:
        failures.append("canvas should contain file nodes")
    for node in file_nodes:
        file_name = node.get("file", "")
        if "\\" in file_name or "/" in file_name or not file_name.endswith(".md"):
            failures.append(f"canvas file path should be vault-relative markdown: {file_name}")
    assert not failures, "\n".join(failures)


def test_bitdot_cube_render(tmp_path: Path) -> None:
    graph, communities, labels = _custom_bitdot_graph()
    out = tmp_path / "bitdot-cube.html"
    to_bitdot_cube_html(graph, communities, str(out), community_labels=labels)
    content = out.read_text(encoding="utf-8")
    failures: list[str] = []
    required = [
        "Bitdot Cube Plotter", "Connection patterns", "Shapes (node kind)", "slice-mode", "copy-json", "export-png", "RAW_NODES", "RAW_EDGES", "graph3d.bitdot-cube",
        "Caller", "Implementation", "contains", "calls", "implements", "#58a6ff", "#f0883e", "#f778ba", '"shape":"triangle"', '"occurrence":', '"inDegree":', '"outDegree":',
        "sh-triangle", "showLabels: false", "p.relation + (p.group ? ' (' + p.group + ')' : '')",
    ]
    for needle in required:
        if needle not in content:
            failures.append(f"bitdot html missing {needle!r}")
    for needle in ["rgba(184,197,216", 'id="show-labels" type="checkbox" checked']:
        if needle in content:
            failures.append(f"bitdot html unexpectedly contained {needle!r}")
    pattern_by_relation = {p["relation"]: p for p in _pattern_summary(_bitdot_edges(graph))}
    for relation, group, color in [("calls", "dataflow", "#f0883e"), ("implements", "hierarchy", "#f778ba"), ("contains", "containment", "#58a6ff")]:
        pattern = pattern_by_relation.get(relation)
        if not pattern:
            failures.append(f"missing pattern summary for {relation}")
            continue
        if pattern.get("group") != group:
            failures.append(f"{relation} group was {pattern.get('group')!r}, expected {group!r}")
        if pattern.get("color") != color:
            failures.append(f"{relation} color was {pattern.get('color')!r}, expected {color!r}")
    for file_type, expected in [("code", "square"), ("document", "circle"), ("rationale", "diamond"), ("schema", "triangle"), ("concept", "hexagon"), ("unknown-kind", "square")]:
        actual = _node_shape(file_type)
        if actual != expected:
            failures.append(f"shape {file_type} was {actual}, expected {expected}")
    fixture_graph = _make_graph()
    fixture_communities = cluster(fixture_graph)
    fixture_nodes = _bitdot_nodes(fixture_graph, fixture_communities, None)
    by_label: dict[str, list[dict[str, Any]]] = {}
    for node in fixture_nodes:
        by_label.setdefault(node["label"], []).append(node)
        if node["degree"] < 0 or node["inDegree"] < 0 or node["outDegree"] < 0:
            failures.append(f"negative degree fields on {node['id']}")
        if node["occurrence"] < 1 or "shape" not in node:
            failures.append(f"missing analytic shape/occurrence fields on {node['id']}")
    for label, group in by_label.items():
        if any(node["occurrence"] != len(group) for node in group):
            failures.append(f"occurrence mismatch for label {label}")
    for i, node_id in enumerate(fixture_graph.nodes()):
        fixture_graph.nodes[node_id]["community"] = 100 + i
    stale_nodes = _bitdot_nodes(fixture_graph, {}, None)
    cids = {node["community"] for node in stale_nodes}
    if cids != {100 + i for i in range(fixture_graph.number_of_nodes())}:
        failures.append(f"stale sidecar fallback communities wrong: {sorted(cids)}")
    if len({node["color"] for node in stale_nodes}) <= 1:
        failures.append("stale sidecar fallback collapsed colors")
    assert not failures, "\n".join(failures)


def test_bitdot_cube_slicing_focus_path(tmp_path: Path) -> None:
    graph = _make_graph()
    communities = cluster(graph)
    out = tmp_path / "bitdot-cube.html"
    to_bitdot_cube_html(graph, communities, str(out), community_labels={cid: f"Group {cid}" for cid in communities})
    content = out.read_text(encoding="utf-8")
    failures = []
    cases = [
        ("vertical-x mode", "vertical-x"), ("vertical-y mode", "vertical-y"), ("horizontal-z mode", "horizontal-z"), ("crosswise mode", "crosswise"),
        ("slice plane", "drawSlicePlane"), ("focus button", "Focus neighborhood"), ("focus state", "focusSet"), ("cluster isolation", "clusterOnly"),
        ("cluster legend active", "legend-item.active"), ("source action", "Set as Source"), ("destination action", "Set as Destination"),
        ("path compute", "computePath"), ("path highlight nodes", "pathNodes"), ("path highlight edges", "pathEdges"), ("selected node panel", "Selected node"),
        ("terminology node", "node"), ("terminology cluster", "Cluster"), ("terminology connections", "Connections"), ("terminology occurrence", "Occurrence"),
        ("terminology source", "Source"), ("terminology destination", "Destination"), ("terminology pattern", "pattern"),
    ]
    for name, needle in cases:
        if needle not in content:
            failures.append(f"{name} missing {needle!r}")
    assert not failures, "\n".join(failures)


def test_export_backup_limits_and_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    failures: list[str] = []
    backup_cases = [
        ("no graph", {}, "none", []),
        ("no markers", {"graph.json": '{"nodes":[],"links":[]}'}, "none", []),
        ("semantic marker", {"graph.json": '{"nodes":[],"links":[]}', "GRAPH_REPORT.md": "# Report", ".graph3d_semantic_marker": '{"output_tokens": 1234}'}, "dir", ["graph.json", "GRAPH_REPORT.md", ".graph3d_semantic_marker"]),
        ("curated labels", {"graph.json": '{"nodes":[],"links":[]}', ".graph3d_labels.json": json.dumps({"0": "Auth Pipeline", "1": "Community 1"})}, "dir", []),
        ("default labels only", {"graph.json": '{"nodes":[],"links":[]}', ".graph3d_labels.json": json.dumps({"0": "Community 0", "1": "Community 1"})}, "none", []),
    ]
    for name, files, expected, must_copy in backup_cases:
        case_dir = tmp_path / f"backup-{name.replace(' ', '-')}"
        case_dir.mkdir()
        for rel_path, text in files.items():
            (case_dir / rel_path).write_text(text, encoding="utf-8")
        result = backup_if_protected(case_dir)
        if expected == "none" and result is not None:
            failures.append(f"{name} expected no backup, got {result}")
        if expected == "dir" and (result is None or not result.is_dir()):
            failures.append(f"{name} expected backup dir, got {result}")
        for rel_path in must_copy:
            if result is None or not (result / rel_path).exists():
                failures.append(f"{name} did not copy {rel_path}")
    same_day = tmp_path / "same-day"
    same_day.mkdir()
    (same_day / "graph.json").write_text('{"nodes":[],"links":[]}', encoding="utf-8")
    (same_day / ".graph3d_semantic_marker").write_text("{}", encoding="utf-8")
    first = backup_if_protected(same_day)
    second = backup_if_protected(same_day)
    if first is None or second is None or first != second or first.name != date.today().isoformat():
        failures.append(f"same-day backup did not reuse one dated dir: {first}, {second}")
    (same_day / "graph.json").write_text('{"nodes":[{"id":"x"}],"links":[]}', encoding="utf-8")
    third = backup_if_protected(same_day)
    if third != first or (third / "graph.json").read_text(encoding="utf-8") != '{"nodes":[{"id":"x"}],"links":[]}':
        failures.append("same-day changed graph was not overwritten in place")
    monkeypatch.setenv("GRAPH3D_NO_BACKUP", "1")
    disabled = tmp_path / "disabled"
    disabled.mkdir()
    (disabled / "graph.json").write_text('{"nodes":[],"links":[]}', encoding="utf-8")
    (disabled / ".graph3d_semantic_marker").write_text("{}", encoding="utf-8")
    if backup_if_protected(disabled) is not None:
        failures.append("GRAPH3D_NO_BACKUP did not disable backup")
    monkeypatch.delenv("GRAPH3D_NO_BACKUP", raising=False)
    graph, communities, labels = _custom_bitdot_graph()
    for name, limit, message in [("limit disabled", 0, "disabled by node limit"), ("too many nodes", 2, "too large for bitdot cube")]:
        with pytest.raises(ValueError) as excinfo:
            to_bitdot_cube_html(graph, communities, str(tmp_path / f"{name.replace(' ', '-')}.html"), community_labels=labels, node_limit=limit)
        if message not in str(excinfo.value):
            failures.append(f"{name} error did not contain {message!r}: {excinfo.value}")
    assert not failures, "\n".join(failures)


def test_cli_export_and_commands(tmp_path: Path) -> None:
    failures: list[str] = []
    graph_cmd_cases = [
        {"name": "export html", "setup": _make_cli_graph, "args": ["export", "html"], "expect": 0, "paths": [Path("graph3d-out") / "graph.html"], "contains": [(Path("graph3d-out") / "graph.html", "vis-network")]},
        {"name": "export html no-viz", "setup": _make_cli_graph, "pre": lambda out: (out / "graph.html").write_text("<html/>", encoding="utf-8"), "args": ["export", "html", "--no-viz"], "expect": 0, "absent": [Path("graph3d-out") / "graph.html"]},
        {"name": "export html missing graph", "args": ["export", "html"], "expect": "fail"},
        {"name": "export bitdot cube", "setup": _make_cli_graph, "args": ["export", "bitdot-cube"], "expect": 0, "paths": [Path("graph3d-out") / "bitdot-cube.html"], "contains": [(Path("graph3d-out") / "bitdot-cube.html", "slice-mode")]},
        {"name": "export bitdot cube missing graph", "args": ["export", "bitdot-cube"], "expect": "fail"},
        {"name": "export obsidian", "setup": _make_cli_graph, "args": ["export", "obsidian"], "expect": 0, "paths": [Path("graph3d-out") / "obsidian"], "glob": (Path("graph3d-out") / "obsidian", "*.md")},
        {"name": "export obsidian custom dir", "setup": _make_cli_graph, "args_factory": lambda case_dir: ["export", "obsidian", "--dir", str(case_dir / "my-vault")], "expect": 0, "paths_factory": lambda case_dir: [case_dir / "my-vault"], "glob_factory": lambda case_dir: (case_dir / "my-vault", "*.md")},
        {"name": "export wiki", "setup": _make_cli_graph, "args": ["export", "wiki"], "expect": 0, "paths": [Path("graph3d-out") / "wiki" / "index.md"]},
        {"name": "export wiki edges only", "setup": _make_cli_graph, "pre": lambda out: _rewrite_links_as_edges(out / "graph.json"), "args": ["export", "wiki"], "expect": 0, "paths": [Path("graph3d-out") / "wiki" / "index.md"]},
        {"name": "export graphml", "setup": _make_cli_graph, "args": ["export", "graphml"], "expect": 0, "paths": [Path("graph3d-out") / "graph.graphml"], "contains": [(Path("graph3d-out") / "graph.graphml", "<graphml")]},
        {"name": "export neo4j", "setup": _make_cli_graph, "args": ["export", "neo4j"], "expect": 0, "paths": [Path("graph3d-out") / "cypher.txt"], "contains_any": [(Path("graph3d-out") / "cypher.txt", ["MERGE", "CREATE"])]},
        {"name": "export unknown format", "args": ["export", "pdf"], "expect": "fail"},
        {"name": "query", "setup": _make_cli_graph, "args": ["query", "test"], "expect": 0, "stdout": True},
        {"name": "query dfs", "setup": _make_cli_graph, "args": ["query", "test", "--dfs"], "expect": 0},
        {"name": "query budget", "setup": _make_cli_graph, "args": ["query", "test", "--budget", "500"], "expect": 0},
        {"name": "query missing graph", "args": ["query", "anything"], "expect": "fail"},
        {"name": "query GRAPH3D_OUT", "setup": _make_cli_graph, "move_out": "custom-graph", "args": ["query", "test"], "env": {"GRAPH3D_OUT": "custom-graph"}, "expect": 0, "stdout": True},
        {"name": "path", "setup": _make_cli_graph, "args": ["path", "Transformer", "LayerNorm"], "expect": 0},
        {"name": "path missing graph", "args": ["path", "a", "b"], "expect": "fail"},
        {"name": "path GRAPH3D_OUT", "setup": _make_cli_graph, "move_out": "custom-graph", "args": ["path", "Transformer", "LayerNorm"], "env": {"GRAPH3D_OUT": "custom-graph"}, "expect": 0},
        {"name": "explain", "setup": _make_cli_graph, "args": ["explain", "test"], "expect": 0},
        {"name": "explain missing graph", "args": ["explain", "anything"], "expect": "fail"},
        {"name": "explain GRAPH3D_OUT", "setup": _make_cli_graph, "move_out": "custom-graph", "args": ["explain", "test"], "env": {"GRAPH3D_OUT": "custom-graph"}, "expect": 0},
    ]
    for case in graph_cmd_cases:
        case_dir = tmp_path / case["name"].replace(" ", "-")
        case_dir.mkdir()
        out = case.get("setup", lambda path: None)(case_dir)
        if case.get("move_out") and out is not None:
            custom = case_dir / case["move_out"]
            out.rename(custom)
            out = custom
        if case.get("pre") and out is not None:
            case["pre"](out)
        args = case.get("args_factory", lambda path: case["args"])(case_dir)
        result = _run(args, case_dir, env=case.get("env"))
        _check_cli_case(case, case_dir, result, failures)

    update_dir = tmp_path / "update-no-cluster"
    update_dir.mkdir()
    (update_dir / "sample.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    result = _run(["update", ".", "--no-cluster"], update_dir)
    raw_graph = update_dir / "graph3d-out" / "graph.json"
    if result.returncode != 0:
        failures.append(f"update --no-cluster failed: {result.stderr}")
    elif not raw_graph.exists():
        failures.append("update --no-cluster did not write graph.json")
    else:
        data = json.loads(raw_graph.read_text(encoding="utf-8"))
        if "nodes" not in data or "links" not in data:
            failures.append("update --no-cluster graph missing nodes or links")
        if any("community" in node for node in data.get("nodes", [])):
            failures.append("update --no-cluster raw graph should not stamp communities")

    cluster_dir = tmp_path / "cluster-only-missing-out"
    cluster_dir.mkdir()
    out = _make_cli_graph(cluster_dir)
    graph_src = cluster_dir / "backup" / "graph.json"
    graph_src.parent.mkdir()
    shutil.copy(out / "graph.json", graph_src)
    shutil.rmtree(out)
    result = _run(["cluster-only", ".", "--graph", str(graph_src), "--no-viz"], cluster_dir)
    if result.returncode != 0 or not (cluster_dir / "graph3d-out" / "GRAPH_REPORT.md").exists():
        failures.append(f"cluster-only missing output dir failed: {result.stderr}")

    remap_dir = tmp_path / "cluster-only-remap"
    remap_dir.mkdir()
    out = _make_cli_graph(remap_dir)
    graph_json = out / "graph.json"
    labels_json = out / ".graph3d_labels.json"
    data = json.loads(graph_json.read_text(encoding="utf-8"))
    nodes = data.get("nodes", [])
    if len(nodes) < 4:
        failures.append("fixture must have enough nodes to form 2+ communities")
    sentinel_a, sentinel_b = 4242, 9999
    for idx, node in enumerate(nodes):
        node["community"] = sentinel_a if idx < len(nodes) // 2 else sentinel_b
    graph_json.write_text(json.dumps(data), encoding="utf-8")
    labels_json.write_text(json.dumps({str(sentinel_a): "First Group", str(sentinel_b): "Second Group"}), encoding="utf-8")
    result = _run(["cluster-only", ".", "--no-viz"], remap_dir)
    if result.returncode != 0:
        failures.append(f"cluster-only remap failed: {result.stderr}")
    else:
        final_graph = json.loads(graph_json.read_text(encoding="utf-8"))
        final_labels = json.loads(labels_json.read_text(encoding="utf-8"))
        actual_cids = {node.get("community") for node in final_graph.get("nodes", [])}
        label_cids = {int(key) for key in final_labels.keys()}
        if not (actual_cids & label_cids):
            failures.append(f"cluster-only remap orphaned labels: labels={final_labels}, cids={actual_cids}")

    fallback_cases = [
        ("fallback sidecar absent", lambda out: (out / ".graph3d_analysis.json").unlink(), True),
        ("fallback count", lambda out: (out / ".graph3d_analysis.json").unlink(), True),
        ("fallback no community", _strip_community_and_remove_analysis, False),
    ]
    for name, mutate, require_html in fallback_cases:
        case_dir = tmp_path / name.replace(" ", "-")
        case_dir.mkdir()
        out = _make_cli_graph(case_dir)
        if name == "fallback count":
            analysis = json.loads((out / ".graph3d_analysis.json").read_text(encoding="utf-8"))
            graph_data = json.loads((out / "graph.json").read_text(encoding="utf-8"))
            expected_count = len(analysis["communities"])
            reconstructed = {node["community"] for node in graph_data.get("nodes", []) if node.get("community") is not None}
            if len(reconstructed) != expected_count:
                failures.append(f"fallback reconstruction count changed: {len(reconstructed)} vs {expected_count}")
        mutate(out)
        result = _run(["export", "html"], case_dir)
        if result.returncode != 0:
            failures.append(f"{name} failed: {result.stderr}")
        if require_html and not (out / "graph.html").exists():
            failures.append(f"{name} did not create graph.html")
        if "Single community" in result.stdout or "Single community" in result.stderr:
            failures.append(f"{name} hit single-community bailout")
    assert not failures, "\n".join(failures)


def test_callflow_html(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    failures: list[str] = []
    direct_dir = tmp_path / "direct"
    direct_dir.mkdir()
    out = _make_callflow_out(direct_dir)
    html_path = write_callflow_html(direct_dir, output=str(Path("graph3d-out") / "callflow.html"), max_sections=4)
    if html_path != out / "callflow.html":
        failures.append(f"callflow path was {html_path}")
    content = html_path.read_text(encoding="utf-8")
    for needle in ["mermaid", "Graph Report Highlights", "Transformer", "ApiClient", "&lt;script&gt;alert(1)&lt;/script&gt;"]:
        if needle not in content:
            failures.append(f"callflow direct missing {needle!r}")
    if "<script>alert(1)</script>" in content:
        failures.append("callflow direct did not escape script label")

    cli_dir = tmp_path / "cli"
    cli_dir.mkdir()
    _make_callflow_out(cli_dir)
    result = _run(["export", "callflow-html", "--output", str(Path("graph3d-out") / "from-cli.html"), "--max-sections", "4"], cli_dir)
    if result.returncode != 0:
        failures.append(f"callflow cli failed: {result.stderr}")
    if not (cli_dir / "graph3d-out" / "from-cli.html").exists():
        failures.append("callflow cli did not create output")
    if "callflow HTML written" not in result.stdout:
        failures.append("callflow cli missing success text")

    positional_dir = tmp_path / "positional"
    positional_dir.mkdir()
    _make_callflow_out(positional_dir)
    external_out = positional_dir / "GitNexus" / "graph3d-out"
    external_out.mkdir(parents=True)
    external_graph = {
        "directed": False,
        "multigraph": False,
        "graph": {},
        "nodes": [
            {"id": "external", "label": "ExternalOnly", "source_file": "src/external.py", "file_type": "code", "community": 0},
            {"id": "writer", "label": "write_external()", "source_file": "src/writer.py", "file_type": "code", "community": 1},
        ],
        "links": [{"source": "external", "target": "writer", "relation": "calls", "confidence": "EXTRACTED", "confidence_score": 1.0}],
        "hyperedges": [],
    }
    (external_out / "graph.json").write_text(json.dumps(external_graph), encoding="utf-8")
    (external_out / ".graph3d_labels.json").write_text(json.dumps({"0": "External Runtime", "1": "External Export"}), encoding="utf-8")
    report = ["# Graph Report - external", "", "## Summary", "- 2 nodes - 1 edges - 2 communities detected", "", "## God Nodes (most connected - your core abstractions)", "1. `ExternalGod` - 1 edges"]
    (external_out / "GRAPH_REPORT.md").write_text("\n".join(report), encoding="utf-8")
    result = _run(["export", "callflow-html", str(external_out / "graph.json"), "--output", "positional.html", "--max-sections", "4"], positional_dir)
    html = (positional_dir / "positional.html").read_text(encoding="utf-8") if (positional_dir / "positional.html").exists() else ""
    for name, ok in [("return code", result.returncode == 0), ("external node", "ExternalOnly" in html), ("external report", "ExternalGod" in html), ("default node absent", "ApiClient" not in html), ("default report absent", "Transformer" not in html)]:
        if not ok:
            failures.append(f"callflow positional failed {name}: {result.stderr}")

    section_nodes = [
        {"id": "extract_py", "label": "extract_python", "source_file": "graph3d/extract.py", "community": 0},
        {"id": "extract_js", "label": "extract_js", "source_file": "graph3d/extract.py", "community": 0},
        {"id": "to_html", "label": "to_html", "source_file": "graph3d/export.py", "community": 1},
        {"id": "test_html", "label": "test_export_html", "source_file": "tests/test_export.py", "community": 2},
    ]
    ids = {section["id"] for section in derive_sections_from_communities(section_nodes, {}, "en", 6)}
    for expected in ["extract-pipeline", "outputs-docs", "tests-fixtures"]:
        if expected not in ids:
            failures.append(f"derive sections missing {expected}")

    from graph3d.callflow_html import load_graph

    graph_path = tmp_path / "oversized-graph.json"
    graph_path.write_text(json.dumps({"nodes": [], "links": []}), encoding="utf-8")
    monkeypatch.setattr("graph3d.security._MAX_GRAPH_FILE_BYTES", 8)
    with pytest.raises(SystemExit) as excinfo:
        load_graph(graph_path)
    if "exceeds" not in str(excinfo.value):
        failures.append(f"oversized graph error was {excinfo.value}")
    assert not failures, "\n".join(failures)


def _rewrite_links_as_edges(graph_path: Path) -> None:
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    data["edges"] = data.pop("links")
    graph_path.write_text(json.dumps(data), encoding="utf-8")


def _strip_community_and_remove_analysis(out: Path) -> None:
    (out / ".graph3d_analysis.json").unlink()
    graph_path = out / "graph.json"
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    for node in data.get("nodes", []):
        node.pop("community", None)
    graph_path.write_text(json.dumps(data), encoding="utf-8")


def _check_cli_case(case: dict[str, Any], case_dir: Path, result: subprocess.CompletedProcess[str], failures: list[str]) -> None:
    expected = case["expect"]
    if expected == "fail":
        if result.returncode == 0:
            failures.append(f"{case['name']} expected failure but succeeded: {result.stdout}")
        return
    if result.returncode != expected:
        failures.append(f"{case['name']} return code {result.returncode}: {result.stderr}")
        return
    if case.get("stdout") and not result.stdout:
        failures.append(f"{case['name']} expected stdout")
    paths = case.get("paths_factory", lambda _case_dir: case.get("paths", []))(case_dir)
    for path in paths:
        full_path = path if path.is_absolute() else case_dir / path
        if not full_path.exists():
            failures.append(f"{case['name']} missing path {full_path}")
        elif full_path.is_file() and full_path.stat().st_size <= 0:
            failures.append(f"{case['name']} wrote empty file {full_path}")
    for path in case.get("absent", []):
        full_path = path if path.is_absolute() else case_dir / path
        if full_path.exists():
            failures.append(f"{case['name']} expected absent path {full_path}")
    glob_spec = case.get("glob_factory", lambda _case_dir: case.get("glob"))(case_dir)
    if glob_spec:
        glob_dir, pattern = glob_spec
        full_dir = glob_dir if glob_dir.is_absolute() else case_dir / glob_dir
        if not list(full_dir.glob(pattern)):
            failures.append(f"{case['name']} expected files matching {full_dir / pattern}")
    for rel_path, needle in case.get("contains", []):
        full_path = rel_path if rel_path.is_absolute() else case_dir / rel_path
        content = full_path.read_text(encoding="utf-8") if full_path.exists() else ""
        if needle not in content:
            failures.append(f"{case['name']} missing {needle!r} in {full_path}")
    for rel_path, needles in case.get("contains_any", []):
        full_path = rel_path if rel_path.is_absolute() else case_dir / rel_path
        content = full_path.read_text(encoding="utf-8") if full_path.exists() else ""
        if not any(needle in content for needle in needles):
            failures.append(f"{case['name']} missing any of {needles!r} in {full_path}")
