<p align="center">
  <a href="https://github.com/DarbotLM/graph3d"><img src="https://raw.githubusercontent.com/DarbotLM/graph3d/v4/docs/logo-text.svg" width="260" height="64" alt="Graph3d"/></a>
</p>

<p align="center">
  <strong>DarbotLM / graph3d</strong> — DarbotLabs fork of <a href="https://github.com/DarbotLM/graph3d">DarbotLM/graph3d</a>
</p>

<p align="center">
  🇺🇸 <a href="README.md">English</a> | 🇨🇳 <a href="docs/translations/README.zh-CN.md">简体中文</a> | 🇯🇵 <a href="docs/translations/README.ja-JP.md">日本語</a> | 🇰🇷 <a href="docs/translations/README.ko-KR.md">한국어</a> | 🇩🇪 <a href="docs/translations/README.de-DE.md">Deutsch</a> | 🇫🇷 <a href="docs/translations/README.fr-FR.md">Français</a> | 🇪🇸 <a href="docs/translations/README.es-ES.md">Español</a> | 🇮🇳 <a href="docs/translations/README.hi-IN.md">हिन्दी</a> | 🇧🇷 <a href="docs/translations/README.pt-BR.md">Português</a> | 🇷🇺 <a href="docs/translations/README.ru-RU.md">Русский</a> | 🇸🇦 <a href="docs/translations/README.ar-SA.md">العربية</a> | 🇮🇹 <a href="docs/translations/README.it-IT.md">Italiano</a> | 🇵🇱 <a href="docs/translations/README.pl-PL.md">Polski</a> | 🇳🇱 <a href="docs/translations/README.nl-NL.md">Nederlands</a> | 🇹🇷 <a href="docs/translations/README.tr-TR.md">Türkçe</a> | 🇺🇦 <a href="docs/translations/README.uk-UA.md">Українська</a> | 🇻🇳 <a href="docs/translations/README.vi-VN.md">Tiếng Việt</a> | 🇮🇩 <a href="docs/translations/README.id-ID.md">Bahasa Indonesia</a> | 🇸🇪 <a href="docs/translations/README.sv-SE.md">Svenska</a> | 🇬🇷 <a href="docs/translations/README.el-GR.md">Ελληνικά</a> | 🇷🇴 <a href="docs/translations/README.ro-RO.md">Română</a> | 🇨🇿 <a href="docs/translations/README.cs-CZ.md">Čeština</a> | 🇫🇮 <a href="docs/translations/README.fi-FI.md">Suomi</a> | 🇩🇰 <a href="docs/translations/README.da-DK.md">Dansk</a> | 🇳🇴 <a href="docs/translations/README.no-NO.md">Norsk</a> | 🇭🇺 <a href="docs/translations/README.hu-HU.md">Magyar</a> | 🇹🇭 <a href="docs/translations/README.th-TH.md">ภาษาไทย</a> | 🇺🇿 <a href="docs/translations/README.uz-UZ.md">Oʻzbekcha</a> | 🇹🇼 <a href="docs/translations/README.zh-TW.md">繁體中文</a> | 🇵🇭 <a href="docs/translations/README.fil-PH.md">Filipino</a>
</p>

<p align="center">
  <a href="https://github.com/DarbotLM/graph3d/actions/workflows/ci.yml"><img src="https://github.com/DarbotLM/graph3d/actions/workflows/ci.yml/badge.svg" alt="CI"/></a>
  <a href="https://pypi.org/project/graph3d/"><img src="https://img.shields.io/pypi/v/graph3d" alt="PyPI"/></a>
  <a href="https://clickpy.clickhouse.com/dashboard/graph3d"><img src="https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fsql-clickhouse.clickhouse.com%2F%3Fquery%3DSELECT%2520concat%2528toString%2528round%2528sum%2528count%2529%2F1000%2529%2529%2C%2520%2527k%2527%2529%2520AS%2520c%2520FROM%2520pypi.pypi_downloads%2520WHERE%2520project%253D%2527graph3d%2527%2520FORMAT%2520JSON%26user%3Ddemo&query=%24.data%5B0%5D.c&label=downloads&color=blue" alt="Downloads"/></a>
  <a href="https://github.com/DarbotLM"><img src="https://img.shields.io/badge/org-DarbotLM-0077B5?logo=github" alt="DarbotLM"/></a>
</p>

<p align="center">
  <a href="https://star-history.com/#DarbotLM/graph3d&Date">
    <img src="https://api.star-history.com/svg?repos=DarbotLM/graph3d&type=Date" alt="Star History Chart" width="370"/>
  </a>
</p>

Type `/graph3d` in your AI coding assistant and it maps your entire project — code, docs, PDFs, images, videos — into a knowledge graph you can query instead of grepping through files.

Works in Claude Code, Codex, OpenCode, Cursor, Gemini CLI, GitHub Copilot CLI, VS Code Copilot Chat, Aider, Amp, OpenClaw, Factory Droid, Trae, Hermes, Kimi Code, Kiro, Pi, and Google Antigravity.

```
/graph3d .
```

That's it. You get three files:

```
graph3d-out/
├── graph.html       open in any browser — click nodes, filter, search
├── GRAPH_REPORT.md  the highlights: key concepts, surprising connections, suggested questions
└── graph.json       the full graph — query it anytime without re-reading your files
```

For a readable architecture page with Mermaid call-flow diagrams, run:

```bash
graph3d export callflow-html
```

---

## Prerequisites

| Requirement | Minimum | Check | Install |
|---|---|---|---|
| Python | 3.10+ | `python --version` | [python.org](https://www.python.org/downloads/) |
| uv *(recommended)* | any | `uv --version` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| pipx *(alternative)* | any | `pipx --version` | `pip install pipx` |

**macOS quick install (Homebrew):**
```bash
brew install python@3.12 uv
```

**Windows quick install:**
```powershell
winget install astral-sh.uv
```

**Ubuntu/Debian:**
```bash
sudo apt install python3.12 python3-pip pipx
# or install uv:
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Install

> **Official package:** The PyPI package is `graph3d` (double-y). Other `graph3d*` packages on PyPI are not affiliated. The CLI command is still `graph3d`.

**Step 1 — install the package:**

```bash
# Recommended (uv puts graph3d on PATH automatically):
uv tool install graph3d

# Alternatives:
pipx install graph3d
pip install graph3d  # may need PATH setup — see note below
```

**Step 2 — register the skill with your AI assistant:**

```bash
graph3d install
```

That's it. Open your AI assistant and type `/graph3d .`

To install the assistant skill into the current repository instead of your user
profile, add `--project`:

```bash
graph3d install --project
graph3d install --project --platform codex
```

Project-scoped installs write under the current directory, for example
`.claude/skills/graph3d/SKILL.md` or `.agents/skills/graph3d/SKILL.md`, and
print a `git add` hint for files that can be committed.
Per-platform commands that support project-scoped installs accept the same flag,
for example `graph3d claude install --project` or `graph3d codex install --project`.

> **PowerShell note:** Use `graph3d .` not `/graph3d .` — the leading slash is a path separator in PowerShell.

> **`graph3d: command not found`?** Use `uv tool install graph3d` or `pipx install graph3d` — both put the CLI on PATH automatically. With plain `pip`, add `~/.local/bin` (Linux) or `~/Library/Python/3.x/bin` (Mac) to your PATH, or run `python -m graph3d`.

> **Avoid `pip install` on Mac/Windows** if possible. The skill resolves Python at runtime from `graph3d-out/.graph3d_python`; if that points to a different environment than where `pip` installed the package, you'll get `ModuleNotFoundError: No module named 'graph3d'`. `uv tool install` and `pipx install` isolate the package in their own env and avoid this entirely.

### Pick your platform

| Platform | Install command |
|----------|----------------|
| Claude Code (Linux/Mac) | `graph3d install` |
| Claude Code (Windows) | `graph3d install --platform windows` |
| Codex | `graph3d install --platform codex` |
| OpenCode | `graph3d install --platform opencode` |
| GitHub Copilot CLI | `graph3d install --platform copilot` |
| VS Code Copilot Chat | `graph3d vscode install` |
| Aider | `graph3d install --platform aider` |
| OpenClaw | `graph3d install --platform claw` |
| Factory Droid | `graph3d install --platform droid` |
| Trae | `graph3d install --platform trae` |
| Trae CN | `graph3d install --platform trae-cn` |
| Gemini CLI | `graph3d install --platform gemini` |
| Hermes | `graph3d install --platform hermes` |
| Kimi Code | `graph3d install --platform kimi` |
| Amp | `graph3d amp install` |
| Kiro IDE/CLI | `graph3d kiro install` |
| Pi coding agent | `graph3d install --platform pi` |
| Cursor | `graph3d cursor install` |
| Devin CLI | `graph3d devin install` |
| Google Antigravity | `graph3d antigravity install` |

> Codex users: also add `multi_agent = true` under `[features]` in `~/.codex/config.toml`.
> Codex uses `$graph3d` instead of `/graph3d`.

### Optional extras

Install only what you need:

| Extra | What it adds | Install |
|---|---|---|
| `pdf` | PDF extraction | `pip install "graph3d[pdf]"` |
| `office` | `.docx` and `.xlsx` support | `pip install "graph3d[office]"` |
| `google` | Google Sheets rendering | `pip install "graph3d[google]"` |
| `video` | Video/audio transcription (faster-whisper + yt-dlp) | `pip install "graph3d[video]"` |
| `mcp` | MCP stdio server | `pip install "graph3d[mcp]"` |
| `neo4j` | Neo4j push support | `pip install "graph3d[neo4j]"` |
| `svg` | SVG graph export | `pip install "graph3d[svg]"` |
| `leiden` | Leiden community detection (Python < 3.13 only) | `pip install "graph3d[leiden]"` |
| `ollama` | Ollama local inference | `pip install "graph3d[ollama]"` |
| `openai` | OpenAI / OpenAI-compatible APIs | `pip install "graph3d[openai]"` |
| `gemini` | Google Gemini API | `pip install "graph3d[gemini]"` |
| `bedrock` | AWS Bedrock (uses IAM, no API key) | `pip install "graph3d[bedrock]"` |
| `sql` | SQL schema extraction | `pip install "graph3d[sql]"` |
| `chinese` | Chinese query segmentation (jieba) | `pip install "graph3d[chinese]"` |
| `all` | Everything above | `pip install "graph3d[all]"` |

---

## Make your assistant always use the graph

Run this once in your project after building a graph:

| Platform | Command |
|----------|---------|
| Claude Code | `graph3d claude install` |
| Codex | `graph3d codex install` |
| OpenCode | `graph3d opencode install` |
| GitHub Copilot CLI | `graph3d copilot install` |
| VS Code Copilot Chat | `graph3d vscode install` |
| Aider | `graph3d aider install` |
| OpenClaw | `graph3d claw install` |
| Factory Droid | `graph3d droid install` |
| Trae | `graph3d trae install` |
| Trae CN | `graph3d trae-cn install` |
| Cursor | `graph3d cursor install` |
| Gemini CLI | `graph3d gemini install` |
| Hermes | `graph3d hermes install` |
| Kimi Code | `graph3d install --platform kimi` |
| Amp | `graph3d amp install` |
| Kiro IDE/CLI | `graph3d kiro install` |
| Pi coding agent | `graph3d pi install` |
| Devin CLI | `graph3d devin install` |
| Google Antigravity | `graph3d antigravity install` |

This writes a small config file that tells your assistant to consult the knowledge graph for codebase questions — preferring scoped queries like `graph3d query "<question>"` over reading the full report or grepping raw files. On platforms that support payload-bearing hooks (Claude Code, Gemini CLI), a hook fires automatically before search-style tool calls and nudges your assistant toward the graph path. On the others (Codex, OpenCode, Cursor, etc.), the persistent instruction files (`AGENTS.md`, `.cursor/rules/`, etc.) provide the same query-first guidance. `GRAPH_REPORT.md` is still available for broad architecture review.

To remove graph3d from all platforms at once: `graph3d uninstall` (add `--purge` to also delete `graph3d-out/`). Or use the per-platform command (e.g. `graph3d claude uninstall`).

---

## What's in the report

- **God nodes** — the most-connected concepts in your project. Everything flows through these.
- **Surprising connections** — links between things that live in different files or modules. Ranked by how unexpected they are.
- **The "why"** — inline comments (`# NOTE:`, `# WHY:`, `# HACK:`), docstrings, and design rationale from docs are extracted as separate nodes linked to the code they explain.
- **Suggested questions** — 4–5 questions the graph is uniquely positioned to answer.
- **Confidence tags** — every inferred relationship is marked `EXTRACTED`, `INFERRED`, or `AMBIGUOUS`. You always know what was found vs guessed.

---

## What files it handles

| Type | Extensions |
|------|-----------|
| Code (33 languages) | `.py .ts .js .jsx .tsx .mjs .go .rs .java .c .cpp .h .hpp .rb .cs .kt .scala .php .swift .lua .luau .zig .ps1 .ex .exs .m .mm .jl .vue .svelte .astro .groovy .gradle .dart .v .sv .svh .sql .f .f90 .f95 .f03 .f08 .pas .pp .dpr .dpk .lpr .inc .dfm .lfm .lpk .sh .bash .json .dm .dme .dmi .dmm .dmf .sln .csproj .fsproj .vbproj .razor .cshtml` |
| MCP configs | `.mcp.json` `mcp.json` `mcp_servers.json` `claude_desktop_config.json` — extracts server nodes, package refs, env var requirements |
| Docs | `.md .mdx .qmd .html .txt .rst .yaml .yml` |
| Office | `.docx .xlsx` (requires `pip install graph3d[office]`) |
| Google Workspace | `.gdoc .gsheet .gslides` (opt-in; requires `gws` auth and `--google-workspace`; Sheets need `pip install graph3d[google]`) |
| PDFs | `.pdf` |
| Images | `.png .jpg .webp .gif` |
| Video / Audio | `.mp4 .mov .mp3 .wav` and more (requires `pip install graph3d[video]`) |
| YouTube / URLs | any video URL (requires `pip install graph3d[video]`) |

Code is extracted locally with no API calls (AST via tree-sitter). Everything else goes through your AI assistant's model API.

Google Drive for desktop `.gdoc`, `.gsheet`, and `.gslides` files are shortcut
pointers, not document content. To include native Google Docs, Sheets, and Slides
in a headless extraction, install and authenticate the
[`gws` CLI](https://github.com/googleworkspace/cli), then run:

```bash
pip install "graph3d[google]"  # needed for Google Sheets table rendering
gws auth login -s drive
graph3d extract ./docs --google-workspace
```

You can also set `GRAPH3D_GOOGLE_WORKSPACE=1`. Graph3d exports shortcuts into
`graph3d-out/converted/` as Markdown sidecars, then extracts those files.

---

## Common commands

```bash
/graph3d .                        # build graph for current folder
/graph3d ./docs --update          # re-extract only changed files
/graph3d . --cluster-only         # rerun clustering without re-extracting
/graph3d . --cluster-only --resolution 1.5      # more granular communities
/graph3d . --cluster-only --exclude-hubs 99     # suppress utility super-hubs from god-node rankings
/graph3d . --no-viz               # skip the HTML, just the report + JSON
/graph3d . --wiki                 # build a markdown wiki from the graph
graph3d export callflow-html      # Mermaid architecture/call-flow HTML (auto-regenerates on every git commit if hook is installed)

/graph3d query "what connects auth to the database?"
/graph3d path "UserService" "DatabasePool"
/graph3d explain "RateLimiter"

/graph3d add https://arxiv.org/abs/1706.03762   # fetch a paper and add it
/graph3d add <youtube-url>                       # transcribe and add a video

graph3d hook install              # auto-rebuild on git commit
graph3d merge-graphs a.json b.json              # combine two graphs

graph3d prs                       # PR dashboard: CI state, review status, worktree mapping
graph3d prs 42                    # deep dive on PR #42 with graph impact
graph3d prs --triage              # AI ranks your review queue (uses whatever backend is configured)
graph3d prs --conflicts           # PRs sharing graph communities — merge-order risk
```

See the [full command reference](#full-command-reference) below.

---

## Ignoring files

Create a `.graph3dignore` in your project root — same syntax as `.gitignore`, including `!` negation:

```
# .graph3dignore
node_modules/
dist/
*.generated.py

# only index src/, ignore everything else
*
!src/
!src/**
```

---

## Team setup

`graph3d-out/` is meant to be committed to git so everyone on the team starts with a map.

**Recommended `.gitignore` additions:**
```
graph3d-out/manifest.json    # mtime-based, breaks after git clone
graph3d-out/cost.json        # local only
# graph3d-out/cache/         # optional: commit for speed, skip to keep repo small
```

**Workflow:**
1. One person runs `/graph3d .` and commits `graph3d-out/`.
2. Everyone pulls — their assistant reads the graph immediately.
3. Run `graph3d hook install` to auto-rebuild after each commit (AST only, no API cost). This also sets up a git merge driver so `graph.json` is never left with conflict markers — two devs committing in parallel get their graphs union-merged automatically.
4. When docs or papers change, run `/graph3d --update` to refresh those nodes.

---

## Using the graph directly

```bash
# query the graph from the terminal
graph3d query "show the auth flow"
graph3d query "what connects DigestAuth to Response?" --graph graph3d-out/graph.json

# expose the graph as an MCP server (for repeated tool-call access)
python -m graph3d.serve graph3d-out/graph.json

# register with Kimi Code:
kimi mcp add --transport stdio graph3d -- python -m graph3d.serve graph3d-out/graph.json
```

The MCP server gives your assistant structured access: `query_graph`, `get_node`, `get_neighbors`, `shortest_path`, `list_prs`, `get_pr_impact`, `triage_prs`.

> **WSL / Linux note:** Ubuntu ships `python3`, not `python`. Use a venv to avoid conflicts:
> ```bash
> python3 -m venv .venv && .venv/bin/pip install "graph3d[mcp]"
> ```

---

## Environment variables

These are only needed for **headless / CI extraction** (`graph3d extract`). When running via the `/graph3d` skill inside your IDE, the model API is provided by your IDE session — no extra keys needed.

| Variable | Used for | When required |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude (Anthropic) backend | `--backend claude` |
| `GEMINI_API_KEY` or `GOOGLE_API_KEY` | Google Gemini backend | `--backend gemini` |
| `OPENAI_API_KEY` | OpenAI or OpenAI-compatible APIs | `--backend openai` |
| `DEEPSEEK_API_KEY` | DeepSeek backend | `--backend deepseek` |
| `MOONSHOT_API_KEY` | Kimi Code backend | `--backend kimi` |
| `OLLAMA_BASE_URL` | Ollama local inference URL | `--backend ollama` (default: `http://localhost:11434`) |
| `OLLAMA_MODEL` | Ollama model name | `--backend ollama` (default: auto-detect) |
| `GRAPH3D_OLLAMA_NUM_CTX` | Override Ollama KV-cache window size | optional — auto-sized by default |
| `GRAPH3D_OLLAMA_KEEP_ALIVE` | Minutes to keep Ollama model loaded | optional — set `0` to unload after each chunk |
| `AWS_*` / `~/.aws/credentials` | AWS Bedrock — standard credential chain | `--backend bedrock` (no API key, uses IAM) |
| `GRAPH3D_MAX_WORKERS` | AST parallelism thread count | optional — also `--max-workers` flag |
| `GRAPH3D_MAX_OUTPUT_TOKENS` | Raise output cap for dense corpora | optional — e.g. `32768` for large files |
| `GRAPH3D_API_TIMEOUT` | HTTP timeout in seconds (default: 600) | optional — also `--api-timeout` flag |
| `GRAPH3D_FORCE` | Force graph rebuild even with fewer nodes | optional — also `--force` flag |
| `GRAPH3D_GOOGLE_WORKSPACE` | Auto-enable Google Workspace export | optional — set to `1` |
| `GRAPH3D_TRIAGE_BACKEND` | Backend for `graph3d prs --triage` | optional — auto-detected from available keys |
| `GRAPH3D_TRIAGE_MODEL` | Model override for triage | optional — e.g. `claude-opus-4-7` |

---

## Privacy

- **Code files** — processed locally via tree-sitter. Nothing leaves your machine.
- **Video / audio** — transcribed locally with faster-whisper. Nothing leaves your machine.
- **Docs, PDFs, images** — sent to your AI assistant for semantic extraction (via the `/graph3d` skill, using whatever model your IDE session runs). Headless `graph3d extract` requires `GEMINI_API_KEY` / `GOOGLE_API_KEY` (Gemini), `MOONSHOT_API_KEY` (Kimi), `ANTHROPIC_API_KEY` (Claude), `OPENAI_API_KEY` (OpenAI), `DEEPSEEK_API_KEY` (DeepSeek), a running Ollama instance (`OLLAMA_BASE_URL`), AWS credentials via the standard provider chain (Bedrock - no API key needed, uses IAM), or the `claude` CLI binary (Claude Code - no API key needed, uses your Claude subscription). The `--dedup-llm` flag uses the same key.
- **Data residency** — `graph3d extract` auto-detects which provider to use based on which API key is set (priority: Gemini → Kimi → Claude → OpenAI → DeepSeek → Bedrock → Ollama). For code with data-residency requirements, use `--backend ollama` (fully local) or pass an explicit `--backend` flag. Kimi (`MOONSHOT_API_KEY`) routes to Moonshot AI servers in China.
- No telemetry, no usage tracking, no analytics.

---

## Troubleshooting

**`graph3d: command not found` after `pip install graph3d`**
pip installs scripts to a user bin directory that may not be on your PATH. Fix:
- macOS: add `~/Library/Python/3.x/bin` to your PATH in `~/.zshrc`
- Linux: add `~/.local/bin` to your PATH in `~/.bashrc`
- Or use `uv tool install graph3d` / `pipx install graph3d` — both manage PATH automatically.

**`python -m graph3d` works but `graph3d` command doesn't**
Your shell's PATH doesn't include the Python scripts directory. Use `uv` or `pipx` instead of plain `pip`.

**`/graph3d .` causes "path not recognized" in PowerShell**
PowerShell treats a leading `/` as a path separator. Use `graph3d .` (no slash) on Windows.

**Graph has fewer nodes after `--update` or rebuild**
If a refactor deleted files, the old nodes linger. Pass `--force` (or set `GRAPH3D_FORCE=1`) to overwrite even when the rebuild has fewer nodes.

**Graph has duplicate nodes for the same entity (ghost duplicates)**
This happens when semantic and AST extraction disagreed on the node ID format. Run a full re-extract to clean up:
```bash
graph3d extract . --force
```

**Ollama runs out of VRAM / context window exceeded**
The KV-cache window is auto-sized but may be too large for your GPU. Reduce it:
```bash
GRAPH3D_OLLAMA_NUM_CTX=8192 graph3d extract ./docs --backend ollama --token-budget 4000
```

**Graph HTML is too large to open in a browser (>5000 nodes)**
Skip HTML generation and use the JSON directly:
```bash
graph3d cluster-only ./my-project --no-viz
graph3d query "..."
```

**`graph.json` has conflict markers after two devs commit at once**
Run `graph3d hook install` — it sets up a git merge driver that union-merges `graph.json` automatically so conflicts never happen.

**Extraction returns empty nodes/edges for docs or PDFs**
Docs and PDFs require an LLM call. Check that your API key is set and the backend is correct:
```bash
ANTHROPIC_API_KEY=sk-... graph3d extract ./docs --backend claude
```

**Skill version mismatch warning in your IDE**
Your installed graph3d version is different from the skill file. Update:
```bash
uv tool upgrade graph3d
graph3d install  # overwrites the skill file
```

---

## Full command reference

```
/graph3d                          # run on current directory
/graph3d ./raw                    # run on a specific folder
/graph3d ./raw --mode deep        # more aggressive relationship extraction
/graph3d ./raw --update           # re-extract only changed files
/graph3d ./raw --directed         # preserve edge direction
/graph3d ./raw --cluster-only     # rerun clustering on existing graph
/graph3d ./raw --no-viz           # skip HTML visualization
/graph3d ./raw --obsidian         # generate Obsidian vault
/graph3d ./raw --wiki             # build agent-crawlable markdown wiki
/graph3d ./raw --svg              # export graph.svg
/graph3d ./raw --graphml          # export for Gephi / yEd
/graph3d ./raw --neo4j            # generate cypher.txt for Neo4j
/graph3d ./raw --neo4j-push bolt://localhost:7687
/graph3d ./raw --watch            # auto-sync as files change
/graph3d ./raw --mcp              # start MCP stdio server

/graph3d add https://arxiv.org/abs/1706.03762
/graph3d add <video-url>
/graph3d add https://... --author "Name" --contributor "Name"

/graph3d query "what connects attention to the optimizer?"
/graph3d query "..." --dfs --budget 1500
/graph3d path "DigestAuth" "Response"
/graph3d explain "SwinTransformer"

graph3d uninstall                 # remove from all platforms in one shot
graph3d uninstall --purge         # also delete graph3d-out/
graph3d uninstall --project --platform codex  # remove project-scoped install files only

graph3d hook install              # post-commit + post-checkout hooks
graph3d hook uninstall
graph3d hook status

graph3d claude install / uninstall
graph3d codex install / uninstall
graph3d opencode install / uninstall
graph3d cursor install / uninstall
graph3d gemini install / uninstall
graph3d copilot install / uninstall
graph3d aider install / uninstall
graph3d claw install / uninstall
graph3d droid install / uninstall
graph3d trae install / uninstall
graph3d trae-cn install / uninstall
graph3d hermes install / uninstall
graph3d amp install / uninstall
graph3d kiro install / uninstall
graph3d devin install / uninstall
graph3d antigravity install / uninstall

graph3d extract ./docs                        # headless LLM extraction for CI (no IDE needed)
graph3d extract ./docs --backend gemini       # explicit backend: gemini, kimi, claude, openai, deepseek, ollama, bedrock, or claude-cli
graph3d extract ./docs --backend gemini --model gemini-3.1-pro-preview
graph3d extract ./docs --backend ollama       # local Ollama (set OLLAMA_BASE_URL / OLLAMA_MODEL) - no API key needed for loopback
GRAPH3D_OLLAMA_NUM_CTX=32768 graph3d extract ./docs --backend ollama   # override KV-cache window (auto-sized by default)
GRAPH3D_OLLAMA_KEEP_ALIVE=0 graph3d extract ./docs --backend ollama    # unload model after each chunk (saves VRAM on small GPUs)
graph3d extract ./docs --backend bedrock      # AWS Bedrock via IAM - no API key, uses AWS credential chain
graph3d extract ./docs --backend claude-cli   # route through Claude Code CLI - no API key, uses your Claude subscription
graph3d extract ./docs --max-workers 16       # AST parallelism (also GRAPH3D_MAX_WORKERS)
graph3d extract ./docs --token-budget 30000   # smaller semantic chunks for local/small models
graph3d extract ./docs --max-concurrency 2    # fewer parallel LLM calls (useful for local inference)
graph3d extract ./docs --api-timeout 900      # longer HTTP timeout for slow local models (default 600s)
graph3d extract ./docs --google-workspace     # export .gdoc/.gsheet/.gslides via gws before extraction
graph3d extract ./docs --mode deep            # richer semantic extraction via extended system prompt
graph3d extract ./docs --no-cluster           # raw extraction only, skip clustering
graph3d extract ./docs --force                # overwrite graph.json even if new graph has fewer nodes (use after refactors or to clear ghost duplicates)
graph3d extract ./docs --dedup-llm            # LLM tiebreaker for ambiguous entity pairs (uses same API key)
graph3d extract ./docs --global --as myrepo   # extract and register into the cross-project global graph
GRAPH3D_MAX_OUTPUT_TOKENS=32768 graph3d extract ./docs --backend claude  # raise output cap for dense corpora

graph3d export callflow-html                       # graph3d-out/<project>-callflow.html
graph3d export callflow-html --max-sections 8      # cap generated architecture sections
graph3d export callflow-html --output docs/arch.html
graph3d export callflow-html ./some-repo/graph3d-out

graph3d global add graph3d-out/graph.json myrepo   # register a project graph into ~/.graph3d/global.json
graph3d global remove myrepo                         # remove a project from the global graph
graph3d global list                                  # show all registered repos + node/edge counts
graph3d global path                                  # print path to the global graph file

graph3d prs                              # PR dashboard: CI, review, worktree, graph impact
graph3d prs 42                           # deep dive on PR #42
graph3d prs --triage                     # AI triage ranking (auto-detects backend from env)
graph3d prs --worktrees                  # worktree → branch → PR mapping
graph3d prs --conflicts                  # PRs sharing graph communities (merge-order risk)
graph3d prs --base main                  # filter to PRs targeting a specific base branch
graph3d prs --repo owner/repo            # run against a different GitHub repo
GRAPH3D_TRIAGE_BACKEND=kimi graph3d prs --triage   # use a specific backend for triage

graph3d clone https://github.com/karpathy/nanoGPT
graph3d merge-graphs a.json b.json --out merged.json
graph3d --version                                    # print installed version
graph3d watch ./src
graph3d check-update ./src
graph3d update ./src
graph3d update ./src --no-cluster  # skip reclustering, write raw AST graph only
graph3d update ./src --force       # overwrite even if new graph has fewer nodes
graph3d cluster-only ./my-project
graph3d cluster-only ./my-project --graph path/to/graph.json  # custom graph location
graph3d cluster-only ./my-project --resolution 1.5            # more, smaller communities
graph3d cluster-only ./my-project --exclude-hubs 99           # exclude p99 degree nodes from partitioning
```

---

## Learn more

- [How it works](docs/how-it-works.md) — the extraction pipeline, community detection, confidence scoring, benchmarks
- [ARCHITECTURE.md](ARCHITECTURE.md) — module breakdown, how to add a language
- [Optional integrations](docs/docker-mcp-sqlite.md) — Docker MCP Toolkit + SQLite

---

## Built on graph3d — Penpax

[**Penpax**](https://graph3dlabs.ai) is the always-on layer built on top of graph3d — it applies the same graph approach to your entire working life: meetings, browser history, emails, files, and code, updating continuously in the background.

Built for people whose work lives across hundreds of conversations and documents they can never fully reconstruct. No cloud, fully on-device.

**Free trial launching soon.** [Join the waitlist →](https://graph3dlabs.ai)

---

<details>
<summary>Contributing</summary>

### Development setup

The project uses [uv](https://docs.astral.sh/uv/) for dev workflow. Install it once, then:

```bash
git clone https://github.com/DarbotLM/graph3d.git
cd graph3d
git checkout v8                        # active development branch

# Create the project venv and install graph3d + all extras + the dev group
# (pytest). uv installs the dev dependency group by default; pass --no-dev to
# skip it.
uv sync --all-extras
```

Verify the editable install:
```bash
uv run graph3d --version
uv run python -c "import graph3d; print(graph3d.__file__)"
```

### Running tests

```bash
uv run pytest tests/ -q                # run the full suite
uv run pytest tests/test_extract.py -q # one module
uv run pytest tests/ -q -k "python"    # filter by name
```

> macOS note: the test suite includes both `sample.f90` and `sample.F90` fixtures. These collide on case-insensitive HFS+ / APFS file systems. Run on Linux or in a Docker container if you need to test both Fortran variants simultaneously.

### Git workflow

- Active development happens on the `v8` branch.
- Commit style: `fix: <description>` / `feat: <description>` / `docs: <description>`
- Before opening a PR, run `uv run pytest tests/ -q` and confirm it passes.
- Add a fixture file to `tests/fixtures/` and tests to `tests/test_languages.py` for any new language extractor.

### What to contribute

**Worked examples** are the most useful contribution. Run `/graph3d` on a real corpus, save the output to `worked/{slug}/`, write an honest `review.md` covering what the graph got right and wrong, and open a PR.

**Extraction bugs** — open an issue with the input file, the cache entry (`graph3d-out/cache/`), and what was missed or wrong.

See [ARCHITECTURE.md](ARCHITECTURE.md) for module responsibilities and how to add a language.

</details>
