from __future__ import annotations

import json
from pathlib import Path

from graph3d.mcp_contracts import REQUIRED_PROMPTS, REQUIRED_RESOURCES, REQUIRED_TOOLS, SCHEMA_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_required_mcp_contract_catalog_is_present():
    tool_names = {tool.name for tool in REQUIRED_TOOLS}
    resource_uris = {resource.uri for resource in REQUIRED_RESOURCES}
    prompt_names = {prompt.name for prompt in REQUIRED_PROMPTS}

    assert {
        "graph3d_query",
        "graph3d_explain",
        "graph3d_path",
        "graph3d_affected",
        "graph3d_update",
        "graph3d_validate",
        "graph3d_export",
        "graph3d_prs",
    }.issubset(tool_names)
    assert {
        "graph://summary",
        "graph://report",
        "graph://communities",
        "graph://nodes/{id}",
        "graph://paths/{source}/{target}",
        "graph://schema",
    }.issubset(resource_uris)
    assert {
        "architecture_review",
        "implementation_map",
        "risk_review",
        "test_plan_from_graph",
    }.issubset(prompt_names)


def test_schema_files_exist_and_are_versioned():
    schema_paths = [
        REPO_ROOT / "schemas" / "extraction-v1.schema.json",
        REPO_ROOT / "schemas" / "graph-v1.schema.json",
        REPO_ROOT / "schemas" / "cli-envelope-v1.schema.json",
        REPO_ROOT / "schemas" / "mcp-contract-v1.schema.json",
    ]
    for path in schema_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_openapi_contract_has_required_paths():
    payload = json.loads(
        (REPO_ROOT / "schemas" / "openapi" / "graph3d-apim.v1.json").read_text(encoding="utf-8")
    )
    assert payload["openapi"] == "3.1.0"
    assert payload["info"]["version"] == SCHEMA_VERSION
    required_paths = {
        "/graphs/build",
        "/graphs/update",
        "/graphs/{graphId}",
        "/graphs/{graphId}/report",
        "/graphs/{graphId}/query",
        "/graphs/{graphId}/path",
        "/graphs/{graphId}/explain",
        "/graphs/{graphId}/affected",
        "/graphs/{graphId}/exports",
    }
    assert required_paths.issubset(set(payload["paths"]))
