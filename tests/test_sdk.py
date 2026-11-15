from __future__ import annotations

import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import shutil
import threading
from urllib import error as urlerror, request as urlrequest

import pytest
from networkx.readwrite import json_graph
import networkx as nx

from graph3d.sdk import Graph3dClient, GraphLoadError


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


def test_sdk_cli_mode_uses_real_cli(tmp_path):
    graph_path = tmp_path / "graph3d-out" / "graph.json"
    _write_graph(graph_path)
    executable = shutil.which("graph3d")
    assert executable, "Install the project before running SDK CLI contract tests"
    client = Graph3dClient(mode="cli", graph=graph_path, cli_executable=executable)
    for mode in ("bfs", "dfs"):
        response = client.query("Alpha", mode=mode)
        assert "Alpha" in response.answer
        assert mode.upper() in response.answer
    assert "Beta" in client.explain("Alpha").answer
    assert "Alpha" in client.affected("Beta", relations=("calls",)).answer
    assert "Alpha" not in client.affected("Beta", relations=("imports",)).answer
    assert "Shortest path (1 hops)" in client.path("Alpha", "Beta").path[0]


def test_sdk_cli_update_uses_target_directory(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    source = corpus / "example.py"
    source.write_text("def alpha():\n    return 1\n", encoding="utf-8")
    client = Graph3dClient(
        mode="cli", graph=tmp_path / "unused.json", cli_executable=shutil.which("graph3d")
    )
    assert client.update(corpus).ok
    graph = corpus / "graph3d-out" / "graph.json"
    assert graph.is_file()
    source.write_text("def beta():\n    return 2\n", encoding="utf-8")
    assert client.update(corpus).ok
    data = json.loads(graph.read_text(encoding="utf-8"))
    assert any("beta" in node["label"] for node in data["nodes"])


@pytest.mark.parametrize("operation", ["query", "explain", "path", "affected"])
@pytest.mark.parametrize("content", [None, "{invalid", "[]", '{"nodes": []}'])
def test_sdk_loading_raises_library_exception(tmp_path, operation, content):
    graph = tmp_path / "graph.json"
    if content is not None:
        graph.write_text(content, encoding="utf-8")
    client = Graph3dClient(graph=graph)
    args = ("Alpha", "Beta") if operation == "path" else ("Alpha",)
    with pytest.raises(GraphLoadError):
        getattr(client, operation)(*args)


@pytest.mark.parametrize("api_key", [None, "sdk-contract-value"])
def test_sdk_http_authentication_uses_real_server(api_key):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append((self.path, self.headers.get("Authorization")))
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert body["question"] == "Alpha"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"schema_version":"1.0.0","answer":"authenticated"}')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = Graph3dClient(
            mode="http", base_url=f"http://127.0.0.1:{server.server_port}", api_key=api_key
        )
        assert client.query("Alpha").answer == "authenticated"
        expected = "Bearer " + api_key if api_key else None
        assert requests == [("/graphs/local/query", expected)]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_sdk_http_blocks_authenticated_cross_origin_redirects():
    received = []

    class Destination(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    destination = ThreadingHTTPServer(("127.0.0.1", 0), Destination)

    class Redirect(BaseHTTPRequestHandler):
        def do_POST(self):
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{destination.server_port}/target")
            self.end_headers()

        def log_message(self, *args):
            pass

    redirect = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    threads = [
        threading.Thread(target=server.serve_forever, daemon=True)
        for server in (destination, redirect)
    ]
    for thread in threads:
        thread.start()
    try:
        client = Graph3dClient(
            mode="http", base_url=f"http://127.0.0.1:{redirect.server_port}",
            api_key="sdk-contract-value",
        )
        with pytest.raises(urlerror.HTTPError, match="Unsafe redirect"):
            client.query("Alpha")
        assert received == []
    finally:
        for server in (destination, redirect):
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join()


def test_sdk_http_redirect_policy():
    from graph3d.sdk import _SafeRedirectHandler

    handler = _SafeRedirectHandler()
    request = urlrequest.Request("https://example.test/query", headers={"Authorization": "test"})
    allowed = handler.redirect_request(
        request, None, 302, "Found", {}, "https://example.test:443/result"
    )
    assert allowed.get_header("Authorization") == "test"
    with pytest.raises(urlerror.HTTPError):
        handler.redirect_request(request, None, 302, "Found", {}, "http://example.test/result")


def test_sdk_http_retries_only_idempotent_reads(monkeypatch):
    calls = {"count": 0}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def read(self):
            return b'{"schema_version":"1.0.0","answer":"ok"}'

    def fake_urlopen(self, request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise TimeoutError("first attempt times out")
        return FakeResponse()

    monkeypatch.setattr("urllib.request.OpenerDirector.open", fake_urlopen)
    client = Graph3dClient(mode="http", base_url="https://example.test", max_read_retries=1)
    response = client.query("Alpha")
    assert response.answer == "ok"
    assert calls["count"] == 2

    calls["count"] = 0

    def always_timeout(self, request, timeout):
        calls["count"] += 1
        raise TimeoutError("timeout")

    monkeypatch.setattr("urllib.request.OpenerDirector.open", always_timeout)
    with pytest.raises(TimeoutError):
        client.update(".")
    assert calls["count"] == 1
