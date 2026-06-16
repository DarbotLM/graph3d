# graph3d SDK and integration guide

graph3d is currently distributed as a Python package, a Python CLI, and an npm/npx
launcher for the Python CLI. The supported programmatic surface is the Python
module API; the npm package is a launcher, not a JavaScript SDK.

This guide documents the stable integration points available today and the
planned package split for `graph3d-cli`, `graph3d-mcp`, and `graph3d-apim`.

## Current supported surfaces

| Surface | Package | Purpose |
|---------|---------|---------|
| Python library | `graph3d` on PyPI | Import graph extraction, build, clustering, reporting, validation, and export helpers. |
| Python CLI | `graph3d` console script | Run install, extract, update, query, explain, path, export, watch, and MCP server commands. |
| npm/npx launcher | `graph3d` on npm | Run the Python CLI from Node-based toolchains and `npx` workflows. |
| MCP stdio server | `graph3d[mcp]` extra | Serve graph query tools to MCP hosts. |

## Python SDK examples

### Unified client API

```python
from graph3d.sdk import Graph3dClient

client = Graph3dClient(mode="local", graph="graph3d-out/graph.json")
result = client.query("Where is extraction implemented?")
print(result.answer)
```

### Detect a corpus

```python
from pathlib import Path
from graph3d.detect import detect

summary = detect(Path("."))
print(summary["total_files"], summary["total_words"])
```

### Extract, build, cluster, and report

```python
from pathlib import Path
from graph3d.extract import collect_files, extract
from graph3d.build import build_from_json
from graph3d.cluster import cluster
from graph3d.analyze import god_nodes, surprising_connections
from graph3d.report import generate

files = collect_files(Path("graph3d"))
extraction = extract(files)
graph = build_from_json(extraction)
communities = cluster(graph)
gods = god_nodes(graph)
surprises = surprising_connections(graph, communities)
report = generate(graph, communities, {}, {}, gods, surprises, extraction)
```

### Validate extraction JSON

```python
from graph3d.validate import validate_extraction

errors = validate_extraction(extraction)
if errors:
    raise ValueError("\n".join(errors))
```

### Register a custom extractor

`graph3d.extractor_registry.ExtractorRegistry` is the forward-compatible entry
point for suffix and filename-predicate extractor registration. Existing
internal callers still use the legacy dispatch table, but new integrations
should prefer the registry surface so route precedence is explicit.

```python
from pathlib import Path
from graph3d.extractor_registry import ExtractorRegistry

def extract_acme(path: Path) -> dict:
    return {"nodes": [], "edges": []}

registry = ExtractorRegistry()
registry.register_suffix(".acme", extract_acme)
assert registry.lookup(Path("sample.acme")) is extract_acme
```

## CLI integration

Use the Python CLI directly when Python is already the runtime boundary:

```bash
uvx graph3d --help
graph3d query "How does extraction flow into reporting?"
graph3d update .
```

Use the npm launcher when the caller is Node-based or wants a one-shot `npx`
workflow:

```bash
npx graph3d --help
npx graph3d query "What are the core abstractions?"
```

The npm launcher requires Python 3.10 or newer. If the selected Python does not
already have the matching `graph3d` package installed, it creates a managed
virtual environment under `~/.graph3d/npm-python/<version>` and installs the
bundled Python package there. Set `GRAPH3D_PYTHON=/path/to/python` to force a
specific interpreter.

## Planned package split

The next packaging phase should split the current monolithic distribution into
clear product surfaces while keeping `graph3d` as the umbrella package:

| Planned package | Runtime | Responsibility |
|-----------------|---------|----------------|
| `graph3d-cli` | Python plus npm launcher | Hardened command surface, JSON output contracts, profiles, plugins, install/update lifecycle, and shell completion. |
| `graph3d-mcp` | Python MCP server | Stable MCP tools/resources/prompts for graph query, path, explain, affected files, update, validation, and report access. |
| `graph3d-apim` | Azure API Management plus hosted API | Authenticated HTTP API, OpenAPI contract, rate limits, tenant isolation, and production deployment policy templates. |
| `graph3d-sdk` | Python and TypeScript | Typed clients for local CLI, MCP, and hosted APIM endpoints. |

See `docs/specs/graph3d-platform-buildout.md` for the buildout spec.

## Compatibility rules

- Preserve the existing `graph3d` CLI command and Python imports.
- Keep `graph3d` as the umbrella package for existing users.
- Add new packages as narrower entry points rather than breaking current installs.
- Version Python, npm, MCP, OpenAPI, and SDK contracts together.
- Treat graph JSON, extraction JSON, and MCP tool schemas as public contracts.
