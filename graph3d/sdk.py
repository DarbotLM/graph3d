"""Typed SDK client for local graph, CLI, and HTTP modes."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

import networkx as nx
from networkx.readwrite import json_graph

from graph3d.affected import DEFAULT_AFFECTED_RELATIONS, format_affected
from graph3d.serve import _find_node, _load_graph, _query_graph_text


SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class QueryResponse:
    schema_version: str
    mode: str
    answer: str


@dataclass(frozen=True)
class ExplainResponse:
    schema_version: str
    concept: str
    answer: str


@dataclass(frozen=True)
class PathResponse:
    schema_version: str
    source: str
    target: str
    hops: int
    path: list[str]


@dataclass(frozen=True)
class UpdateResponse:
    schema_version: str
    ok: bool
    message: str


@dataclass(frozen=True)
class AffectedResponse:
    schema_version: str
    query: str
    answer: str


class Graph3dClient:
    """Unified graph3d client for local, CLI, and HTTP targets."""

    def __init__(
        self,
        *,
        mode: str = "local",
        graph: str | Path = Path("graph3d-out") / "graph.json",
        cli_executable: str = "graph3d",
        base_url: str | None = None,
        timeout: float = 30.0,
        api_key: str | None = None,
        max_read_retries: int = 1,
    ) -> None:
        if mode not in {"local", "cli", "http"}:
            raise ValueError("mode must be one of: local, cli, http")
        if mode == "http" and not base_url:
            raise ValueError("base_url is required for mode='http'")
        self.mode = mode
        self.graph = Path(graph)
        self.cli_executable = cli_executable
        self.base_url = base_url.rstrip("/") if base_url else None
        self.timeout = timeout
        self.api_key = api_key
        self.max_read_retries = max(0, int(max_read_retries))

    def query(self, question: str, *, depth: int = 3, mode: str = "bfs") -> QueryResponse:
        if self.mode == "local":
            graph = _load_graph(str(self.graph))
            answer = _query_graph_text(graph, question, mode=mode, depth=depth)
            return QueryResponse(schema_version=SCHEMA_VERSION, mode=mode, answer=answer)
        payload = {"question": question, "depth": depth, "mode": mode}
        raw = self._dispatch("query", payload, idempotent=True)
        if isinstance(raw, dict) and "answer" in raw:
            return QueryResponse(schema_version=raw.get("schema_version", SCHEMA_VERSION), mode=mode, answer=str(raw["answer"]))
        return QueryResponse(schema_version=SCHEMA_VERSION, mode=mode, answer=str(raw))

    def explain(self, concept: str) -> ExplainResponse:
        if self.mode == "local":
            graph = _load_graph(str(self.graph))
            matches = _find_node(graph, concept)
            if not matches:
                answer = f"No node matching '{concept}' found."
            else:
                node_id = matches[0]
                node = graph.nodes[node_id]
                neighbors = [graph.nodes[n].get("label", n) for n in graph.neighbors(node_id)]
                answer = f"{node.get('label', node_id)}\nNeighbors: {', '.join(map(str, neighbors[:20]))}"
            return ExplainResponse(schema_version=SCHEMA_VERSION, concept=concept, answer=answer)
        raw = self._dispatch("explain", {"concept": concept}, idempotent=True)
        if isinstance(raw, dict) and "answer" in raw:
            return ExplainResponse(schema_version=raw.get("schema_version", SCHEMA_VERSION), concept=concept, answer=str(raw["answer"]))
        return ExplainResponse(schema_version=SCHEMA_VERSION, concept=concept, answer=str(raw))

    def path(self, source: str, target: str) -> PathResponse:
        if self.mode == "local":
            graph = _load_graph(str(self.graph))
            src = self._resolve_label(graph, source)
            dst = self._resolve_label(graph, target)
            if src is None or dst is None:
                raise ValueError(f"Could not resolve source/target in graph: {source!r}, {target!r}")
            node_ids = nx.shortest_path(graph.to_undirected(), source=src, target=dst)
            labels = [str(graph.nodes[n].get("label", n)) for n in node_ids]
            return PathResponse(
                schema_version=SCHEMA_VERSION,
                source=source,
                target=target,
                hops=max(0, len(labels) - 1),
                path=labels,
            )
        raw = self._dispatch("path", {"source": source, "target": target}, idempotent=True)
        if isinstance(raw, dict):
            return PathResponse(
                schema_version=raw.get("schema_version", SCHEMA_VERSION),
                source=source,
                target=target,
                hops=int(raw.get("hops", 0)),
                path=[str(item) for item in raw.get("path", [])],
            )
        return PathResponse(schema_version=SCHEMA_VERSION, source=source, target=target, hops=0, path=[str(raw)])

    def update(self, path: str | Path = ".") -> UpdateResponse:
        raw = self._dispatch("update", {"path": str(path)}, idempotent=False)
        if isinstance(raw, dict):
            return UpdateResponse(
                schema_version=raw.get("schema_version", SCHEMA_VERSION),
                ok=bool(raw.get("ok", True)),
                message=str(raw.get("message", "ok")),
            )
        return UpdateResponse(schema_version=SCHEMA_VERSION, ok=True, message=str(raw))

    def affected(
        self,
        query: str,
        *,
        depth: int = 2,
        relations: tuple[str, ...] = DEFAULT_AFFECTED_RELATIONS,
    ) -> AffectedResponse:
        if self.mode == "local":
            graph = _load_graph(str(self.graph))
            answer = format_affected(graph, query, depth=depth, relations=relations)
            return AffectedResponse(schema_version=SCHEMA_VERSION, query=query, answer=answer)
        raw = self._dispatch(
            "affected",
            {"query": query, "depth": depth, "relations": list(relations)},
            idempotent=True,
        )
        if isinstance(raw, dict) and "answer" in raw:
            return AffectedResponse(schema_version=raw.get("schema_version", SCHEMA_VERSION), query=query, answer=str(raw["answer"]))
        return AffectedResponse(schema_version=SCHEMA_VERSION, query=query, answer=str(raw))

    def _dispatch(self, operation: str, payload: dict[str, Any], *, idempotent: bool) -> Any:
        if self.mode == "cli":
            return self._dispatch_cli(operation, payload)
        if self.mode == "http":
            return self._dispatch_http(operation, payload, idempotent=idempotent)
        raise RuntimeError(f"Unsupported mode: {self.mode}")

    def _dispatch_cli(self, operation: str, payload: dict[str, Any]) -> Any:
        command = [self.cli_executable]
        if operation == "query":
            command += ["query", payload["question"], "--depth", str(payload.get("depth", 3))]
        elif operation == "explain":
            command += ["explain", payload["concept"]]
        elif operation == "path":
            command += ["path", payload["source"], payload["target"]]
        elif operation == "update":
            command += ["update", payload.get("path", ".")]
        elif operation == "affected":
            command += ["affected", payload["query"], "--depth", str(payload.get("depth", 2))]
        else:
            raise ValueError(f"Unknown operation: {operation}")
        command += ["--graph", str(self.graph), "--format", "json"]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return self._coerce_json(result.stdout.strip())

    def _dispatch_http(self, operation: str, payload: dict[str, Any], *, idempotent: bool) -> Any:
        if not self.base_url:
            raise RuntimeError("base_url is required for HTTP mode")
        if operation == "query":
            method = "POST"
            path = "/graphs/{graphId}/query"
        elif operation == "explain":
            method = "POST"
            path = "/graphs/{graphId}/explain"
        elif operation == "path":
            method = "POST"
            path = "/graphs/{graphId}/path"
        elif operation == "affected":
            method = "POST"
            path = "/graphs/{graphId}/affected"
        elif operation == "update":
            method = "POST"
            path = "/graphs/update"
        else:
            raise ValueError(f"Unknown operation: {operation}")
        graph_id = payload.pop("graph_id", "local")
        endpoint = path.format(graphId=graph_id)
        request_payload = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"******"
        attempts = self.max_read_retries + 1 if idempotent else 1
        last_error: Exception | None = None
        for _ in range(attempts):
            request = urlrequest.Request(
                f"{self.base_url}{endpoint}",
                data=request_payload,
                method=method,
                headers=headers,
            )
            try:
                with urlrequest.urlopen(request, timeout=self.timeout) as response:
                    return self._coerce_json(response.read().decode("utf-8"))
            except (urlerror.URLError, TimeoutError) as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("HTTP dispatch failed unexpectedly")

    @staticmethod
    def _coerce_json(payload: str) -> Any:
        if not payload:
            return {}
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return payload

    @staticmethod
    def _resolve_label(graph: nx.Graph, query: str) -> str | None:
        if query in graph:
            return query
        lowered = query.casefold()
        for node_id, data in graph.nodes(data=True):
            label = str(data.get("label", "")).casefold()
            if label == lowered or lowered in label:
                return str(node_id)
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "graph": str(self.graph),
            "cli_executable": self.cli_executable,
            "base_url": self.base_url,
            "timeout": self.timeout,
            "schema_version": SCHEMA_VERSION,
        }

    @staticmethod
    def response_to_dict(response: QueryResponse | ExplainResponse | PathResponse | UpdateResponse | AffectedResponse) -> dict[str, Any]:
        return asdict(response)

