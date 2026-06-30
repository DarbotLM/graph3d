
from __future__ import annotations

import builtins
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import networkx as nx
import pytest
from networkx.readwrite import json_graph

import graph3d.__main__ as mainmod
from graph3d.cache import _body_content, cached_files, clear_cache, file_hash, load_cached, save_cached
from graph3d.cli_api import ExtractProfileArgs, parse_corpus_profile, parse_extract_profile_args, valid_corpus_profiles
from graph3d.hooks import _CHECKOUT_MARKER, _HOOK_MARKER, _hooks_dir, install as hook_install, status as hook_status, uninstall as hook_uninstall
from graph3d.watch import _WATCHED_EXTENSIONS, _check_shrink, _notify_only, _rebuild_lock


PLATFORMS = {
    "claude": ".claude/skills/graph3d/SKILL.md",
    "codex": ".agents/skills/graph3d/SKILL.md",
    "opencode": ".config/opencode/skills/graph3d/SKILL.md",
    "claw": ".openclaw/skills/graph3d/SKILL.md",
    "droid": ".factory/skills/graph3d/SKILL.md",
    "trae": ".trae/skills/graph3d/SKILL.md",
    "trae-cn": ".trae-cn/skills/graph3d/SKILL.md",
    "windows": ".claude/skills/graph3d/SKILL.md",
}
OLD = """## graph3d\n\nRules:\n- ALWAYS read graph3d-out/GRAPH_REPORT.md before reading any source files.\n- use graph3d query when needed\n"""
OLD_VSCODE = """## graph3d\n\nYour first tool call must be to read `graph3d-out/GRAPH_REPORT.md`.\n"""
OLD_CURSOR = """---\ndescription: graph3d knowledge graph context\nalwaysApply: true\n---\n\nread graph3d-out/GRAPH_REPORT.md for god nodes and community structure\n"""
OLD_KIRO = """---\ninclusion: always\n---\n\nIf `graph3d-out/GRAPH_REPORT.md` exists, read it before answering architecture questions.\n"""
OLD_HOOK = "Read graph3d-out/GRAPH_REPORT.md for god nodes and community structure before searching raw files"


def _install(root: Path, platform: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    cwd = Path.cwd()
    try:
        os.chdir(root)
        with patch("graph3d.__main__.Path.home", return_value=root):
            mainmod.install(platform=platform)
    finally:
        os.chdir(cwd)


def _repo(path: Path) -> Path:
    subprocess.run(["git", "init", str(path)], check=True, capture_output=True)
    return path


def _docs(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    docs = root / "docs"
    docs.mkdir()
    (docs / "intro.md").write_text("# Intro\nText", encoding="utf-8")
    (docs / "api.md").write_text("# API\nText", encoding="utf-8")
    return docs


def _shrink(n: int) -> dict[str, object]:
    return {"nodes": [{"id": f"n{i}"} for i in range(n)], "links": []}


def test_install(tmp_path, monkeypatch, capsys):
    failures = []
    for platform, rel in PLATFORMS.items():
        root = tmp_path / platform
        root.mkdir()
        try:
            _install(root, platform)
            assert (root / rel).exists(), f"{platform} missing {rel}"
        except AssertionError as exc:
            failures.append(str(exc))
    with pytest.raises(SystemExit):
        _install(tmp_path / "unknown", "unknown")

    pkg = Path(mainmod.__file__).parent
    skill_cases = [
        ("skill-codex.md", ["spawn_agent", "Dirty `graph3d-out/` artifacts are expected", "not a reason to skip Graph3d", "graph3d query", "graph3d explain", "graph3d path"], []),
        ("skill-opencode.md", ["@mention", "@agent", "serial fallback", "reduce semantic chunks to 10-12 files each", "10-12 files each if the smaller-chunk large-corpus policy was applied", "process chunks one at a time"], ["general-purpose", 'subagent_type="general-purpose"', "Wait for the user's answer before proceeding"]),
        ("skill-claw.md", ["sequential"], ["spawn_agent", "@mention"]),
    ]
    for name, need, banned in skill_cases:
        text = (pkg / name).read_text(encoding="utf-8")
        failures += [f"{name} missing {n}" for n in need if n not in text and n not in text.lower()]
        failures += [f"{name} contains {n}" for n in banned if n in text]
    for name in ("skill.md", "skill-codex.md", "skill-opencode.md", "skill-claw.md", "skill-windows.md", "skill-droid.md", "skill-trae.md"):
        assert (pkg / name).exists(), f"missing package skill {name}"

    cli_cases = [
        (["graph3d", "install", "opencode"], lambda p, h: [(h / ".config/opencode/skills/graph3d/SKILL.md").exists(), not (h / ".claude").exists()]),
        (["graph3d", "install", "--project"], lambda p, h: [(p / ".claude/skills/graph3d/SKILL.md").exists(), (p / ".claude/CLAUDE.md").exists(), not (h / ".claude").exists(), ".claude/skills/graph3d/SKILL.md" in (p / ".claude/CLAUDE.md").read_text(encoding="utf-8")]),
        (["graph3d", "install", "--project", "--platform", "codex"], lambda p, h: [(p / ".agents/skills/graph3d/SKILL.md").exists(), (p / "AGENTS.md").exists(), (p / ".codex/hooks.json").exists(), not (h / ".agents").exists()]),
        (["graph3d", "antigravity", "install", "--project"], lambda p, h: [(p / ".agents/skills/graph3d/SKILL.md").exists(), not (h / ".agents").exists()]),
    ]
    for i, (argv, checks) in enumerate(cli_cases):
        home, project = tmp_path / f"home{i}", tmp_path / f"project{i}"
        project.mkdir()
        monkeypatch.chdir(project)
        monkeypatch.setattr(sys, "argv", argv)
        with patch("graph3d.__main__.Path.home", return_value=home):
            mainmod.main()
        assert all(checks(project, home)), argv
    assert "git add .claude/" in capsys.readouterr().out

    help_root = tmp_path / "help"
    help_root.mkdir()
    monkeypatch.chdir(help_root)
    monkeypatch.setattr(sys, "argv", ["graph3d", "install", "opencode", "--help"])
    with patch("graph3d.__main__.Path.home", return_value=help_root):
        mainmod.main()
    out = capsys.readouterr().out
    assert "Usage: graph3d install" in out and "opencode" in out and not (help_root / ".claude").exists() and not (help_root / ".config").exists()

    uninstall_cases = [
        (["graph3d", "claude", "install", "--project"], ["graph3d", "claude", "uninstall", "--project"], ".claude/skills/graph3d/SKILL.md", [".claude/skills/graph3d/SKILL.md", ".claude/CLAUDE.md", "CLAUDE.md"]),
        (["graph3d", "codex", "install", "--project"], ["graph3d", "codex", "uninstall", "--project"], ".agents/skills/graph3d/SKILL.md", [".agents/skills/graph3d/SKILL.md", "AGENTS.md"]),
        (["graph3d", "install", "--project", "--platform", "codex"], ["graph3d", "uninstall", "--project", "--platform", "codex"], ".agents/skills/graph3d/SKILL.md", [".agents/skills/graph3d/SKILL.md", "AGENTS.md"]),
        (["graph3d", "install", "--project"], ["graph3d", "uninstall", "--project"], ".claude/skills/graph3d/SKILL.md", [".claude/skills/graph3d/SKILL.md", ".claude/CLAUDE.md"]),
        (["graph3d", "antigravity", "install", "--project"], ["graph3d", "antigravity", "uninstall", "--project"], ".gemini/config/skills/graph3d/SKILL.md", [".agents/skills/graph3d/SKILL.md"]),
    ]
    for i, (install_argv, uninstall_argv, user_rel, removed) in enumerate(uninstall_cases):
        home, project = tmp_path / f"uhome{i}", tmp_path / f"uproject{i}"
        project.mkdir()
        user_skill = home / user_rel
        user_skill.parent.mkdir(parents=True)
        user_skill.write_text("user", encoding="utf-8")
        monkeypatch.chdir(project)
        with patch("graph3d.__main__.Path.home", return_value=home):
            monkeypatch.setattr(sys, "argv", install_argv); mainmod.main()
            monkeypatch.setattr(sys, "argv", uninstall_argv); mainmod.main()
        assert user_skill.exists()
        assert not any((project / r).exists() for r in removed)

    ag_project, ag_home = tmp_path / "agproject", tmp_path / "aghome"
    ag_project.mkdir(); monkeypatch.chdir(ag_project)
    with patch("graph3d.__main__.Path.home", return_value=ag_home):
        monkeypatch.setattr(sys, "argv", ["graph3d", "antigravity", "install"]); mainmod.main()
        assert (ag_home / ".gemini/config/skills/graph3d/SKILL.md").exists()
        assert not (ag_home / ".agents/skills/graph3d/SKILL.md").exists()
        assert (ag_project / ".agents/rules/graph3d.md").exists() and (ag_project / ".agents/workflows/graph3d.md").exists()
        monkeypatch.setattr(sys, "argv", ["graph3d", "antigravity", "uninstall"]); mainmod.main()
    assert not (ag_home / ".gemini/config/skills/graph3d/SKILL.md").exists()
    assert not (ag_project / ".agents/rules/graph3d.md").exists() and not (ag_project / ".agents/workflows/graph3d.md").exists()

    for platform in ("codex", "opencode", "claw"):
        root = tmp_path / f"agents-{platform}"; root.mkdir(); mainmod._agents_install(root, platform)
        assert (root / "AGENTS.md").exists()
    root = tmp_path / "agents-idem"; root.mkdir(); mainmod._agents_install(root, "codex"); mainmod._agents_install(root, "codex")
    assert (root / "AGENTS.md").read_text(encoding="utf-8").count("## graph3d") == 1
    assert "Dirty graph3d-out/ files are expected" in (root / "AGENTS.md").read_text(encoding="utf-8")
    existing = tmp_path / "agents-existing"; existing.mkdir(); (existing / "AGENTS.md").write_text("# Existing\nDo not break things.\n", encoding="utf-8")
    mainmod._agents_install(existing, "codex"); mainmod._agents_uninstall(existing)
    assert "Do not break things." in (existing / "AGENTS.md").read_text(encoding="utf-8") and "## graph3d" not in (existing / "AGENTS.md").read_text(encoding="utf-8")
    only = tmp_path / "agents-only"; only.mkdir(); mainmod._agents_install(only, "codex"); mainmod._agents_uninstall(only)
    assert not (only / "AGENTS.md").exists()
    none = tmp_path / "agents-none"; none.mkdir(); mainmod._agents_uninstall(none)
    assert "nothing to do" in capsys.readouterr().out

    op = tmp_path / "opencode-plugin"; op.mkdir(); cfg = op / ".opencode/opencode.json"; cfg.parent.mkdir(parents=True); cfg.write_text(json.dumps({"model": "claude-opus-4-5", "plugin": []}), encoding="utf-8")
    mainmod._agents_install(op, "opencode")
    assert (op / ".opencode/plugins/graph3d.js").exists() and "tool.execute.before" in (op / ".opencode/plugins/graph3d.js").read_text(encoding="utf-8")
    assert json.loads(cfg.read_text(encoding="utf-8"))["model"] == "claude-opus-4-5" and any("graph3d.js" in p for p in json.loads(cfg.read_text(encoding="utf-8"))["plugin"])
    mainmod._agents_uninstall(op, platform="opencode")
    assert not (op / ".opencode/plugins/graph3d.js").exists() and not any("graph3d.js" in p for p in json.loads(cfg.read_text(encoding="utf-8")).get("plugin", []))

    cursor = tmp_path / "cursor"; cursor.mkdir(); mainmod._cursor_install(cursor); rule = cursor / ".cursor/rules/graph3d.mdc"; before = rule.read_text(encoding="utf-8"); mainmod._cursor_install(cursor)
    assert rule.read_text(encoding="utf-8") == before and "alwaysApply: true" in before and "graph3d-out/GRAPH_REPORT.md" in before
    mainmod._cursor_uninstall(cursor); mainmod._cursor_uninstall(cursor); assert not rule.exists()
    gem = tmp_path / "gemini"; gem.mkdir(); (gem / "GEMINI.md").write_text("# Existing\n", encoding="utf-8"); mainmod.gemini_install(gem); mainmod.gemini_install(gem)
    text = (gem / "GEMINI.md").read_text(encoding="utf-8"); settings = json.loads((gem / ".gemini/settings.json").read_text(encoding="utf-8"))
    assert "# Existing" in text and "graph3d-out/GRAPH_REPORT.md" in text and text.count("## graph3d") == 1 and any("graph3d" in str(h) for h in settings["hooks"]["BeforeTool"])
    mainmod.gemini_uninstall(gem); mainmod.gemini_uninstall(gem); assert (gem / "GEMINI.md").exists() and "# Existing" in (gem / "GEMINI.md").read_text(encoding="utf-8") and "## graph3d" not in (gem / "GEMINI.md").read_text(encoding="utf-8")
    assert not failures, "\n".join(failures)


def test_install_upgrade_and_strings(tmp_path, monkeypatch):
    failures = []
    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    cases = [
        ("claude", "CLAUDE.md", OLD, lambda r: mainmod.claude_install(r), "# My Project\nSome description.\n"),
        ("agents", "AGENTS.md", OLD, lambda r: mainmod._agents_install(r, "codex"), "# Project agents\n"),
        ("gemini", "GEMINI.md", OLD, lambda r: mainmod.gemini_install(r), ""),
        ("vscode", ".github/copilot-instructions.md", OLD_VSCODE, lambda r: mainmod.vscode_install(r), ""),
        ("cursor", ".cursor/rules/graph3d.mdc", OLD_CURSOR, lambda r: mainmod._cursor_install(r), ""),
    ]
    for name, rel, old, installer, prefix in cases:
        root = tmp_path / name; root.mkdir(); monkeypatch.chdir(root); path = root / rel; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(prefix + old, encoding="utf-8")
        installer(root); after = path.read_text(encoding="utf-8")
        if "ALWAYS read graph3d-out/GRAPH_REPORT.md" in after or "first tool call must be" in after or "graph3d query" not in after:
            failures.append(f"{name} stale report-first text survived")
        if prefix and prefix.strip() not in after:
            failures.append(f"{name} did not preserve existing content")
    root = tmp_path / "hook"; root.mkdir(); monkeypatch.chdir(root); (root / "CLAUDE.md").write_text(OLD, encoding="utf-8"); settings = root / ".claude/settings.json"; settings.parent.mkdir(parents=True)
    settings.write_text(json.dumps({"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": OLD_HOOK}]}]}}), encoding="utf-8")
    mainmod.claude_install(root); assert OLD_HOOK not in settings.read_text(encoding="utf-8") and "graph3d query" in settings.read_text(encoding="utf-8")
    if (Path(mainmod.__file__).parent / "skill-kiro.md").exists():
        root = tmp_path / "kiro"; root.mkdir(); steering = root / ".kiro/steering/graph3d.md"; steering.parent.mkdir(parents=True); steering.write_text(OLD_KIRO, encoding="utf-8"); mainmod._kiro_install(root); after = steering.read_text(encoding="utf-8")
        assert "read it before answering architecture questions" not in after and "graph3d query" in after and "inclusion: always" in after
    texts = {"_SETTINGS_HOOK": json.dumps(mainmod._SETTINGS_HOOK), "_CLAUDE_MD_SECTION": mainmod._CLAUDE_MD_SECTION, "_AGENTS_MD_SECTION": mainmod._AGENTS_MD_SECTION, "_GEMINI_MD_SECTION": mainmod._GEMINI_MD_SECTION, "_GEMINI_HOOK": json.dumps(mainmod._GEMINI_HOOK), "_VSCODE_INSTRUCTIONS_SECTION": mainmod._VSCODE_INSTRUCTIONS_SECTION, "_ANTIGRAVITY_RULES": mainmod._ANTIGRAVITY_RULES, "_KIRO_STEERING": mainmod._KIRO_STEERING, "_CURSOR_RULE": mainmod._CURSOR_RULE, "_OPENCODE_PLUGIN_JS": mainmod._OPENCODE_PLUGIN_JS, "_DEVIN_RULES": mainmod._DEVIN_RULES}
    assert not [n for n, t in texts.items() if "graph3d query" not in t]
    banned = [re.compile(r"read[^.\n]{0,80}GRAPH_REPORT\.md[^.\n]{0,80}before", re.I), re.compile(r"first\s+tool\s+call[^.\n]{0,80}GRAPH_REPORT", re.I), re.compile(r"always\s+read[^.\n]{0,80}GRAPH_REPORT", re.I)]
    assert not [(n, p.search(t).group(0)) for n, t in texts.items() for p in banned if p.search(t)]
    md = {k: texts[k] for k in ("_CLAUDE_MD_SECTION", "_AGENTS_MD_SECTION", "_GEMINI_MD_SECTION", "_VSCODE_INSTRUCTIONS_SECTION", "_ANTIGRAVITY_RULES", "_KIRO_STEERING", "_CURSOR_RULE", "_DEVIN_RULES")}
    assert not [n for n, t in md.items() if "GRAPH_REPORT.md" not in t]
    assert "Dirty graph3d-out/ files are expected" in mainmod._AGENTS_MD_SECTION and "not a reason to skip graph3d" in mainmod._AGENTS_MD_SECTION
    doc = (Path(__file__).parent.parent / "docs/how-it-works.md").read_text(encoding="utf-8")
    assert all(s in doc for s in ("Code files are not sent to the LLM semantic extractor", "code files, Pass 3 is skipped entirely", "docs, papers, images, and transcripts"))
    assert not failures, "\n".join(failures)


def test_cli_subcommands(tmp_path, monkeypatch, capsys):
    assert valid_corpus_profiles() == ("all", "product", "schemas", "session", "tests", "worked")
    for raw, expected in [(None, None), ("", None), ("  ", None), ("PRODUCT", "product"), (" tests ", "tests")]:
        assert parse_corpus_profile(raw) == expected
    with pytest.raises(ValueError, match="unknown corpus profile"):
        parse_corpus_profile("docs")
    assert parse_extract_profile_args(["--backend", "claude", "--profile", "PRODUCT", "--no-cluster"]) == ExtractProfileArgs(profile="product", args=("--backend", "claude", "--no-cluster"))
    parsed = parse_extract_profile_args(["--profile=tests", "--profile=schemas"])
    assert parsed.profile == "schemas" and parsed.args == ()
    for args in (["--profile"], ["--profile", ""], ["--profile="]):
        with pytest.raises(ValueError, match="--profile requires a non-empty value"):
            parse_extract_profile_args(list(args))

    graph = nx.DiGraph()
    graph.add_node("target", label="Foo", source_file="pkg/foo.py", source_location="L1")
    graph.add_node("caller", label="X()", source_file="app.py", source_location="L4")
    graph.add_node("barrel", label="__init__.py", source_file="pkg/__init__.py", source_location=None)
    graph.add_node("consumer", label="app.py", source_file="app.py", source_location=None)
    graph.add_edge("caller", "target", relation="calls", context="call", confidence="EXTRACTED")
    graph.add_edge("barrel", "target", relation="re_exports", context="export", confidence="EXTRACTED")
    graph.add_edge("consumer", "target", relation="imports", context="import", confidence="EXTRACTED")
    graph_path = tmp_path / "affected.json"; graph_path.write_text(json.dumps(json_graph.node_link_data(graph, edges="links")), encoding="utf-8")
    monkeypatch.setattr(mainmod, "_check_skill_version", lambda _: None)
    monkeypatch.setattr(mainmod.sys, "argv", ["graph3d", "affected", "Foo", "--graph", str(graph_path)]); mainmod.main(); out = capsys.readouterr().out
    assert all(s in out for s in ("Affected nodes for Foo", "X()", "calls", "__init__.py", "re_exports", "app.py", "imports"))
    monkeypatch.setattr(mainmod.sys, "argv", ["graph3d", "affected", "Foo", "--relation", "calls", "--graph", str(graph_path)]); mainmod.main(); out = capsys.readouterr().out
    assert "Relations: calls" in out and "X()" in out and "__init__.py" not in out

    explain = {"directed": False, "multigraph": False, "graph": {}, "nodes": [{"id": "validate", "label": "validateSanitySession()", "source_file": "server/sanity-validate-session.ts", "community": 0}, {"id": "create_patch", "label": "createPatchHandler()", "source_file": "server/create-patch-handler.ts", "community": 0}, {"id": "create_edit", "label": "createEditHandler()", "source_file": "server/create-edit-handler.ts", "community": 0}, {"id": "stable_stringify", "label": "stableStringify()", "source_file": "shared/stringify.ts", "community": 0}], "links": [{"source": "create_patch", "target": "validate", "relation": "calls", "confidence": "EXTRACTED"}, {"source": "create_edit", "target": "validate", "relation": "calls", "confidence": "EXTRACTED"}, {"source": "validate", "target": "stable_stringify", "relation": "calls", "confidence": "EXTRACTED"}]}
    explain_path = tmp_path / "explain.json"; explain_path.write_text(json.dumps(explain), encoding="utf-8")
    cases = [("validateSanitySession", ["<-- createPatchHandler() [calls]", "<-- createEditHandler() [calls]", "--> stableStringify() [calls]"], ["--> createPatchHandler() [calls]", "--> createEditHandler() [calls]"]), ("createPatchHandler", ["--> validateSanitySession() [calls]"], ["<-- "])]
    for label, need, banned in cases:
        monkeypatch.setattr(mainmod.sys, "argv", ["graph3d", "explain", label, "--graph", str(explain_path)]); mainmod.main(); out = capsys.readouterr().out
        assert all(s in out for s in need) and not any(s in out for s in banned)

    def corpus(root: Path) -> Path:
        root.mkdir(); (root / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8"); (root / "README.md").write_text("# Notes\nThe main function entry point.\n", encoding="utf-8"); return root

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake-key")
    monkeypatch.setattr("graph3d.llm.extract_corpus_parallel", lambda paths, **kw: {"nodes": [], "edges": [], "hyperedges": [], "input_tokens": 0, "output_tokens": 0})
    out_dir = tmp_path / "extract-fail-out"; monkeypatch.setattr(mainmod.sys, "argv", ["graph3d", "extract", str(corpus(tmp_path / "extract-fail")), "--backend", "claude", "--out", str(out_dir)])
    with pytest.raises(SystemExit) as exc:
        mainmod.main()
    stderr = capsys.readouterr().err
    assert exc.value.code == 1 and "all semantic chunks failed" in stderr and "claude" in stderr and not (out_dir / "graph3d-out/graph.json").exists()

    def ok_chunks(paths, **kwargs):
        if kwargs.get("on_chunk_done"):
            kwargs["on_chunk_done"](0, 1, {"nodes": [], "edges": [], "hyperedges": []})
        return {"nodes": [], "edges": [], "hyperedges": [], "input_tokens": 100, "output_tokens": 50}

    monkeypatch.setattr("graph3d.llm.extract_corpus_parallel", ok_chunks)
    out_dir = tmp_path / "extract-ok-out"; monkeypatch.setattr(mainmod.sys, "argv", ["graph3d", "extract", str(corpus(tmp_path / "extract-ok")), "--backend", "claude", "--out", str(out_dir)])
    try:
        mainmod.main()
    except SystemExit as exc:
        assert exc.code in (None, 0)
    assert (out_dir / "graph3d-out/graph.json").exists()

    seen = {}
    def fake_detect(root, **kwargs):
        seen["root"] = root; seen["kwargs"] = kwargs
        return {"files": {"code": [], "document": [], "paper": [], "image": [], "video": []}, "total_files": 0, "total_words": 0}
    monkeypatch.setattr("graph3d.detect.detect", fake_detect)
    out_dir = tmp_path / "profile-out"; monkeypatch.setattr(mainmod.sys, "argv", ["graph3d", "extract", str(tmp_path), "--backend", "claude", "--profile", "PRODUCT", "--out", str(out_dir), "--no-cluster"])
    with pytest.raises(SystemExit) as exc:
        mainmod.main()
    assert exc.value.code == 0 and seen["root"] == tmp_path.resolve() and seen["kwargs"]["profile"] == "product" and (out_dir / "graph3d-out/graph.json").exists()


def test_hooks(tmp_path, monkeypatch):
    repo = _repo(tmp_path / "repo"); result = hook_install(repo); pc = repo / ".git/hooks/post-commit"; co = repo / ".git/hooks/post-checkout"
    assert pc.exists() and co.exists() and _HOOK_MARKER in pc.read_text(encoding="utf-8") and _CHECKOUT_MARKER in co.read_text(encoding="utf-8") and "installed" in result
    if os.name == "nt":
        assert pc.read_text(encoding="utf-8").startswith("#!/bin/sh\n") and co.read_text(encoding="utf-8").startswith("#!/bin/sh\n")
    else:
        assert pc.stat().st_mode & 0o111 and co.stat().st_mode & 0o111
    assert "already installed" in hook_install(repo) and pc.read_text(encoding="utf-8").count(_HOOK_MARKER) == 1
    stat = hook_status(repo); assert "post-commit" in stat and "post-checkout" in stat and stat.count("installed") >= 2
    existing = _repo(tmp_path / "existing"); hook = existing / ".git/hooks/post-commit"; hook.write_text("#!/bin/bash\necho existing\n", encoding="utf-8"); hook.chmod(0o755); hook_install(existing)
    assert "existing" in hook.read_text(encoding="utf-8") and _HOOK_MARKER in hook.read_text(encoding="utf-8")
    rem = _repo(tmp_path / "remove"); hook_install(rem); assert "removed" in hook_uninstall(rem).lower(); assert not (rem / ".git/hooks/post-commit").exists() and not (rem / ".git/hooks/post-checkout").exists()
    assert "nothing to remove" in hook_uninstall(_repo(tmp_path / "empty")) and "not installed" in hook_status(_repo(tmp_path / "status-empty"))
    with pytest.raises(RuntimeError, match="No git repository"):
        hook_install(tmp_path / "not-a-repo")
    repo = _repo(tmp_path / "paths")
    monkeypatch.setattr("subprocess.run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=".git/hooks\n")); assert _hooks_dir(repo) == (repo / ".git/hooks").resolve()
    monkeypatch.setattr("subprocess.run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="--path-format=absolute\n.git/hooks\n")); assert _hooks_dir(repo) == repo / ".git/hooks" and not (repo / "--path-format=absolute\n.git").exists()
    actual = tmp_path / "actual-hooks"; monkeypatch.setattr("subprocess.run", lambda *a, **k: SimpleNamespace(returncode=0, stdout=f"{actual}\n")); assert _hooks_dir(repo) == actual.resolve()
    monkeypatch.undo()
    from graph3d.hooks import _PYTHON_DETECT
    assert "*.exe) _SHEBANG=" in _PYTHON_DETECT or "*.exe)" in _PYTHON_DETECT
    root = tmp_path / "hook-check"; (root / "graph3d-out").mkdir(parents=True); (root / "graph3d-out/graph.json").write_text("{}", encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "graph3d", "hook-check"], cwd=root, capture_output=True, text=True)
    assert result.returncode == 0 and result.stdout == "" and result.stderr == ""


def test_watch_rebuild(tmp_path, monkeypatch, capsys):
    for name in ("flag", "flag-dir", "idempotent"):
        root = tmp_path / name; root.mkdir(); _notify_only(root); _notify_only(root); assert (root / "graph3d-out/needs_update").read_text(encoding="utf-8") == "1"
    for ext in (".py", ".ts", ".go", ".rs", ".md", ".txt", ".pdf", ".png", ".jpg", ".json", ".sh"):
        assert ext in _WATCHED_EXTENSIONS
    assert ".pyc" not in _WATCHED_EXTENSIONS and ".log" not in _WATCHED_EXTENSIONS
    from graph3d.watch import check_update, watch, _rebuild_code, _queue_pending, _drain_pending, _merge_changed_paths, _PENDING_FILENAME
    assert check_update(tmp_path / "none") is True
    flag = tmp_path / "checked/graph3d-out/needs_update"; flag.parent.mkdir(parents=True); flag.write_text("1", encoding="utf-8"); assert check_update(tmp_path / "checked") is True and "graph3d --update" in capsys.readouterr().out and flag.exists()
    with monkeypatch.context() as m:
        real_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name in {"watchdog.observers", "watchdog.events"}:
                raise ImportError("mocked missing watchdog")
            return real_import(name, *args, **kwargs)
        m.setattr(builtins, "__import__", mock_import)
        with pytest.raises(ImportError, match="watchdog not installed"):
            watch(tmp_path / "watch")
    if sys.platform != "win32":
        out = tmp_path / "lock/graph3d-out"; lock = out / ".rebuild.lock"
        with _rebuild_lock(out) as got:
            assert got is True and lock.read_text(encoding="utf-8") == f"{os.getpid()}\n"
        assert not lock.exists()
        with _rebuild_lock(out) as outer:
            held = lock.read_text(encoding="utf-8")
            with _rebuild_lock(out, blocking=False) as inner:
                assert outer is True and inner is False and lock.read_text(encoding="utf-8") == held
    corpus = tmp_path / "corpus"; corpus.mkdir(); (corpus / "auth.py").write_text("def login(): pass\ndef logout(): pass\n", encoding="utf-8"); (corpus / "utils.py").write_text("def format_date(): pass\n", encoding="utf-8")
    assert _rebuild_code(corpus, acquire_lock=False); graph_path = corpus / "graph3d-out/graph.json"; assert "format_date()" in {n["label"] for n in json.loads(graph_path.read_text(encoding="utf-8"))["nodes"]}
    (corpus / "utils.py").unlink(); assert _rebuild_code(corpus, acquire_lock=False); labels = {n["label"] for n in json.loads(graph_path.read_text(encoding="utf-8"))["nodes"]}; assert "format_date()" not in labels and "login()" in labels
    from graph3d import cluster as cluster_mod
    root = tmp_path / "cluster"; root.mkdir(); (root / "app.py").write_text("def alpha():\n    return 1\n\ndef beta():\n    return alpha()\n", encoding="utf-8"); calls = {"n": 0}
    def cluster_once(graph):
        calls["n"] += 1
        if calls["n"] > 1:
            raise AssertionError("cluster() should be skipped")
        return {0: sorted(graph.nodes())}
    monkeypatch.setattr(cluster_mod, "cluster", cluster_once); monkeypatch.setattr(cluster_mod, "score_all", lambda _g, comm: {cid: 1.0 for cid in comm}); assert _rebuild_code(root) and _rebuild_code(root) and calls["n"] == 1
    for kwargs, expected in [({"force": False, "existing_data": _shrink(100), "new_data": _shrink(80)}, False), ({"force": True, "existing_data": _shrink(100), "new_data": _shrink(1)}, True), ({"force": False, "existing_data": _shrink(100), "new_data": _shrink(80), "had_explicit_deletions": True}, True), ({"force": False, "existing_data": {}, "new_data": _shrink(50)}, True), ({"force": False, "existing_data": _shrink(50), "new_data": _shrink(60)}, True)]:
        assert _check_shrink(**kwargs) is expected
    assert "Refusing to overwrite" in capsys.readouterr().err
    tmp_file = tmp_path / "graph.tmp.json"; tmp_file.write_text("{}", encoding="utf-8"); assert _check_shrink(force=False, existing_data=_shrink(100), new_data=_shrink(80), tmp=tmp_file) is False and not tmp_file.exists()
    tmp_file.write_text("{}", encoding="utf-8"); assert _check_shrink(force=False, existing_data=_shrink(100), new_data=_shrink(80), tmp=tmp_file, had_explicit_deletions=True) is True and tmp_file.exists()
    out = tmp_path / "pending/graph3d-out"; paths = [Path("a.py"), Path("sub/b.py"), Path("c.md")]; _queue_pending(out, paths); assert (out / _PENDING_FILENAME).read_text(encoding="utf-8").splitlines() == ["a.py", "sub/b.py", "c.md"] and _drain_pending(out) == paths and _drain_pending(out) == []
    _queue_pending(out, [Path("a.py"), Path("b.py")]); _queue_pending(out, [Path("b.py"), Path("c.py")]); (out / ".pending_changes").open("a", encoding="utf-8").write("\n   \n"); assert _drain_pending(out) == [Path("a.py"), Path("b.py"), Path("c.py")]
    _queue_pending(out, []); assert not (out / _PENDING_FILENAME).exists(); assert [p.as_posix() for p in _merge_changed_paths([Path("a.py"), Path("b.py")], None, [Path("b.py"), Path("c.py")], [Path("a.py")])] == ["a.py", "b.py", "c.py"]


def test_incremental(tmp_path):
    docs = _docs(tmp_path / "manifest"); result = subprocess.run([sys.executable, "-m", "graph3d", "extract", str(docs)], cwd=tmp_path, capture_output=True, text=True)
    assert "no LLM API key" in result.stderr or result.returncode != 0
    assert not (docs / "graph3d-out/manifest.json").exists()
    docs = _docs(tmp_path / "with-manifest"); out = docs / "graph3d-out"; out.mkdir(); (out / "graph.json").write_text(json.dumps({"nodes": [], "links": []}), encoding="utf-8"); (out / "manifest.json").write_text(json.dumps({"document": [str(docs / "intro.md")]}), encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "graph3d", "extract", str(docs)], cwd=tmp_path, capture_output=True, text=True); assert "incremental" in (result.stdout + result.stderr).lower() or result.returncode != 0
    docs = _docs(tmp_path / "without-manifest"); result = subprocess.run([sys.executable, "-m", "graph3d", "extract", str(docs)], cwd=tmp_path, capture_output=True, text=True)
    assert "incremental update" not in result.stdout.lower() and "incremental scan" not in result.stdout.lower()


def test_cache(tmp_path):
    sample = tmp_path / "sample.txt"; sample.write_text("hello world", encoding="utf-8"); h1 = file_hash(sample); assert h1 == file_hash(sample) and isinstance(h1, str) and len(h1) == 64
    a = tmp_path / "a.txt"; b = tmp_path / "b.txt"; a.write_text("content one", encoding="utf-8"); b.write_text("content two", encoding="utf-8"); assert file_hash(a) != file_hash(b)
    result = {"nodes": [{"id": "n1", "label": "Node1"}], "edges": []}; save_cached(sample, result, root=tmp_path); assert load_cached(sample, root=tmp_path) == result; sample.write_text("changed", encoding="utf-8"); assert load_cached(sample, root=tmp_path) is None
    f1 = tmp_path / "file1.py"; f2 = tmp_path / "file2.py"; f1.write_text("alpha", encoding="utf-8"); f2.write_text("beta", encoding="utf-8"); save_cached(f1, {"nodes": [], "edges": []}, root=tmp_path); save_cached(f2, {"nodes": [], "edges": []}, root=tmp_path); hashes = cached_files(tmp_path); assert file_hash(f1, tmp_path) in hashes and file_hash(f2, tmp_path) in hashes
    base = tmp_path / "graph3d-out/cache"; assert list(base.rglob("*.json")); clear_cache(tmp_path); assert not list(base.rglob("*.json"))
    md = tmp_path / "doc.md"; md.write_text("---\nreviewed: 2026-01-01\n---\n\n# Title\n\nBody text.", encoding="utf-8"); h = file_hash(md); md.write_text("---\nreviewed: 2026-04-09\n---\n\n# Title\n\nBody text.", encoding="utf-8"); assert file_hash(md) == h
    md.write_text("---\nreviewed: 2026-01-01\n---\n\n# Title\n\nOriginal body.", encoding="utf-8"); h = file_hash(md); md.write_text("---\nreviewed: 2026-01-01\n---\n\n# Title\n\nChanged body.", encoding="utf-8"); assert file_hash(md) != h
    md.write_text("# Just a heading\n\nNo frontmatter here.", encoding="utf-8"); h = file_hash(md); md.write_text("# Just a heading\n\nDifferent content.", encoding="utf-8"); assert file_hash(md) != h
    py = tmp_path / "script.py"; py.write_text("# comment\nx = 1", encoding="utf-8"); h = file_hash(py); py.write_text("# changed comment\nx = 1", encoding="utf-8"); assert file_hash(py) != h
    assert _body_content(b"---\ntitle: Test\n---\n\nActual body.") == b"\n\nActual body."
    assert _body_content(b"No frontmatter here.") == b"No frontmatter here."
