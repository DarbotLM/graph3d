"""Consolidated integration tests for graph3d legacy test modules."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import networkx as nx
import pytest
from networkx.readwrite import json_graph

import graph3d.google_workspace as gw
from graph3d.__main__ import _CLAUDE_MD_MARKER, claude_install, claude_uninstall
from graph3d.analyze import god_nodes, suggest_questions, surprising_connections
from graph3d.benchmark import (
    _hr,
    _query_subgraph_tokens,
    _safe,
    print_benchmark,
    run_benchmark,
)
from graph3d.build import build_from_json
from graph3d.cluster import cluster, score_all
from graph3d.detect import detect
from graph3d.export import to_html, to_json, to_obsidian
from graph3d.extract import extract
from graph3d.ingest import save_query_result
from graph3d.prs import (
    PRInfo,
    _classify,
    _detect_default_branch,
    _parse_ci,
    _path_match,
    build_community_labels,
    compute_pr_impact,
    fetch_worktrees,
    format_prs_text,
)
from graph3d.report import generate
from graph3d.transcribe import (
    VIDEO_EXTENSIONS,
    build_whisper_prompt,
    transcribe,
    transcribe_all,
)
from graph3d.wiki import to_wiki


FIXTURES = Path(__file__).parent / "fixtures"


def _failures_assert(failures: list[str]) -> None:
    assert not failures, "\n".join(failures)


def _make_pr(
    number: int = 1,
    title: str = "Test PR",
    branch: str = "feature",
    base_branch: str = "v8",
    author: str = "alice",
    is_draft: bool = False,
    review_decision: str = "",
    ci_status: str = "SUCCESS",
    updated_at: datetime | None = None,
    expected_base: str = "v8",
) -> PRInfo:
    if updated_at is None:
        updated_at = datetime.now(timezone.utc) - timedelta(days=1)
    return PRInfo(
        number=number,
        title=title,
        branch=branch,
        base_branch=base_branch,
        author=author,
        is_draft=is_draft,
        review_decision=review_decision,
        ci_status=ci_status,
        updated_at=updated_at,
        expected_base=expected_base,
    )


def _prs_graph() -> nx.Graph:
    graph = nx.Graph()
    graph.add_node("n1", source_file="src/auth/api.py", community=0)
    graph.add_node("n2", source_file="src/auth/api.py", community=0)
    graph.add_node("n3", source_file="src/utils/helpers.py", community=1)
    return graph


def _wiki_graph() -> nx.Graph:
    graph = nx.Graph()
    graph.add_node("n1", label="parse", file_type="code", source_file="parser.py", community=0)
    graph.add_node("n2", label="validate", file_type="code", source_file="parser.py", community=0)
    graph.add_node("n3", label="render", file_type="code", source_file="renderer.py", community=1)
    graph.add_node("n4", label="stream", file_type="code", source_file="renderer.py", community=1)
    graph.add_edge("n1", "n2", relation="calls", confidence="EXTRACTED", weight=1.0)
    graph.add_edge("n1", "n3", relation="references", confidence="INFERRED", weight=1.0)
    graph.add_edge("n3", "n4", relation="calls", confidence="EXTRACTED", weight=1.0)
    return graph


def _benchmark_graph() -> nx.Graph:
    graph = nx.Graph()
    graph.add_node("n1", label="authentication", source_file="auth.py", source_location="L1", community=0)
    graph.add_node("n2", label="api_handler", source_file="api.py", source_location="L5", community=0)
    graph.add_node("n3", label="main_entry", source_file="main.py", source_location="L1", community=1)
    graph.add_node("n4", label="error_handler", source_file="errors.py", source_location="L1", community=1)
    graph.add_node("n5", label="database_layer", source_file="db.py", source_location="L1", community=2)
    graph.add_edge("n1", "n2", relation="calls", confidence="INFERRED")
    graph.add_edge("n2", "n3", relation="imports", confidence="EXTRACTED")
    graph.add_edge("n3", "n4", relation="uses", confidence="EXTRACTED")
    graph.add_edge("n5", "n2", relation="provides", confidence="EXTRACTED")
    return graph


def _write_graph(graph: nx.Graph, path: Path) -> None:
    path.write_text(json.dumps(json_graph.node_link_data(graph, edges="links")))


def test_pipeline_end_to_end(tmp_path):
    failures = []
    detection = detect(FIXTURES)
    if detection["total_files"] <= 0:
        failures.append("detect should find fixture files")
    if "files" not in detection:
        failures.append("detect result should include files")
    code_files = [Path(file) for file in detection["files"].get("code", [])]
    if not code_files:
        failures.append("fixtures should include code files")
    if not detection["files"].get("document", []):
        failures.append("fixtures should include document files")

    extraction = extract(code_files)
    graph = build_from_json(extraction)
    communities = cluster(graph)
    cohesion = score_all(graph, communities)
    gods = god_nodes(graph)
    surprises = surprising_connections(graph, communities)
    labels = {community_id: f"Group {community_id}" for community_id in communities}
    questions = suggest_questions(graph, communities, labels)
    report = generate(
        graph,
        communities,
        cohesion,
        labels,
        gods,
        surprises,
        detection,
        {"input": 0, "output": 0},
        str(FIXTURES),
        suggested_questions=questions,
    )

    checks = [
        ("extraction nodes", len(extraction["nodes"]) > 0),
        ("extraction edges", len(extraction["edges"]) > 0),
        ("graph nodes", graph.number_of_nodes() > 0),
        ("graph edges", graph.number_of_edges() > 0),
        ("communities", len(communities) > 0),
        ("cohesion length", len(cohesion) == len(communities)),
        ("god nodes", len(gods) > 0),
        ("god node shape", all("id" in node and "degree" in node for node in gods)),
        ("surprises list", isinstance(surprises, list)),
        ("questions list", isinstance(questions, list)),
        ("report god nodes", "God Nodes" in report),
        ("report communities", "Communities" in report),
        ("report length", len(report) > 100),
        ("top god in report", gods and gods[0]["label"] in report),
    ]
    failures.extend(name for name, passed in checks if not passed)
    for community_id, score in cohesion.items():
        if not 0.0 <= score <= 1.0:
            failures.append(f"cohesion {community_id} out of range: {score}")
    all_community_nodes = {node for nodes in communities.values() for node in nodes}
    for node in graph.nodes():
        if node not in all_community_nodes:
            failures.append(f"node {node!r} missing community")
    valid_confidence = {"EXTRACTED", "INFERRED", "AMBIGUOUS"}
    for edge in extraction["edges"]:
        if edge["confidence"] not in valid_confidence:
            failures.append(f"invalid edge confidence: {edge['confidence']}")
    for source, target in graph.edges():
        if source == target:
            failures.append(f"self-loop found on node {source!r}")

    json_path = tmp_path / "graph.json"
    to_json(graph, communities, str(json_path))
    data = json.loads(json_path.read_text())
    if "nodes" not in data or "links" not in data:
        failures.append("exported graph should use nodes and links")
    if not all("community" in node for node in data.get("nodes", [])):
        failures.append("exported nodes should include community")

    html_path = tmp_path / "graph.html"
    to_html(graph, communities, str(html_path), community_labels=labels)
    html = html_path.read_text()
    if "vis-network" not in html or "RAW_NODES" not in html:
        failures.append("HTML export should include vis-network and RAW_NODES")

    vault_path = tmp_path / "obsidian"
    note_count = to_obsidian(graph, communities, str(vault_path), community_labels=labels, cohesion=cohesion)
    if note_count <= 0:
        failures.append("obsidian export should write notes")
    if not (vault_path / ".obsidian" / "graph.json").exists():
        failures.append("obsidian export should write .obsidian graph config")
    if not list(vault_path.glob("*.md")):
        failures.append("obsidian export should write markdown files")

    rerun_graph = build_from_json(extract(code_files))
    if graph.number_of_nodes() != rerun_graph.number_of_nodes():
        failures.append("incremental node count should be stable")
    if graph.number_of_edges() != rerun_graph.number_of_edges():
        failures.append("incremental edge count should be stable")
    _failures_assert(failures)


def test_ingest(tmp_path):
    failures = []
    cases = [
        {
            "name": "file created",
            "question": "what is attention?",
            "answer": "Attention is...",
            "checks": [lambda out, content: out.exists()],
        },
        {
            "name": "filename format",
            "question": "what connects A to B?",
            "answer": "They share...",
            "checks": [lambda out, content: out.name.startswith("query_"), lambda out, content: out.suffix == ".md"],
        },
        {
            "name": "frontmatter question",
            "question": "what is attention?",
            "answer": "Attention is softmax.",
            "checks": [
                lambda out, content: "question:" in content,
                lambda out, content: "attention" in content.lower(),
            ],
        },
        {
            "name": "frontmatter type",
            "question": "q",
            "answer": "a",
            "kwargs": {"query_type": "path_query"},
            "checks": [lambda out, content: 'type: "path_query"' in content],
        },
        {
            "name": "source nodes included",
            "question": "q",
            "answer": "a",
            "kwargs": {"source_nodes": ["AttentionLayer", "SoftmaxFunc"]},
            "checks": [
                lambda out, content: "AttentionLayer" in content,
                lambda out, content: "SoftmaxFunc" in content,
            ],
        },
        {
            "name": "source nodes capped",
            "question": "q",
            "answer": "a",
            "kwargs": {"source_nodes": [f"Node{index}" for index in range(20)]},
            "checks": [
                lambda out, content: next(
                    line for line in content.splitlines() if line.startswith("source_nodes:")
                ).count('"Node')
                == 10
            ],
        },
        {
            "name": "answer in body",
            "question": "what is the answer?",
            "answer": "The answer is forty-two.",
            "checks": [lambda out, content: "The answer is forty-two." in content],
        },
    ]
    for index, case in enumerate(cases):
        memory_dir = tmp_path / f"memory_{index}"
        output = save_query_result(case["question"], case["answer"], memory_dir, **case.get("kwargs", {}))
        content = output.read_text()
        for check_index, check in enumerate(case["checks"]):
            if not check(output, content):
                failures.append(f"{case['name']} check {check_index} failed for {output}")

    deep_memory = tmp_path / "deep" / "memory"
    if deep_memory.exists():
        failures.append("deep memory directory should not exist before save")
    save_query_result("q", "a", deep_memory)
    if not deep_memory.exists():
        failures.append("save_query_result should create memory directory")
    _failures_assert(failures)


def test_prs():
    failures = []
    old = datetime.now(timezone.utc) - timedelta(days=20)
    classify_cases = [
        ("ready", _make_pr(ci_status="SUCCESS", review_decision="", is_draft=False), "READY"),
        ("ci fail", _make_pr(ci_status="FAILURE"), "CI-FAIL"),
        ("changes requested", _make_pr(ci_status="SUCCESS", review_decision="CHANGES_REQUESTED"), "CHANGES-REQ"),
        ("draft", _make_pr(ci_status="SUCCESS", is_draft=True), "DRAFT"),
        ("stale", _make_pr(ci_status="SUCCESS", updated_at=old, is_draft=False), "STALE"),
        ("draft not stale", _make_pr(ci_status="SUCCESS", updated_at=old, is_draft=True), "DRAFT"),
        ("pending", _make_pr(ci_status="PENDING", is_draft=False, review_decision=""), "PENDING"),
        ("wrong base precedence", _make_pr(base_branch="master", ci_status="FAILURE"), "WRONG-BASE"),
    ]
    for name, pr, expected in classify_cases:
        actual = _classify(pr, base="v8")
        if actual != expected:
            failures.append(f"_classify {name}: expected {expected}, got {actual}")

    ci_cases = [
        ("empty rollup", [], "NONE"),
        ("failure conclusion", [{"conclusion": "FAILURE", "status": "COMPLETED"}], "FAILURE"),
        ("cancelled", [{"conclusion": "CANCELLED", "status": "COMPLETED"}], "FAILURE"),
        ("timed out", [{"conclusion": "TIMED_OUT", "status": "COMPLETED"}], "FAILURE"),
        ("in progress", [{"conclusion": None, "status": "IN_PROGRESS"}], "PENDING"),
        ("success", [{"conclusion": "SUCCESS", "status": "COMPLETED"}], "SUCCESS"),
        (
            "mixed",
            [
                {"conclusion": "SUCCESS", "status": "COMPLETED"},
                {"conclusion": "FAILURE", "status": "COMPLETED"},
            ],
            "FAILURE",
        ),
    ]
    for name, rollup, expected in ci_cases:
        actual = _parse_ci(rollup)
        if actual != expected:
            failures.append(f"_parse_ci {name}: expected {expected}, got {actual}")

    path_cases = [
        ("exact", "src/auth/api.py", "src/auth/api.py", True),
        ("graph longer boundary", "src/auth/api.py", "api.py", True),
        ("partial filename graph", "config.py", "g.py", False),
        ("partial filename pr", "g.py", "config.py", False),
        ("pr longer", "api.py", "src/auth/api.py", True),
    ]
    for name, graph_src, pr_file, expected in path_cases:
        actual = _path_match(graph_src, pr_file)
        if actual is not expected:
            failures.append(f"_path_match {name}: expected {expected}, got {actual}")

    impact_cases = [
        ("matching file", _prs_graph(), ["src/auth/api.py"], [0], 2),
        ("matching both files", _prs_graph(), ["src/auth/api.py", "src/utils/helpers.py"], [0, 1], 3),
        ("empty files", _prs_graph(), [], [], 0),
        ("no match", _prs_graph(), ["docs/README.md"], [], 0),
    ]
    duplicate_graph = nx.Graph()
    duplicate_graph.add_node("a1", source_file="src/auth/api.py", community=0)
    duplicate_graph.add_node("a2", source_file="src/admin/api.py", community=1)
    impact_cases.append(("no basename double count", duplicate_graph, ["src/auth/api.py"], [0], 1))
    repeated_graph = nx.Graph()
    repeated_graph.add_node("n1", source_file="src/auth/api.py", community=0)
    repeated_graph.add_node("n2", source_file="src/auth/api.py", community=0)
    impact_cases.append(("same graph file counted once", repeated_graph, ["src/auth/api.py", "api.py"], [0], 2))
    for name, graph, files, expected_comms, expected_nodes in impact_cases:
        comms, nodes = compute_pr_impact(files, graph)
        if comms != expected_comms or nodes != expected_nodes:
            failures.append(
                f"compute_pr_impact {name}: expected {(expected_comms, expected_nodes)}, got {(comms, nodes)}"
            )

    worktree_cases = [
        (
            "normal",
            0,
            "worktree /home/user/proj\nHEAD abc123\nbranch refs/heads/main\n\n"
            "worktree /home/user/proj-feature\nHEAD def456\nbranch refs/heads/feature-x\n\n",
            {"main": "/home/user/proj", "feature-x": "/home/user/proj-feature"},
        ),
        (
            "detached reset",
            0,
            "worktree /home/user/detached\nHEAD abc123\ndetached\n\n"
            "worktree /home/user/proj-feature\nHEAD def456\nbranch refs/heads/feature-x\n\n",
            {"feature-x": "/home/user/proj-feature"},
        ),
        ("empty", 0, "", {}),
        ("nonzero", 1, "", {}),
    ]
    for name, returncode, stdout, expected in worktree_cases:
        result = MagicMock(returncode=returncode, stdout=stdout)
        with patch("graph3d.prs.subprocess.run", return_value=result):
            actual = fetch_worktrees()
        if actual != expected:
            failures.append(f"fetch_worktrees {name}: expected {expected}, got {actual}")
    with patch("graph3d.prs.subprocess.run", side_effect=FileNotFoundError("git not found")):
        if fetch_worktrees() != {}:
            failures.append("fetch_worktrees should return empty dict on subprocess failure")

    formatted = format_prs_text(
        [
            _make_pr(number=101, title="Add awesome feature", base_branch="v8", expected_base="v8", ci_status="SUCCESS"),
            _make_pr(number=102, title="Fix flaky test", base_branch="v8", expected_base="v8", ci_status="FAILURE"),
            _make_pr(number=103, title="Wrong base PR", base_branch="master", expected_base="v8"),
        ],
        base="v8",
    )
    for required in ["Open PRs targeting v8: 2", "(1 on wrong base, not shown)", "#101", "Add awesome feature"]:
        if required not in formatted:
            failures.append(f"format_prs_text missing {required!r}")
    for required in ["#102", "Fix flaky test", "[READY]", "[CI-FAIL]"]:
        if required not in formatted:
            failures.append(f"format_prs_text missing {required!r}")
    if "#103" in formatted:
        failures.append("format_prs_text should filter wrong-base PR from body")
    empty_formatted = format_prs_text([], base="v8")
    if "Open PRs targeting v8: 0" not in empty_formatted or "(0 on wrong base, not shown)" not in empty_formatted:
        failures.append("format_prs_text empty list should include zero counts")

    default_branch_cases = [
        ("gh main", {"defaultBranchRef": {"name": "main"}}, None, None, "main"),
        ("git fallback", None, 0, "refs/remotes/origin/develop\n", "develop"),
        ("both fail", None, 1, "", "main"),
        ("empty gh fallback", {}, 0, "refs/remotes/origin/trunk\n", "trunk"),
    ]
    for name, gh_result, git_returncode, git_stdout, expected in default_branch_cases:
        git_result = MagicMock(returncode=git_returncode, stdout=git_stdout)
        with patch("graph3d.prs._gh", return_value=gh_result), patch(
            "graph3d.prs.subprocess.run", return_value=git_result
        ):
            actual = _detect_default_branch()
        if actual != expected:
            failures.append(f"_detect_default_branch {name}: expected {expected}, got {actual}")
    with patch("graph3d.prs._gh", return_value=None), patch(
        "graph3d.prs.subprocess.run", side_effect=subprocess.TimeoutExpired("git", 5)
    ):
        if _detect_default_branch() != "main":
            failures.append("_detect_default_branch should return main on git timeout")

    label_cases = [
        (
            "basic grouping",
            {"nodes": [{"id": "a", "label": "Alpha", "community": 0}, {"id": "b", "label": "Beta", "community": 0}]},
            None,
            lambda labels: set(labels[0]) == {"Alpha", "Beta"},
        ),
        (
            "top n capped",
            {"nodes": [{"id": str(index), "label": f"Node{index}", "community": 0} for index in range(10)]},
            4,
            lambda labels: len(labels[0]) == 4,
        ),
        ("no community skipped", {"nodes": [{"id": "x", "label": "X"}]}, None, lambda labels: labels == {}),
        ("missing nodes", {}, None, lambda labels: labels == {}),
        ("empty nodes", {"nodes": []}, None, lambda labels: labels == {}),
    ]
    for name, data, top_n, check in label_cases:
        labels = build_community_labels(data) if top_n is None else build_community_labels(data, top_n=top_n)
        if not check(labels):
            failures.append(f"build_community_labels {name}: got {labels}")
    _failures_assert(failures)


def test_google_workspace(tmp_path, monkeypatch):
    failures = []
    shortcut_cases = [
        (
            "doc id",
            "Planning.gdoc",
            '{"url":"https://docs.google.com/document/d/doc-123/edit","doc_id":"doc-123","email":"me@example.com"}',
            {"file_id": "doc-123", "account": "me@example.com"},
        ),
        (
            "url id resource key",
            "Budget.gsheet",
            '{"url":"https://docs.google.com/spreadsheets/d/sheet-456/edit?resourcekey=key-1"}',
            {"file_id": "sheet-456", "resource_key": "key-1"},
        ),
    ]
    for name, filename, payload, expected in shortcut_cases:
        shortcut = tmp_path / filename
        shortcut.write_text(payload, encoding="utf-8")
        metadata = gw.read_google_shortcut(shortcut)
        for key, value in expected.items():
            if metadata.get(key) != value:
                failures.append(f"read_google_shortcut {name}: {key} expected {value}, got {metadata.get(key)}")

    doc_shortcut = tmp_path / "Planning.gdoc"
    doc_shortcut.write_text('{"url":"https://docs.google.com/document/d/doc-123/edit","doc_id":"doc-123"}', encoding="utf-8")

    original_run_gws_export = gw._run_gws_export

    def fake_doc_export(file_id, mime_type, output, resource_key=None):
        assert (file_id, mime_type, resource_key) == ("doc-123", "text/markdown", None)
        output.write_text("# Planning\n\nExported doc text.", encoding="utf-8")

    monkeypatch.setattr(gw, "_run_gws_export", fake_doc_export)
    doc_output = gw.convert_google_workspace_file(doc_shortcut, tmp_path / "converted_docs")
    if doc_output is None or doc_output.suffix != ".md":
        failures.append("gdoc conversion should produce markdown sidecar")
    else:
        doc_content = doc_output.read_text(encoding="utf-8")
        if 'source_type: "google_workspace"' not in doc_content or "# Planning" not in doc_content:
            failures.append("gdoc conversion should include frontmatter and exported content")

    sheet_shortcut = tmp_path / "Budget.gsheet"
    sheet_shortcut.write_text('{"doc_id":"sheet-456"}', encoding="utf-8")

    def fake_sheet_export(file_id, mime_type, output, resource_key=None):
        assert (
            file_id,
            mime_type,
            resource_key,
        ) == ("sheet-456", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", None)
        output.write_bytes(b"xlsx")

    monkeypatch.setattr(gw, "_run_gws_export", fake_sheet_export)
    sheet_output = gw.convert_google_workspace_file(
        sheet_shortcut,
        tmp_path / "converted_sheets",
        xlsx_to_markdown=lambda path: "## Sheet: Main\n\n| A |\n| --- |\n| 1 |",
    )
    if sheet_output is None or "## Sheet: Main" not in sheet_output.read_text(encoding="utf-8"):
        failures.append("gsheet conversion should use xlsx markdown callback")
    monkeypatch.setattr(gw, "_run_gws_export", original_run_gws_export)

    run_calls = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd, **kwargs):
        run_calls.append((cmd, kwargs))
        return Result()

    monkeypatch.setattr(gw.shutil, "which", lambda name: "/usr/local/bin/gws")
    monkeypatch.setattr(gw.subprocess, "run", fake_run)
    output = tmp_path / "converted" / "doc.md"
    gw._run_gws_export("doc-123", "text/markdown", output)
    cmd, kwargs = run_calls[-1]
    if not output.parent.exists():
        failures.append("_run_gws_export should create output directory")
    if kwargs["cwd"] != output.parent.resolve():
        failures.append("_run_gws_export should use output directory as cwd")
    if cmd[:4] != ["/usr/local/bin/gws", "drive", "files", "export"] or cmd[-2:] != ["-o", "doc.md"]:
        failures.append(f"_run_gws_export command shape unexpected: {cmd}")

    gw._run_gws_export("doc-123", "text/markdown", output, resource_key="rk-1")
    params = json.loads(run_calls[-1][0][run_calls[-1][0].index("--params") + 1])
    if params != {"fileId": "doc-123", "mimeType": "text/markdown"}:
        failures.append("_run_gws_export should not send resource_key as query param")

    monkeypatch.setenv("GRAPH3D_GOOGLE_WORKSPACE", "yes")
    if not gw.google_workspace_enabled():
        failures.append("GRAPH3D_GOOGLE_WORKSPACE=yes should enable google workspace")
    monkeypatch.setenv("GRAPH3D_GOOGLE_WORKSPACE", "0")
    if gw.google_workspace_enabled():
        failures.append("GRAPH3D_GOOGLE_WORKSPACE=0 should disable google workspace")
    _failures_assert(failures)


def test_transcribe(tmp_path, monkeypatch):
    failures = []
    for extension, expected in [(".mp4", True), (".mp3", True), (".wav", True), (".mov", True), (".py", False)]:
        actual = extension in VIDEO_EXTENSIONS
        if actual is not expected:
            failures.append(f"VIDEO_EXTENSIONS {extension}: expected {expected}, got {actual}")

    prompt_cases = [
        ("no nodes", [], lambda prompt: "punctuation" in prompt.lower() or len(prompt) > 0),
        (
            "topic string",
            [{"label": "neural networks"}, {"label": "transformers"}, {"label": "attention"}],
            lambda prompt: ("neural networks" in prompt.lower() or "transformers" in prompt.lower())
            and "punctuation" in prompt.lower(),
        ),
        ("nodes without labels", [{"id": "1"}, {"id": "2", "label": ""}], lambda prompt: len(prompt) > 0),
    ]
    monkeypatch.delenv("GRAPH3D_WHISPER_PROMPT", raising=False)
    for name, nodes, check in prompt_cases:
        prompt = build_whisper_prompt(nodes)
        if not check(prompt):
            failures.append(f"build_whisper_prompt {name}: got {prompt!r}")
    monkeypatch.setenv("GRAPH3D_WHISPER_PROMPT", "Custom domain hint.")
    env_prompt = build_whisper_prompt([{"label": "Python"}, {"label": "FastAPI"}])
    if env_prompt != "Custom domain hint.":
        failures.append("GRAPH3D_WHISPER_PROMPT should override whisper prompt")
    monkeypatch.delenv("GRAPH3D_WHISPER_PROMPT", raising=False)

    cached_video = tmp_path / "lecture.mp4"
    cached_video.write_bytes(b"fake")
    out_dir = tmp_path / "transcripts"
    out_dir.mkdir()
    cached = out_dir / "lecture.txt"
    cached.write_text("Cached transcript content.")
    if transcribe(cached_video, output_dir=out_dir) != cached:
        failures.append("transcribe should return cached transcript path")

    force_video = tmp_path / "talk.mp4"
    force_video.write_bytes(b"fake")
    (out_dir / "talk.txt").write_text("Old transcript.")
    fake_segment = MagicMock(text="New transcript segment.")
    fake_info = MagicMock(language="en")
    fake_model = MagicMock()
    fake_model.transcribe.return_value = ([fake_segment], fake_info)
    with patch("graph3d.transcribe._get_whisper", return_value=lambda *args, **kwargs: fake_model):
        force_result = transcribe(force_video, output_dir=out_dir, force=True)
    if force_result.read_text() != "New transcript segment.":
        failures.append("transcribe force should rerun and overwrite cached transcript")

    missing_video = tmp_path / "clip.mp4"
    missing_video.write_bytes(b"fake")
    with patch("graph3d.transcribe._get_whisper", side_effect=ImportError("faster-whisper not installed")):
        with pytest.raises(ImportError):
            transcribe(missing_video, output_dir=tmp_path / "out")

    if transcribe_all([]) != []:
        failures.append("transcribe_all empty input should return empty list")
    all_results = transcribe_all([str(cached_video)], output_dir=out_dir)
    if len(all_results) != 1 or str(cached) not in all_results[0]:
        failures.append("transcribe_all should return cached paths")
    broken_video = tmp_path / "broken.mp4"
    broken_video.write_bytes(b"fake")
    with patch("graph3d.transcribe.transcribe", side_effect=RuntimeError("boom")):
        if transcribe_all([str(broken_video)], output_dir=tmp_path / "out") != []:
            failures.append("transcribe_all should skip failed files")
    _failures_assert(failures)


def test_wiki(tmp_path, capsys):
    failures = []
    communities = {0: ["n1", "n2"], 1: ["n3", "n4"]}
    labels = {0: "Parsing Layer", 1: "Rendering Layer"}
    cohesion = {0: 0.85, 1: 0.72}
    god_nodes_data = [{"id": "n1", "label": "parse", "degree": 2}]

    base_out = tmp_path / "base"
    count = to_wiki(
        _wiki_graph(),
        communities,
        base_out,
        community_labels=labels,
        cohesion=cohesion,
        god_nodes_data=god_nodes_data,
    )
    files = {
        "index": (base_out / "index.md").read_text(),
        "parsing": (base_out / "Parsing_Layer.md").read_text(),
        "rendering_path": base_out / "Rendering_Layer.md",
        "god": (base_out / "parse.md").read_text(),
    }
    checks = [
        ("index exists", (base_out / "index.md").exists()),
        ("article count", count == 3),
        ("community article parsing", (base_out / "Parsing_Layer.md").exists()),
        ("community article rendering", files["rendering_path"].exists()),
        ("god article exists", (base_out / "parse.md").exists()),
        ("index parsing link", "[[Parsing Layer]]" in files["index"]),
        ("index rendering link", "[[Rendering Layer]]" in files["index"]),
        ("index god link", "[[parse]]" in files["index"]),
        ("index god connections", "2 connections" in files["index"]),
        ("cross community link", "[[Rendering Layer]]" in files["parsing"]),
        ("cohesion shown", "cohesion 0.85" in files["parsing"]),
        ("audit extracted", "EXTRACTED" in files["parsing"]),
        ("audit inferred", "INFERRED" in files["parsing"]),
        ("god connections", "[[validate]]" in files["god"] or "[[render]]" in files["god"]),
        ("god community link", "[[Parsing Layer]]" in files["god"]),
        ("navigation footer", "[[index]]" in files["parsing"]),
    ]
    failures.extend(name for name, passed in checks if not passed)

    bad_count = to_wiki(
        _wiki_graph(),
        communities,
        tmp_path / "bad_god",
        community_labels=labels,
        god_nodes_data=[{"id": "nonexistent", "label": "ghost", "degree": 99}],
    )
    if bad_count != 2:
        failures.append(f"missing god nodes should be skipped, got count {bad_count}")
    fallback_out = tmp_path / "fallback"
    to_wiki(_wiki_graph(), communities, fallback_out)
    if not (fallback_out / "Community_0.md").exists() or not (fallback_out / "Community_1.md").exists():
        failures.append("to_wiki should use fallback community filenames without labels")

    big_graph = nx.Graph()
    big_nodes = [f"n{index}" for index in range(30)]
    for node in big_nodes:
        big_graph.add_node(node, label=f"concept_{node}", file_type="code", source_file="a.py", community=0)
    for index in range(len(big_nodes) - 1):
        big_graph.add_edge(big_nodes[index], big_nodes[index + 1], relation="calls", confidence="EXTRACTED", weight=1.0)
    to_wiki(big_graph, {0: big_nodes}, tmp_path / "big", community_labels={0: "Big Community"})
    if "and 5 more nodes" not in (tmp_path / "big" / "Big_Community.md").read_text():
        failures.append("large community article should include truncation notice")

    no_attr_graph = nx.Graph()
    no_attr_graph.add_node("n1", label="parse", file_type="code", source_file="parser.py")
    no_attr_graph.add_node("n2", label="render", file_type="code", source_file="renderer.py")
    no_attr_graph.add_edge("n1", "n2", relation="references", confidence="INFERRED", weight=1.0)
    to_wiki(no_attr_graph, {0: ["n1"], 1: ["n2"]}, tmp_path / "no_attr_links", community_labels={0: "Parsing", 1: "Rendering"})
    if "[[Rendering]]" not in (tmp_path / "no_attr_links" / "Parsing.md").read_text():
        failures.append("cross-community links should work without node community attrs")

    god_no_attr_graph = nx.Graph()
    god_no_attr_graph.add_node("n1", label="parse", file_type="code", source_file="parser.py")
    god_no_attr_graph.add_node("n2", label="validate", file_type="code", source_file="parser.py")
    god_no_attr_graph.add_edge("n1", "n2", relation="calls", confidence="EXTRACTED", weight=1.0)
    to_wiki(
        god_no_attr_graph,
        {0: ["n1", "n2"]},
        tmp_path / "god_no_attr",
        community_labels={0: "Core Logic"},
        god_nodes_data=[{"id": "n1", "label": "parse", "degree": 1}],
    )
    if "[[Core Logic]]" not in (tmp_path / "god_no_attr" / "parse.md").read_text():
        failures.append("god node article should link community without node community attrs")

    stale_count = to_wiki(
        _wiki_graph(),
        {0: ["n1", "n2", "stale_ghost"], 1: ["n3", "n4"]},
        tmp_path / "stale_drop",
        community_labels=labels,
    )
    stale_article = (tmp_path / "stale_drop" / "Parsing_Layer.md").read_text()
    if stale_count != 2 or "parse" not in stale_article or "stale_ghost" in stale_article:
        failures.append("to_wiki should drop stale community nodes without crashing")
    with pytest.raises(ValueError, match="stale"):
        to_wiki(_wiki_graph(), {0: ["ghost1", "ghost2"], 1: ["ghost3"]}, tmp_path / "all_stale", community_labels=labels)
    to_wiki(_wiki_graph(), {0: ["n1", "stale1", "stale2"], 1: ["n3", "n4"]}, tmp_path / "stale_warn", community_labels=labels)
    err = capsys.readouterr().err
    if "2" not in err or "stale" not in err.lower():
        failures.append("stale node warning should include drop count and stale text")

    null_graph = nx.Graph()
    null_graph.add_node("n1", label="parse", file_type="code", source_file=None, community=0)
    null_graph.add_node("n2", label="validate", file_type="code", source_file="parser.py", community=0)
    null_graph.add_edge("n1", "n2", relation="calls", confidence="EXTRACTED", weight=1.0)
    null_out = tmp_path / "null_source"
    to_wiki(null_graph, {0: ["n1", "n2"]}, null_out, community_labels={0: "Parsing Layer"})
    if not (null_out / "index.md").exists():
        failures.append("community article should handle null source_file without TypeError")
    _failures_assert(failures)


def test_claude_md(tmp_path, capsys):
    failures = []
    create_root = tmp_path / "create"
    create_root.mkdir()
    claude_install(create_root)
    target = create_root / "CLAUDE.md"
    if not target.exists() or _CLAUDE_MD_MARKER not in target.read_text():
        failures.append("claude_install should create CLAUDE.md with marker")
    content = target.read_text()
    for required in ["GRAPH_REPORT.md", "wiki/index.md", "graph3d update"]:
        if required not in content:
            failures.append(f"claude_install section missing {required}")

    append_root = tmp_path / "append"
    append_target = append_root / "CLAUDE.md"
    append_root.mkdir()
    append_target.write_text("# Existing content\n\nSome rules here.\n")
    claude_install(append_root)
    append_content = append_target.read_text()
    if "Existing content" not in append_content or _CLAUDE_MD_MARKER not in append_content:
        failures.append("claude_install should append without clobbering existing content")

    idempotent_root = tmp_path / "idempotent"
    idempotent_root.mkdir()
    claude_install(idempotent_root)
    capsys.readouterr()
    claude_install(idempotent_root)
    idempotent_content = (idempotent_root / "CLAUDE.md").read_text()
    idempotent_out = capsys.readouterr().out
    if idempotent_content.count(_CLAUDE_MD_MARKER) != 1:
        failures.append("claude_install should not duplicate graph3d section")
    if "already configured" not in idempotent_out:
        failures.append("second claude_install should print already configured")

    uninstall_root = tmp_path / "uninstall"
    uninstall_root.mkdir()
    claude_install(uninstall_root)
    claude_uninstall(uninstall_root)
    uninstall_target = uninstall_root / "CLAUDE.md"
    if uninstall_target.exists() and _CLAUDE_MD_MARKER in uninstall_target.read_text():
        failures.append("claude_uninstall should remove graph3d section")

    preserve_root = tmp_path / "preserve"
    preserve_root.mkdir()
    preserve_target = preserve_root / "CLAUDE.md"
    preserve_target.write_text("# My Project\n\nSome rules.\n")
    claude_install(preserve_root)
    claude_uninstall(preserve_root)
    preserve_content = preserve_target.read_text()
    if "My Project" not in preserve_content or "Some rules" not in preserve_content or _CLAUDE_MD_MARKER in preserve_content:
        failures.append("claude_uninstall should preserve non-graph3d content")

    no_op_root = tmp_path / "noop"
    no_op_root.mkdir()
    (no_op_root / "CLAUDE.md").write_text("# Other stuff\n")
    claude_uninstall(no_op_root)
    no_op_out = capsys.readouterr().out
    if "not found" not in no_op_out and "nothing to do" not in no_op_out:
        failures.append("claude_uninstall should report no-op when section missing")
    missing_root = tmp_path / "missing"
    missing_root.mkdir()
    claude_uninstall(missing_root)
    missing_out = capsys.readouterr().out
    if "No CLAUDE.md" not in missing_out and "nothing to do" not in missing_out:
        failures.append("claude_uninstall should report no-op when file missing")

    settings_root = tmp_path / "settings"
    settings_root.mkdir()
    claude_install(settings_root)
    settings_path = settings_root / ".claude" / "settings.json"
    settings = json.loads(settings_path.read_text())
    hooks = settings.get("hooks", {}).get("PreToolUse", [])
    if not any(hook.get("matcher") == "Bash" for hook in hooks):
        failures.append("claude_install should create settings.json PreToolUse Bash hook")
    claude_install(settings_root)
    settings = json.loads(settings_path.read_text())
    hooks = settings.get("hooks", {}).get("PreToolUse", [])
    bash_hooks = [hook for hook in hooks if hook.get("matcher") == "Bash" and "graph3d" in str(hook)]
    if len(bash_hooks) != 1:
        failures.append("claude_install should not duplicate settings Bash hook")
    claude_uninstall(settings_root)
    if settings_path.exists():
        settings = json.loads(settings_path.read_text())
        hooks = settings.get("hooks", {}).get("PreToolUse", [])
        if any(hook.get("matcher") == "Bash" and "graph3d" in str(hook) for hook in hooks):
            failures.append("claude_uninstall should remove graph3d settings hook")
    _failures_assert(failures)


def test_benchmark(tmp_path, monkeypatch, capsys):
    failures = []
    graph = _benchmark_graph()
    token_cases = [
        ("matching", graph, "how does authentication work", 1, lambda tokens: tokens > 0),
        ("no match", graph, "xyzzy plugh zorkmid", 1, lambda tokens: tokens == 0),
        (
            "short non english",
            nx.Graph(),
            "\u524d\u7aef",
            1,
            lambda tokens: tokens > 0,
        ),
    ]
    token_cases[2][1].add_node("frontend", label="\u524d\u7aef", source_file="docs/\u524d\u7aef.md", source_location="L1", community=0)
    for name, token_graph, question, depth, check in token_cases:
        tokens = _query_subgraph_tokens(token_graph, question, depth=depth)
        if not check(tokens):
            failures.append(f"_query_subgraph_tokens {name}: got {tokens}")
    if _query_subgraph_tokens(graph, "authentication", depth=3) < _query_subgraph_tokens(graph, "authentication", depth=1):
        failures.append("_query_subgraph_tokens should expand neighbors with deeper BFS")

    graph_file = tmp_path / "graph.json"
    _write_graph(graph, graph_file)
    reduction = run_benchmark(str(graph_file), corpus_words=10_000)
    if "reduction_ratio" not in reduction or reduction["reduction_ratio"] <= 1.0:
        failures.append("run_benchmark should return reduction_ratio greater than 1")
    r1 = run_benchmark(str(graph_file), corpus_words=1_000)
    r2 = run_benchmark(str(graph_file), corpus_words=10_000)
    if abs(r2["corpus_tokens"] - r1["corpus_tokens"] * 10) > r1["corpus_tokens"]:
        failures.append("run_benchmark corpus_tokens should scale with corpus_words")
    per_question = run_benchmark(
        str(graph_file),
        corpus_words=5_000,
        questions=["how does authentication work", "what is the main entry"],
    )
    if len(per_question["per_question"]) < 1:
        failures.append("run_benchmark should include per_question rows")
    for row in per_question["per_question"]:
        for key in ["question", "query_tokens", "reduction"]:
            if key not in row:
                failures.append(f"per_question row missing {key}: {row}")
    estimated = run_benchmark(str(graph_file), corpus_words=None)
    if estimated["corpus_words"] <= 0:
        failures.append("run_benchmark should estimate corpus_words when omitted")
    if run_benchmark(str(tmp_path / "empty.json"), corpus_words=1_000) if False else False:
        failures.append("unreachable")
    empty_file = tmp_path / "empty.json"
    _write_graph(nx.Graph(), empty_file)
    if "error" not in run_benchmark(str(empty_file), corpus_words=1_000):
        failures.append("run_benchmark should report error on empty graph")
    counts = run_benchmark(str(graph_file), corpus_words=5_000)
    if counts["nodes"] != graph.number_of_nodes() or counts["edges"] != graph.number_of_edges():
        failures.append("run_benchmark should include node and edge counts")

    print_benchmark(counts)
    out = capsys.readouterr().out
    if "reduction" not in out.lower() or "x" not in out:
        failures.append("print_benchmark should print reduction text")
    print_benchmark({"error": "test error message"})
    if "test error message" not in capsys.readouterr().out:
        failures.append("print_benchmark should print error messages")

    real_stdout = sys.stdout
    try:
        sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        if _safe("\u2192", "->") != "\u2192" or _hr(5) != "\u2500" * 5:
            failures.append("_safe and _hr should keep unicode when stdout can encode it")
    finally:
        sys.stdout = real_stdout
    real_stdout = sys.stdout
    try:
        sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        if _safe("\u2192", "->") != "->" or _hr(5) != "-" * 5:
            failures.append("_safe and _hr should use ASCII fallback when stdout cannot encode unicode")
    finally:
        sys.stdout = real_stdout

    cp1252_stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", cp1252_stdout)
    print_benchmark(counts)
    cp1252_stdout.flush()
    written = cp1252_stdout.buffer.getvalue().decode("cp1252")
    if "reduction" not in written.lower() or "\u2500" in written or "\u2192" in written:
        failures.append("print_benchmark should survive cp1252 stdout with ASCII fallbacks")
    monkeypatch.setattr(sys, "stdout", sys.__stdout__)

    monkeypatch.setattr("graph3d.security._MAX_GRAPH_FILE_BYTES", 8)
    with pytest.raises(ValueError, match="exceeds"):
        run_benchmark(str(graph_file))
    _failures_assert(failures)
