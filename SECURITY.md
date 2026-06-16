# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.8.x   | Yes       |
| < 0.8   | No        |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report security issues via GitHub's private vulnerability reporting, or email the maintainer directly. Please include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

We will acknowledge receipt within 48 hours and aim to release a fix within 7 days for critical issues.

## Security Model

graph3d is a **local development tool**. It runs as a Claude Code skill and optionally as a local MCP stdio server. Network calls depend on which commands and extras are in use — see the Optional network calls section below for the full list.

### Threat Surface

| Vector | Mitigation |
|--------|-----------|
| SSRF via URL fetch | `security.validate_url()` allows only `http` and `https` schemes, blocks private/loopback/link-local IPs, and blocks cloud metadata endpoints. Redirect targets are re-validated. All fetch paths including tweet oEmbed go through `safe_fetch()`. |
| Oversized downloads | `safe_fetch()` streams responses and aborts at 50 MB. `safe_fetch_text()` aborts at 10 MB. |
| Non-2xx HTTP responses | `safe_fetch()` raises `HTTPError` on non-2xx status codes - error pages are not silently treated as content. |
| Path traversal in MCP server | `security.validate_graph_path()` resolves paths and requires them to be inside `graph3d-out/`. Also requires the `graph3d-out/` directory to exist. |
| XSS in graph HTML output | `security.sanitize_label()` strips control characters and caps at 256 chars. Export callers (e.g. `export.py`) then apply `html.escape()` before pyvis embeds labels in HTML. The two steps are intentionally separate: `sanitize_label` is safe for JSON/plain-text; HTML contexts require the additional escape at the call site. |
| Prompt injection via node labels | `sanitize_label()` also applied to MCP text output - node labels from user-controlled source files cannot break the text format returned to agents. |
| YAML frontmatter injection | `_yaml_str()` escapes backslashes, double quotes, and newlines before embedding user-controlled strings (webpage titles, query questions) in YAML frontmatter. |
| Encoding crashes on source files | All tree-sitter byte slices decoded with `errors="replace"` - non-UTF-8 source files degrade gracefully instead of crashing extraction. |
| Symlink traversal | `os.walk(..., followlinks=False)` is explicit throughout `detect.py`. |
| Corrupted graph.json | `_load_graph()` in `serve.py` wraps `json.JSONDecodeError` and prints a clear recovery message instead of crashing. |

### What graph3d does NOT do

- Does not run a network listener (MCP server communicates over stdio only)
- Does not execute code from source files (tree-sitter parses ASTs - no eval/exec)
- Does not use `shell=True` in any subprocess call
- Does not store credentials or API keys

### Optional network calls

The following operations make outbound network calls. All other operations (AST extraction, clustering, MCP queries, watch mode) are local.

| Operation | Network target |
|-----------|---------------|
| `ingest` / `add` subcommand | URLs explicitly provided by the user; goes through `safe_fetch()` |
| Headless `extract` for docs, PDFs, and images | LLM provider API (Anthropic, Gemini, OpenAI, DeepSeek, Moonshot/Kimi, or AWS Bedrock depending on configured backend) |
| `extract --google-workspace` | Google Drive API via the `gws` CLI (opt-in, requires explicit auth) |
| `extract` with `[video]` extra — YouTube or remote video URLs | yt-dlp downloads from the video host; transcription is then done locally with faster-whisper |
| `prs` command | GitHub API via the `gh` CLI (requires `gh auth login`) |
| `prs --triage` | GitHub API via `gh` plus the configured LLM provider for ranking |
| PDF extraction | Local files only (pypdf makes no network calls) |
| Watch mode | Local filesystem events only (watchdog makes no network calls) |
