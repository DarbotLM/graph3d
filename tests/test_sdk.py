from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from networkx.readwrite import json_graph
import networkx as nx

from graph3d.sdk import Graph3dClient


def _write_graph(path: Path) -> None:
    graph = nx.DiGraph()
    graph.add_node("a", label="Alpha", source_file="alpha.py", community=0)
    graph.add_node("b", label="Beta", source_file="beta.py", community=0)
    graph.add_edge("a", "b", relation="calls", confidence="EXTRACTED")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_graph.node_link_data(graph, edges="links")), encoding="utf-8")


def test_sdk_local_query_path_and_explain(tmp_path):
    graph_path = tmp_path / "graph3d-out" / "graph.json"
    _write_graph(graph_path)
    client = Graph3dClient(mode="local", graph=graph_path)

    query = client.query("Alpha")
    assert query.schema_version == "1.0.0"
    assert "Alpha" in query.answer

    explain = client.explain("Alpha")
    assert "Neighbors" in explain.answer
    assert "Beta" in explain.answer

    path = client.path("Alpha", "Beta")
    assert path.hops == 1
    assert path.path == ["Alpha", "Beta"]


def test_sdk_cli_mode_uses_json_flag(monkeypatch, tmp_path):
    graph_path = tmp_path / "graph3d-out" / "graph.json"
    _write_graph(graph_path)
    commands: list[list[str]] = []

    def fake_run(command, check, capture_output, text):
        commands.append(command)
        return Mock(stdout='{"schema_version":"1.0.0","answer":"ok"}')

    monkeypatch.setattr("subprocess.run", fake_run)
    client = Graph3dClient(mode="cli", graph=graph_path, cli_executable="graph3d")
    response = client.query("Alpha")

    assert response.answer == "ok"
    assert commands
    assert "--format" in commands[0]
    assert "json" in commands[0]


def test_sdk_http_retries_only_idempotent_reads(monkeypatch):
    calls = {"count": 0}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def read(self):
            return b'{"schema_version":"1.0.0","answer":"ok"}'

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("first attempt times out")
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = Graph3dClient(mode="http", base_url="https://example.test", max_read_retries=1)
    response = client.query("Alpha")
    assert response.answer == "ok"
    assert calls["count"] == 2

    calls["count"] = 0

    def always_timeout(request, timeout):
        calls["count"] += 1
        raise TimeoutError("timeout")

    monkeypatch.setattr("urllib.request.urlopen", always_timeout)
    with pytest.raises(TimeoutError):
        client.update(".")
    assert calls["count"] == 1
