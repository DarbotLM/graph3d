# Spec: graph3d platform package buildout

## Status

Draft for implementation issue.

## Problem

graph3d now has a Python package, Python CLI, npm/npx launcher, MCP server
capabilities, schema-path extraction, and multiple assistant skill installers.
Those surfaces are useful, but they are still packaged as one broad tool. The
next phase needs explicit product boundaries:

- `graph3d-cli` for local and CI command-line workflows.
- `graph3d-mcp` for host-integrated graph tools and resources.
- `graph3d-apim` for authenticated hosted API access through Azure API
  Management.
- SDKs that let Python and TypeScript callers use the same contracts without
  shelling out unless they choose to.

## Goals

1. Keep `graph3d` working as the umbrella install and CLI command.
2. Define stable contracts for graph JSON, extraction JSON, CLI JSON output,
   MCP tools/resources, OpenAPI operations, and SDK clients.
3. Split implementation into package-oriented workstreams without fragmenting
   user experience.
4. Make local, MCP, and hosted API workflows share the same command semantics.
5. Provide production-ready CI validation for Python, npm, npx, MCP, OpenAPI,
   and SDK surfaces.

## Non-goals

- Do not remove or rename the existing `graph3d` Python package.
- Do not require cloud services for local graph extraction or query.
- Do not make LLM-backed semantic extraction mandatory for code-only corpora.
- Do not introduce a hosted service dependency into the default CLI path.

## Current baseline

| Area | Baseline |
|------|----------|
| Python package | `graph3d` with console script `graph3d`. |
| npm package | `graph3d` launcher that delegates to the Python CLI. |
| CLI helpers | `graph3d.cli_api` starts normalizing profile parsing and CLI/API boundaries. |
| Extractor extensibility | `graph3d.extractor_registry` starts formalizing extractor registration. |
| MCP | `graph3d.serve` provides a local MCP stdio server path. |
| Graph artifacts | `graph3d-out/graph.json`, `GRAPH_REPORT.md`, and optional `graph.html`. |
| Validation | pytest, ruff, npm package validation, npx tarball smoke, and GitHub Actions. |

## Target package surfaces

### graph3d-cli

`graph3d-cli` is the hardened command surface for humans, CI, and automation.
It should remain installable through Python and callable through npm/npx.

Required capabilities:

- Command groups: `build`, `update`, `query`, `path`, `explain`, `export`,
  `validate`, `watch`, `install`, `serve`, `prs`.
- Global flags: `--graph`, `--out`, `--profile`, `--format text|json`,
  `--quiet`, `--verbose`, `--no-viz`.
- Stable JSON outputs for automation.
- Documented exit codes.
- Shell completions for PowerShell, Bash, and Zsh.
- Offline-safe behavior for code-only corpora.
- Config file discovery for repository and user scopes.
- Plugin hooks for custom extractors and exporters.
- CI examples for GitHub Actions and Azure DevOps.

Acceptance criteria:

- `graph3d --help` shows command groups and global flags.
- Every automation command supports `--format json`.
- CLI JSON contracts are covered by schema tests.
- npm `npx graph3d ...` and Python `graph3d ...` produce equivalent results.
- Backward-compatible command aliases continue to work.

### graph3d-mcp

`graph3d-mcp` is the MCP-first package for assistant hosts. It should expose
safe, query-oriented tools over local graph artifacts without requiring raw file
access for common architecture questions.

Required resources:

- `graph://summary`
- `graph://report`
- `graph://communities`
- `graph://nodes/{id}`
- `graph://paths/{source}/{target}`
- `graph://schema`

Required tools:

- `graph3d_query`
- `graph3d_explain`
- `graph3d_path`
- `graph3d_affected`
- `graph3d_update`
- `graph3d_validate`
- `graph3d_export`
- `graph3d_prs`

Required prompts:

- `architecture_review`
- `implementation_map`
- `risk_review`
- `test_plan_from_graph`

Acceptance criteria:

- MCP tool schemas are generated from a single source of truth.
- MCP server has deterministic error shapes and no broad silent failures.
- MCP server rejects graph paths outside `graph3d-out/`.
- MCP Inspector smoke tests are documented and automated where possible.
- Host instructions prefer graph queries before raw-file reads for codebase
  questions.

### graph3d-apim

`graph3d-apim` is the production API front door for hosted graph workflows. It
should provide an APIM-ready OpenAPI contract and policy templates while keeping
local graph3d behavior unchanged.

Required API operations:

- `POST /graphs/build`
- `POST /graphs/update`
- `GET /graphs/{graphId}`
- `GET /graphs/{graphId}/report`
- `POST /graphs/{graphId}/query`
- `POST /graphs/{graphId}/path`
- `POST /graphs/{graphId}/explain`
- `POST /graphs/{graphId}/affected`
- `POST /graphs/{graphId}/exports`

Required APIM assets:

- OpenAPI 3.1 document.
- APIM policy templates for auth, rate limits, request body limits, response
  shaping, and correlation IDs.
- Deployment examples for Azure API Management plus a Python API backend.
- Tenant and repository isolation guidance.
- Observability fields: request ID, graph ID, repo ID, duration, token counts,
  extractor profile, and cache hit rate.

Acceptance criteria:

- OpenAPI validates in CI.
- SDK clients can be generated from the OpenAPI document.
- Hosted API never exposes raw secrets or local filesystem paths.
- Graph build/update endpoints have explicit quotas and async job semantics.
- APIM policies are tested with representative requests.

### graph3d-sdk

The SDK should provide typed clients over local CLI, MCP, and hosted APIM
targets.

Python SDK:

- Importable client: `from graph3d.sdk import Graph3dClient`.
- Local mode that calls Python functions directly.
- CLI mode that shells out to `graph3d --format json`.
- HTTP mode that calls `graph3d-apim`.
- Pydantic or dataclass models for graph, node, edge, query, path, and report
  responses.

TypeScript SDK:

- Package: `graph3d-sdk`.
- Local mode through spawned `graph3d` CLI.
- HTTP mode through generated OpenAPI client.
- Types generated from shared JSON schemas.

Acceptance criteria:

- Python and TypeScript clients share schema fixtures.
- SDK clients support retries only for idempotent read operations.
- SDK examples cover query, explain, path, and update.
- SDK docs clearly distinguish local, MCP, and APIM modes.

## Shared contract work

Create versioned schemas for:

- Extraction JSON.
- Graph node-link JSON.
- CLI response envelopes.
- MCP tool inputs and outputs.
- OpenAPI request and response bodies.
- SDK model fixtures.

Contract rules:

- Use additive changes for minor versions.
- Keep deprecated fields for at least one minor release.
- Validate examples in CI.
- Include `schema_version` in machine-readable outputs.

## Implementation plan

### Milestone 1: Contract foundation

- Add `schemas/` for extraction, graph, CLI, MCP, and OpenAPI contracts.
- Add schema validation tests.
- Add CLI `--format json` response envelope for core commands.
- Document exit codes and error envelopes.

### Milestone 2: graph3d-cli

- Split CLI parser helpers into a package-owned command layer.
- Add command group help and completions.
- Add config discovery and profile documentation.
- Harden npm/npx parity tests.

### Milestone 3: graph3d-mcp

- Define MCP tool/resource schema source of truth.
- Add MCP Inspector smoke instructions.
- Add tool-level tests for query, explain, path, affected, update, and validate.
- Publish MCP-focused docs and host configuration examples.

### Milestone 4: graph3d-apim

- Add OpenAPI contract and API backend skeleton.
- Add APIM policy templates.
- Add deployment documentation for dev/test/prod.
- Add CI validation for OpenAPI and generated clients.

### Milestone 5: graph3d-sdk

- Add Python SDK client.
- Add TypeScript SDK package.
- Add generated model fixtures.
- Add examples and end-to-end tests across local and HTTP modes.

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Package split breaks existing users | Keep `graph3d` as umbrella package and make new packages additive. |
| CLI, MCP, and APIM drift | Generate schemas from shared contracts and validate examples in CI. |
| Hosted API exposes local paths or secrets | Sanitize metadata, avoid raw env capture, and add APIM response shaping policies. |
| npm launcher creates surprising Python environments | Keep `GRAPH3D_PYTHON` override, document managed venv path, and validate npx tarballs. |
| MCP tools become too broad | Keep graph paths constrained to `graph3d-out/` and return bounded responses. |

## Issue checklist

- [ ] Define shared schemas and versioning policy.
- [ ] Build `graph3d-cli` package boundary and JSON output mode.
- [ ] Build `graph3d-mcp` package boundary and MCP tool/resource catalog.
- [ ] Build `graph3d-apim` OpenAPI contract and APIM policy templates.
- [ ] Build Python and TypeScript SDK clients.
- [ ] Add CI for schema, OpenAPI, npm/npx, MCP smoke, and SDK fixtures.
- [ ] Update README, architecture, SDK docs, and examples.

