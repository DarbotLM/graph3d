"""Versioned MCP contract catalog for graph3d."""
from __future__ import annotations

from dataclasses import dataclass


SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class McpResourceContract:
    uri: str
    name: str
    description: str
    mime_type: str


@dataclass(frozen=True)
class McpToolContract:
    name: str
    description: str
    input_schema: dict


@dataclass(frozen=True)
class McpPromptContract:
    name: str
    description: str


REQUIRED_RESOURCES: tuple[McpResourceContract, ...] = (
    McpResourceContract("graph://summary", "Graph Summary", "Summary statistics for graph artifacts.", "text/plain"),
    McpResourceContract("graph://report", "Graph Report", "Full GRAPH_REPORT.md content.", "text/markdown"),
    McpResourceContract("graph://communities", "Graph Communities", "Community overview extracted from graph nodes.", "text/plain"),
    McpResourceContract("graph://nodes/{id}", "Graph Node Lookup", "Lookup a node by label or identifier.", "text/plain"),
    McpResourceContract("graph://paths/{source}/{target}", "Graph Path Lookup", "Find shortest path between two graph nodes.", "text/plain"),
    McpResourceContract("graph://schema", "Graph Contract Schema", "MCP tool/resource/prompt contract metadata.", "application/json"),
)


REQUIRED_TOOLS: tuple[McpToolContract, ...] = (
    McpToolContract(
        "graph3d_query",
        "Search graph context by question text.",
        {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "mode": {"type": "string", "enum": ["bfs", "dfs"], "default": "bfs"},
                "depth": {"type": "integer", "default": 3},
                "token_budget": {"type": "integer", "default": 2000},
                "context_filter": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["question"],
        },
    ),
    McpToolContract(
        "graph3d_explain",
        "Explain a graph concept by label.",
        {
            "type": "object",
            "properties": {"concept": {"type": "string"}},
            "required": ["concept"],
        },
    ),
    McpToolContract(
        "graph3d_path",
        "Find shortest path between two concepts.",
        {
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "target": {"type": "string"},
                "max_hops": {"type": "integer", "default": 8},
            },
            "required": ["source", "target"],
        },
    ),
    McpToolContract(
        "graph3d_affected",
        "Find impacted nodes for a changed concept.",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "depth": {"type": "integer", "default": 2},
                "relations": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["query"],
        },
    ),
    McpToolContract(
        "graph3d_update",
        "Refresh graph artifacts for a local workspace path.",
        {"type": "object", "properties": {"path": {"type": "string", "default": "."}}},
    ),
    McpToolContract(
        "graph3d_validate",
        "Validate graph artifact shape and schema metadata.",
        {"type": "object", "properties": {}},
    ),
    McpToolContract(
        "graph3d_export",
        "Export graph artifact content.",
        {
            "type": "object",
            "properties": {"format": {"type": "string", "enum": ["report", "stats"], "default": "report"}},
        },
    ),
    McpToolContract(
        "graph3d_prs",
        "List actionable pull requests with graph impact.",
        {"type": "object", "properties": {"repo": {"type": "string"}, "base": {"type": "string"}}},
    ),
)


REQUIRED_PROMPTS: tuple[McpPromptContract, ...] = (
    McpPromptContract("architecture_review", "Review architecture from graph summaries and communities."),
    McpPromptContract("implementation_map", "Map where an implementation concern lives in graph artifacts."),
    McpPromptContract("risk_review", "Assess merge/change risk from graph neighborhoods."),
    McpPromptContract("test_plan_from_graph", "Generate a test plan from affected graph regions."),
)
