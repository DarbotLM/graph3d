from __future__ import annotations

import ast
import inspect
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from graph3d import llm
from graph3d.detect import CODE_EXTENSIONS
from graph3d.extract import (
    _DISPATCH, _TSX_CONFIG, _TS_CONFIG, _file_stem, _get_extractor, _make_id,
    _semantic_reference_edge, collect_files, extract, extract_astro, extract_bash,
    extract_blade, extract_c, extract_cpp, extract_csproj, extract_csharp,
    extract_dart, extract_delphi_form, extract_dm, extract_dmf, extract_dmi,
    extract_dmm, extract_elixir, extract_fortran, extract_go, extract_groovy,
    extract_java, extract_js, extract_json, extract_julia, extract_kotlin,
    extract_lazarus_form, extract_lazarus_package, extract_markdown,
    extract_objc, extract_pascal, extract_php, extract_powershell,
    extract_python, extract_razor, extract_ruby, extract_rust, extract_scala,
    extract_sln, extract_sql, extract_swift, register_suffix_extractor,
)
from graph3d.extractor_registry import ExtractorRegistry
from graph3d.mcp_ingest import extract_mcp_config
from graph3d import pdf as g3pdf
from graph3d.schema_paths import extract_sqlite_schema

FIXTURES = Path(__file__).parent / "fixtures"
UNICODE_CONTENT = "\u2192 means implies. \u2705 done. Score \u2265 90."


def _labels(r):
    return [n["label"] for n in r.get("nodes", [])]


def _relations(r):
    return {e["relation"] for e in r.get("edges", [])}


def _norm(label):
    return label.strip("()").lstrip(".")


def _edge_labels(r, relation, context=None):
    labels = {n["id"]: _norm(n["label"]) for n in r.get("nodes", [])}
    pairs = set()
    for e in r.get("edges", []):
        if e.get("relation") == relation and (context is None or e.get("context") == context):
            pairs.add((labels.get(e["source"], e["source"]), labels.get(e["target"], e["target"])))
    return pairs


def _call_pairs(r):
    labels = {n["id"]: n["label"] for n in r.get("nodes", [])}
    return {(labels.get(e["source"], e["source"]), labels.get(e["target"], e["target"])) for e in r.get("edges", []) if e.get("relation") == "calls"}


def _edges(r, *relations):
    return [e for e in r.get("edges", []) if e.get("relation") in relations]


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")
    return path


def _dangling(r, name, target_relations=None):
    failures = []
    node_ids = {n["id"] for n in r.get("nodes", [])}
    for e in r.get("edges", []):
        if e.get("source") not in node_ids:
            failures.append(f"{name}: dangling source {e}")
        if target_relations is None or e.get("relation") in target_relations:
            if e.get("target") not in node_ids:
                failures.append(f"{name}: dangling target {e}")
    return failures


def _fake_a(path):
    return {"nodes": [], "edges": [], "path": str(path)}


def _fake_b(path):
    return {"nodes": [], "edges": [], "path": str(path)}


def test_language_extractors_structural():
    case_table = [
        ("python", extract_python, "sample.py", ["Transformer"], {"contains", "method"}),
        ("java", extract_java, "sample.java", ["DataProcessor", "Processor", "addItem", "process"], {"imports", "inherits", "implements", "method"}),
        ("c", extract_c, "sample.c", ["process", "main"], {"imports", "calls", "references"}),
        ("cpp", extract_cpp, "sample.cpp", ["HttpClient", "AuthedHttpClient", "RetryingHttpClient"], {"imports", "inherits", "references"}),
        ("ruby", extract_ruby, "sample.rb", ["ApiClient", "get", "post", "parse_response"], {"method"}),
        ("csharp", extract_csharp, "sample.cs", ["DataProcessor", "IProcessor", "Process"], {"imports", "inherits", "implements", "references"}),
        ("kotlin", extract_kotlin, "sample.kt", ["HttpClient", "Config", "get", "post", "createClient"], {"calls", "inherits", "implements", "references"}),
        ("scala", extract_scala, "sample.scala", ["HttpClient", "HttpClientFactory", "get", "post"], {"imports", "inherits", "mixes_in", "references"}),
        ("php", extract_php, "sample.php", ["ApiClient", "get", "post", "parseResponse"], {"imports", "inherits", "implements", "mixes_in", "calls"}),
        ("swift", extract_swift, "sample.swift", ["DataProcessor", "Processor", "Config", "CacheManager", "NetworkError", "timeout", "connectionFailed", "deinit", "subscript"], {"imports", "inherits", "implements", "case_of", "calls"}),
        ("elixir", extract_elixir, "sample.ex", ["MyApp.Accounts.User", "create", "find", "validate"], {"imports", "calls", "method"}),
        ("objc", extract_objc, "sample.m", ["Animal", "Dog", "speak", "fetch", "initWithName"], {"imports", "inherits", "implements", "references"}),
        ("go", extract_go, "sample.go", ["Server", "Start", "Stop", "NewServer"], {"imports_from", "calls", "embeds", "references"}),
        ("julia", extract_julia, "sample.jl", ["Geometry", "Point", "Circle", "Shape", "area", "distance", "perimeter"], {"imports", "inherits", "calls", "references"}),
        ("fortran", extract_fortran, "sample.f90", ["geometry", "circle_area", "print_area", "distance", "main", "point"], {"imports", "calls", "references"}),
        ("powershell", extract_powershell, "sample.ps1", ["DataProcessor", "Transform", "Save"], {"references"}),
        ("typescript", extract_js, "sample.ts", ["HttpClient", "get", "post", "buildHeaders"], {"imports", "imports_from", "calls"}),
        ("tsx", extract_js, "sample.tsx", ["fmtDate", "fmtCount", "App"], {"calls"}),
        ("rust", extract_rust, "sample.rs", ["Graph", "add_node", "add_edge", "build_graph"], {"imports_from", "calls", "implements", "inherits", "references"}),
        ("sql", extract_sql, "sample.sql", ["users", "organizations", "active_users", "get_user"], {"references", "reads_from"}),
        ("markdown", extract_markdown, "deploy_guide.md", ["Deploy Guide", "Prerequisites", "Full Deploy", "Rollback", "Database Migration"], {"contains"}),
        ("groovy", extract_groovy, "sample.groovy", ["SampleService", "process", "reset"], {"imports"}),
        ("groovy_spock", extract_groovy, "sample_spock.groovy", ["SampleSpec", "it's"], {"imports"}),
        ("dm", extract_dm, "sample.dm", ["log_event()", "RunTest()", "/datum/weapon", "/datum/weapon/sword", "/datum/weapon/attack()", "/datum/weapon/sword/attack()", "/datum/weapon/sword/sharpen()"], {"imports", "calls", "instantiates"}),
        ("dmi", extract_dmi, "sample.dmi", ["sample.dmi", '"mob"'], {"contains"}),
        ("dmm", extract_dmm, "sample.dmm", ["sample.dmm"], {"uses"}),
        ("dmf", extract_dmf, "sample.dmf", ['window "mapwindow"', 'window "infowindow"', 'elem "map" [MAP]'], {"contains"}),
        ("sln", extract_sln, "sample.sln", ["WebApi", "Domain", "Tests"], {"contains", "imports"}),
        ("csproj", extract_csproj, "sample.csproj", ["MediatR", "FluentValidation", "Swashbuckle", "Domain.csproj", "net8.0", "Microsoft.NET.Sdk.Web"], {"imports"}),
        ("razor", extract_razor, "sample.razor", ["IncrementCount", "LoadData", "/counter"], {"imports", "calls", "inherits"}),
        ("pascal", extract_pascal, "sample.pas", ["SampleUnit", "TBaseProcessor", "TDataProcessor", "IProcessor", "Process", "Initialize", "GetCount", "Reset"], {"imports", "inherits", "calls"}),
        ("lfm", extract_lazarus_form, "sample.lfm", ["TSampleForm", "TPanel", "TButton", "TLabel", "TTimer", "ButtonOKClick", "TimerRefreshTimer"], {"contains", "references"}),
        ("lpk", extract_lazarus_package, "sample.lpk", ["SamplePackage", "FCL", "LCL", "sample", "sampleutils"], {"imports", "contains"}),
        ("dfm", extract_delphi_form, "sample.dfm", ["TMainForm", "TPanel", "TButton", "TMemo", "TStatusBar", "FormCreate", "ButtonOKClick"], {"contains", "references"}),
        ("bash", extract_bash, "sample.sh", ["build()", "test_suite()", "deploy()"], {"defines", "calls", "contains"}),
        ("json", extract_json, "sample.json", ["name", "version", "scripts", "dependencies"], {"contains", "imports"}),
    ]
    failures = []
    for name, fn, fixture, expected_labels, expected_relations in case_table:
        if name == "sql":
            pytest.importorskip("tree_sitter_sql")
        result = fn(FIXTURES / fixture)
        labels = _labels(result)
        relations = _relations(result)
        if "error" in result:
            failures.append(f"{name}: unexpected error {result['error']}")
        failures += [f"{name}: missing label {x}; labels={labels}" for x in expected_labels if not any(x in label for label in labels)]
        missing = expected_relations - relations
        if missing:
            failures.append(f"{name}: missing relations {sorted(missing)} from {sorted(relations)}")
        failures += _dangling(result, name, {"contains", "method", "calls", "inherits", "implements", "mixes_in", "embeds", "references", "case_of", "instantiates", "defines"})
    assert not failures, failures


def test_language_calls_references_and_special_edges(tmp_path):
    failures = []
    results = {
        "java": extract_java(FIXTURES / "sample.java"), "c": extract_c(FIXTURES / "sample.c"),
        "cpp": extract_cpp(FIXTURES / "sample.cpp"), "csharp": extract_csharp(FIXTURES / "sample.cs"),
        "kotlin": extract_kotlin(FIXTURES / "sample.kt"), "scala": extract_scala(FIXTURES / "sample.scala"),
        "php": extract_php(FIXTURES / "sample.php"), "swift": extract_swift(FIXTURES / "sample.swift"),
        "objc": extract_objc(FIXTURES / "sample.m"), "go": extract_go(FIXTURES / "sample.go"),
        "julia": extract_julia(FIXTURES / "sample.jl"), "fortran": extract_fortran(FIXTURES / "sample.f90"),
        "powershell": extract_powershell(FIXTURES / "sample.ps1"), "rust": extract_rust(FIXTURES / "sample.rs"),
        "dm": extract_dm(FIXTURES / "sample.dm"), "dmm": extract_dmm(FIXTURES / "sample.dmm"),
        "dmi": extract_dmi(FIXTURES / "sample.dmi"), "dmf": extract_dmf(FIXTURES / "sample.dmf"),
        "lfm": extract_lazarus_form(FIXTURES / "sample.lfm"), "dfm": extract_delphi_form(FIXTURES / "sample.dfm"),
        "lpk": extract_lazarus_package(FIXTURES / "sample.lpk"), "scala": extract_scala(FIXTURES / "sample.scala"),
    }
    pair_cases = [
        ("java", "inherits", None, [("DataProcessor", "BaseProcessor")]),
        ("java", "implements", None, [("DataProcessor", "Processor")]),
        ("java", "references", "parameter_type", [("build", "HttpClient")]),
        ("java", "references", "return_type", [("build", "Result")]),
        ("java", "references", "generic_arg", [("build", "DataProcessor")]),
        ("java", "references", "attribute", [("build", "Override")]),
        ("c", "references", "parameter_type", [("make_rect", "Rectangle")]),
        ("c", "references", "return_type", [("make_rect", "Rectangle")]),
        ("cpp", "inherits", None, [("AuthedHttpClient", "HttpClient"), ("RetryingHttpClient", "HttpClient")]),
        ("cpp", "references", "field", [("HttpClient", "string"), ("HttpClient", "vector")]),
        ("cpp", "references", "generic_arg", [("HttpClient", "string")]),
        ("csharp", "inherits", None, [("DataProcessor", "Processor")]),
        ("csharp", "implements", None, [("DataProcessor", "IProcessor")]),
        ("csharp", "references", "field", [("DataProcessor", "HttpClient")]),
        ("csharp", "references", "return_type", [("Build", "Result")]),
        ("kotlin", "calls", None, [("get", "buildRequest"), ("post", "buildRequest"), ("createClient", "Config"), ("createClient", "HttpClient")]),
        ("kotlin", "implements", None, [("DataProcessor", "Loggable")]),
        ("kotlin", "references", "field", [("DataProcessor", "Result")]),
        ("scala", "mixes_in", None, [("HttpClient", "Loggable")]),
        ("scala", "references", "return_type", [("create", "HttpClient")]),
        ("php", "mixes_in", None, [("DataProcessor", "HasName")]),
        ("php", "references", "return_type", [("run", "Result")]),
        ("swift", "case_of", None, [("NetworkError", "timeout"), ("NetworkError", "connectionFailed")]),
        ("swift", "method", None, [("Config", "isValid")]),
        ("objc", "inherits", None, [("Animal", "NSObject"), ("Dog", "Animal")]),
        ("objc", "implements", None, [("Animal", "SampleDelegate")]),
        ("go", "embeds", None, [("DataProcessor", "BaseProcessor"), ("ReaderLogger", "Logger")]),
        ("go", "references", "return_type", [("Build", "Result")]),
        ("julia", "inherits", None, [("Point", "Shape"), ("Circle", "Shape")]),
        ("julia", "references", "field", [("Point", "Float64"), ("Circle", "Point"), ("Circle", "Float64")]),
        ("fortran", "references", "parameter_type", [("translate", "point")]),
        ("fortran", "references", "return_type", [("origin", "point")]),
        ("powershell", "references", "return_type", [("Transform", "string"), ("Save", "void")]),
        ("rust", "implements", None, [("DataProcessor", "Processor")]),
        ("rust", "inherits", None, [("Logger", "Processor")]),
        ("rust", "references", "generic_arg", [("build", "DataProcessor")]),
        ("dmi", "contains", None, [("sample.dmi", '"mob"')]),
        ("dmf", "contains", None, [('window "mapwindow"', 'elem "map" [MAP]')]),
    ]
    for name, relation, context, pairs in pair_cases:
        got = _edge_labels(results[name], relation, context)
        failures += [f"{name}: missing {relation}/{context} pair {p}; got={got}" for p in pairs if p not in got]
    context_cases = [
        ("java", ["imports", "imports_from"], "import"), ("c", ["imports", "imports_from"], "import"),
        ("cpp", ["imports", "imports_from"], "import"), ("csharp", ["imports"], "import"),
        ("scala", ["imports", "imports_from"], "import"), ("php", ["imports", "imports_from"], "import"),
        ("swift", ["imports", "imports_from"], "import"), ("objc", ["imports", "imports_from"], "import"),
        ("go", ["imports", "imports_from"], "import"), ("julia", ["imports", "imports_from"], "import"),
        ("fortran", ["imports"], "use"), ("dm", ["imports", "imports_from"], "import"),
        ("lfm", ["references"], "event"), ("dfm", ["references"], "event"), ("lpk", ["imports"], "import"),
    ]
    for name, rels, context in context_cases:
        edges = _edges(results[name], *rels)
        if not edges or not all(e.get("context") == context for e in edges):
            failures.append(f"{name}: bad context for {rels}: {edges}")
    for name, result in results.items():
        if name == "powershell":
            continue
        for e in _edges(result, "calls", "instantiates"):
            if e.get("context") != "call":
                failures.append(f"{name}: call-like edge missing call context {e}")
    dynamic = extract_js(FIXTURES / "dynamic_import.ts")
    targets = {e["target"] for e in dynamic["edges"] if e["relation"] == "imports_from"}
    for part in ["logger", "mayaengine", "queue", "statichelper"]:
        if not any(part in t.lower() for t in targets):
            failures.append(f"dynamic_import: missing {part} in {targets}")
    if any("{" in t or "}" in t for t in targets):
        failures.append(f"dynamic_import: unresolved template target {targets}")
    labels_by_id = {n["id"]: n["label"] for n in dynamic["nodes"]}
    maya = [e for e in dynamic["edges"] if e["relation"] == "imports_from" and "mayaengine" in e["target"].lower()]
    if not maya or maya[0]["confidence"] != "EXTRACTED" or "processInbound" not in labels_by_id.get(maya[0]["source"], ""):
        failures.append(f"dynamic_import: bad maya edge {maya}")
    sync = next((n["id"] for n in dynamic["nodes"] if n["label"] == "syncOnly()"), None)
    if sync and any(e["source"] == sync and e["relation"] == "imports_from" for e in dynamic["edges"]):
        failures.append("dynamic_import: syncOnly emitted imports_from")
    php_special = [("uses_static_prop", "DefaultPalette", "sample_php_static_prop.php"), ("uses_config", "Throttle", "sample_php_config.php"), ("bound_to", "StripeGateway", "sample_php_container.php"), ("listened_by", "SendWelcomeEmail", "sample_php_listen.php")]
    for relation, target_label, fixture in php_special:
        result = extract_php(FIXTURES / fixture)
        labels = {n["id"]: n["label"] for n in result["nodes"]}
        pairs = [(labels.get(e["source"], e["source"]), labels.get(e["target"], e["target"])) for e in result["edges"] if e["relation"] == relation]
        if not any(target_label in tgt for _, tgt in pairs):
            failures.append(f"php {relation}: missing target {target_label}; pairs={pairs}")
    dm = results["dm"]
    if any(c.strip("()") == ".." for _, c in _call_pairs(dm)) or any(raw.get("callee") == ".." for raw in dm.get("raw_calls", [])):
        failures.append("dm: super call emitted")
    if any(s == "RunTest()" and "attack" in c for s, c in _call_pairs(dm)) or not any(raw.get("callee") == "attack" for raw in dm.get("raw_calls", [])):
        failures.append("dm: ambiguous attack handling changed")
    dmm_targets = {e["target"] for e in results["dmm"]["edges"] if e["relation"] == "uses"}
    if {"turf_closed_wall", "obj_structure_table", "obj_item_weapon_sword", "area_station_maintenance"} - dmm_targets or any("{" in t for t in dmm_targets) or len(dmm_targets) != 5:
        failures.append(f"dmm: bad targets {dmm_targets}")
    swift = extract(sorted((FIXTURES / "swift_cross_file").glob("*.swift")), cache_root=tmp_path / "swift-cache")
    foo_nodes = [n for n in swift["nodes"] if n["label"] == "Foo"]
    if len(foo_nodes) != 1:
        failures.append(f"swift cross-file: expected one Foo, got {foo_nodes}")
    else:
        method_ids = {e["target"] for e in swift["edges"] if e["relation"] == "method" and e["source"] == foo_nodes[0]["id"]}
        method_labels = {n["label"] for n in swift["nodes"] if n["id"] in method_ids}
        if not any("one" in label for label in method_labels) or not any("two" in label for label in method_labels):
            failures.append(f"swift cross-file: methods {method_labels}")
    assert not failures, failures


def test_extract_pipeline_registry_and_dispatch(tmp_path, monkeypatch, capsys):
    failures = []
    for args, expected in [(("_auth",), "auth"), ((".httpx._client",), "httpx_client"), (("__init__",), "init")]:
        got = _make_id(*args)
        if got != expected:
            failures.append(f"_make_id{args}: got {got}")
    if _make_id("foo", "Bar") != _make_id("foo", "Bar"):
        failures.append("_make_id inconsistent")
    files = collect_files(FIXTURES)
    if not files or not all(f.suffix in set(_DISPATCH) for f in files) or any(part.startswith(".") for f in files for part in f.parts):
        failures.append("collect_files returned bad files")
    real = tmp_path / "real_src"
    real.mkdir()
    _write(real / "lib.py", "x = 1\n")
    (tmp_path / "linked_src").symlink_to(real, target_is_directory=True)
    if [p.name for p in collect_files(tmp_path, follow_symlinks=False)].count("lib.py") != 1:
        failures.append("collect_files no-follow symlink failed")
    if [p.name for p in collect_files(tmp_path, follow_symlinks=True)].count("lib.py") != 2:
        failures.append("collect_files follow symlink failed")
    (real / "cycle").symlink_to(tmp_path, target_is_directory=True)
    if not any(p.name == "lib.py" for p in collect_files(tmp_path, follow_symlinks=True)):
        failures.append("collect_files circular symlink failed")
    merged = extract([FIXTURES / "sample.py", FIXTURES / "sample.ts", FIXTURES / "sample.go", FIXTURES / "sample.rs"], cache_root=tmp_path / "merge-cache")
    sources = {n.get("source_file") for n in merged["nodes"] if n.get("source_file")}
    for name in ["sample.py", "sample.ts", "sample.go", "sample.rs"]:
        if not any(name in source for source in sources):
            failures.append(f"extract dispatch missing {name}")
    if merged.get("input_tokens") != 0:
        failures.append("extract should not use LLM tokens")
    first = _write(tmp_path / "apps" / "api" / "Program.cs", "class Program { void Run() { SharedHelper(); } }\n")
    second = _write(tmp_path / "tools" / "api" / "Program.cs", "class Program { void Run() {} }\n")
    helper = _write(tmp_path / "shared" / "Helper.cs", "class Helper { void SharedHelper() {} }\n")
    dup = extract([first, second, helper], cache_root=tmp_path / "dup-cache")
    programs = [n for n in dup["nodes"] if n["label"] == "Program" and n.get("source_file", "").endswith("Program.cs")]
    if len(programs) != 2 or len({n["id"] for n in programs}) != 2:
        failures.append(f"duplicate Program ids not disambiguated: {programs}")
    failures += _dangling(dup, "duplicate ids", {"contains", "method", "calls"})
    definition = _write(tmp_path / "interfaces.py", "class BookStore:\n    pass\n")
    implementation = _write(tmp_path / "services" / "BookStore.cs", "class SqliteBookStore : BookStore { }\n")
    rewired = extract([definition, implementation], cache_root=tmp_path / "rewire-cache")
    by_id = {n["id"]: n for n in rewired["nodes"]}
    matches = [e for e in rewired["edges"] if e["relation"] == "inherits" and by_id[e["source"]]["label"] == "SqliteBookStore" and by_id[e["target"]]["label"] == "BookStore"]
    if not matches or matches[0]["target"] != next(n["id"] for n in rewired["nodes"] if n["label"] == "BookStore" and str(n.get("source_file", "")).endswith("interfaces.py")):
        failures.append("unique inheritance stub not rewired")
    if any(n["label"] == "BookStore" and not n.get("source_file") for n in rewired["nodes"]):
        failures.append("rewired stub still present")
    ambiguous = extract([_write(tmp_path / "a" / "interfaces.py", "class BookStore:\n    pass\n"), _write(tmp_path / "b" / "interfaces.py", "class BookStore:\n    pass\n"), implementation], cache_root=tmp_path / "amb-cache")
    if not any(n["label"] == "BookStore" and not n.get("source_file") for n in ambiguous["nodes"]):
        failures.append("ambiguous inheritance stub should remain")
    factory = _write(tmp_path / "factory.py", "def BookStore():\n    return object()\n")
    no_func = extract([factory, implementation], cache_root=tmp_path / "func-cache")
    by_id = {n["id"]: n for n in no_func["nodes"]}
    if any(by_id[e["source"]]["label"] == "SqliteBookStore" and by_id[e["target"]]["label"] == "BookStore()" for e in no_func["edges"] if e["relation"] == "inherits"):
        failures.append("inheritance rewired to same-named function")
    constructor = extract([_write(tmp_path / "Sample.java", "class DataProcessor { public DataProcessor() {} }\n")], cache_root=tmp_path / "constructor-cache")
    if not any(n["label"] == ".DataProcessor()" for n in constructor["nodes"]) or any(e["source"] == e["target"] for e in constructor["edges"]):
        failures.append("constructor missing or self-loop emitted")
    cache_file = _write(tmp_path / "cache_me.py", "def foo(): pass\n")
    r1 = extract([cache_file], cache_root=tmp_path / "ast-cache")
    r2 = extract([cache_file], cache_root=tmp_path / "ast-cache")
    cache_file.write_text("def foo(): pass\ndef bar(): pass\n", encoding="utf-8")
    r3 = extract([cache_file], cache_root=tmp_path / "ast-cache")
    if (len(r1["nodes"]), len(r1["edges"])) != (len(r2["nodes"]), len(r2["edges"])) or not any("bar" in label for label in _labels(r3)):
        failures.append("cache hit/miss behavior changed")
    ambiguous_calls = extract([_write(tmp_path / "caller.py", "def run():\n    log()\n"), _write(tmp_path / "one.py", "def log():\n    return 'a'\n"), _write(tmp_path / "two.py", "def log():\n    return 'b'\n")], cache_root=tmp_path / "call-cache")
    nodes = {n["id"]: n for n in ambiguous_calls["nodes"]}
    if any(nodes[e["source"]]["label"] == "run()" and nodes[e["target"]]["label"] == "log()" for e in ambiguous_calls["edges"] if e["relation"] == "calls" and e["confidence"] == "INFERRED"):
        failures.append("ambiguous duplicate cross-file call was inferred")
    imported_call = extract([_write(tmp_path / "caller.js", "const { doWork } = require('./lib');\nfunction run() { doWork(); }\n"), _write(tmp_path / "lib.js", "function doWork() { return 1; }\nmodule.exports = { doWork };\n")], cache_root=tmp_path)
    nodes = {n["id"]: n for n in imported_call["nodes"]}
    call_edges = [e for e in imported_call["edges"] if e["relation"] == "calls" and nodes[e["source"]]["label"] == "run()" and nodes[e["target"]]["label"] == "doWork()"]
    if len(call_edges) != 1 or call_edges[0]["confidence"] != "EXTRACTED" or call_edges[0].get("confidence_score") != 1.0:
        failures.append(f"import evidence did not promote call edge: {call_edges}")
    inferred_call = extract([_write(tmp_path / "caller_no_import.js", "function run() { doUnique(); }\n"), _write(tmp_path / "unique_lib.js", "function doUnique() { return 1; }\nmodule.exports = { doUnique };\n")], cache_root=tmp_path)
    nodes = {n["id"]: n for n in inferred_call["nodes"]}
    inferred_edges = [e for e in inferred_call["edges"] if e["relation"] == "calls" and nodes[e["source"]]["label"] == "run()" and nodes[e["target"]]["label"] == "doUnique()"]
    if len(inferred_edges) != 1 or inferred_edges[0]["confidence"] != "INFERRED":
        failures.append(f"no-import call should stay inferred: {inferred_edges}")
    registry = ExtractorRegistry({".json": _fake_a})
    registry.register_suffix("artifact", _fake_a)
    registry.register_filename_predicate(lambda path: path.name == "special.json", _fake_b, name="special_json")
    if registry.lookup(Path("sample.artifact")) is not _fake_a or registry.lookup(Path("special.json")) is not _fake_b or registry.lookup(Path("package.json")) is not _fake_a or registry.filename_routes()[0].name != "special_json":
        failures.append("ExtractorRegistry lookup behavior changed")
    dispatch = {}
    compat = ExtractorRegistry(dispatch)
    compat.register_suffix(".foo", _fake_a)
    dispatch[".bar"] = _fake_b
    if dispatch.get(".foo") is not _fake_a or compat.lookup(Path("two.bar")) is not _fake_b:
        failures.append("ExtractorRegistry backing dispatch compatibility changed")
    old = _DISPATCH.get(".g3dtest")
    try:
        if register_suffix_extractor(".g3dtest", _fake_a) is not _fake_a or _get_extractor(Path("artifact.g3dtest")) is not _fake_a:
            failures.append("register_suffix_extractor failed")
    finally:
        if old is None:
            _DISPATCH.pop(".g3dtest", None)
        else:
            _DISPATCH[".g3dtest"] = old
    dispatch_cases = [(Path("package.json"), extract_json), (Path(".mcp.json"), extract_mcp_config), (Path("claude_desktop_config.json"), extract_mcp_config), (Path("component.blade.php"), extract_blade), (Path("events.sqlite"), extract_sqlite_schema), (Path("foo.sh"), extract_bash), (Path("foo.bash"), extract_bash), (Path("foo.json"), extract_json), (Path("foo.sln"), extract_sln), (Path("foo.csproj"), extract_csproj), (Path("foo.fsproj"), extract_csproj), (Path("foo.vbproj"), extract_csproj), (Path("foo.razor"), extract_razor), (Path("foo.cshtml"), extract_razor), (Path("foo.pas"), extract_pascal), (Path("foo.dfm"), extract_delphi_form)]
    for path, expected in dispatch_cases:
        if _get_extractor(path) is not expected:
            failures.append(f"dispatch mismatch for {path}")
    for ext in [".sln", ".csproj", ".fsproj", ".vbproj", ".razor", ".cshtml", ".pas", ".pp", ".dpr", ".lpr", ".lfm", ".lpk", ".dfm", ".astro"]:
        if ext not in CODE_EXTENSIONS:
            failures.append(f"CODE_EXTENSIONS missing {ext}")
    import graph3d.extract as extract_mod
    calls = {"parallel": 0, "sequential": 0}
    real_sequential = extract_mod._extract_sequential
    real_parallel = extract_mod._extract_parallel
    def fake_parallel(*args, **kwargs):
        calls["parallel"] += 1
        return False
    def wrapped_sequential(*args, **kwargs):
        calls["sequential"] += 1
        return real_sequential(*args, **kwargs)
    monkeypatch.setattr(extract_mod, "_extract_parallel", fake_parallel)
    monkeypatch.setattr(extract_mod, "_extract_sequential", wrapped_sequential)
    fallback = extract_mod.extract([FIXTURES / "sample.py"] * 25, cache_root=tmp_path / "fallback-cache")
    if calls != {"parallel": 1, "sequential": 1} or not fallback["nodes"]:
        failures.append(f"parallel fallback failed: {calls}")
    monkeypatch.setattr(extract_mod, "_extract_parallel", real_parallel)
    import concurrent.futures
    from concurrent.futures.process import BrokenProcessPool
    class FakePool:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def submit(self, *args, **kwargs): raise BrokenProcessPool("simulated spawn failure")
    monkeypatch.setattr(concurrent.futures, "ProcessPoolExecutor", lambda *args, **kwargs: FakePool())
    ok = extract_mod._extract_parallel([(0, FIXTURES / "sample.py")], [None], tmp_path, 2, 1)
    out = capsys.readouterr().out
    if ok is not False or "BrokenProcessPool" not in out or "__main__" not in out:
        failures.append("BrokenProcessPool fallback warning changed")
    fake_ts = type(sys)("tree_sitter")
    fake_ts.Language = lambda *a, **k: (_ for _ in ()).throw(TypeError("missing 1 required positional argument: 'name'"))
    fake_ts.Parser = None
    fake_lang = type(sys)("fake_ts_lang")
    fake_lang.language = lambda: object()
    monkeypatch.setitem(sys.modules, "tree_sitter", fake_ts)
    monkeypatch.setitem(sys.modules, "fake_ts_lang", fake_lang)
    from graph3d.extract import LanguageConfig, _extract_generic
    error_result = _extract_generic(Path("dummy.txt"), LanguageConfig(ts_module="fake_ts_lang", ts_language_fn="language"))
    if "error" not in error_result or "tree-sitter version mismatch" not in error_result["error"] or "pip install --upgrade" not in error_result["error"]:
        failures.append(f"tree-sitter mismatch hint changed: {error_result}")
    expected_edge = {"source": "source_node", "target": "target_node", "relation": "references", "context": "parameter_type", "confidence": "EXTRACTED", "source_file": "/repo/src/Foo.cs", "source_location": "L12", "weight": 1.0}
    if _semantic_reference_edge("source_node", "target_node", "parameter_type", "/repo/src/Foo.cs", 12) != expected_edge:
        failures.append("semantic reference edge shape changed")
    assert not failures, failures


def test_source_specific_edge_cases(tmp_path):
    failures = []
    js_scope = extract_js(_write(tmp_path / "scope_guard.js", "describe('suite', () => {\n  const inner = new Set([1, 2, 3]);\n  let other = [1, 2];\n});\nconst moduleConst = new Set([4, 5]);\nexport const exportedConst = { a: 1 };\n"))
    labels = _labels(js_scope)
    if "inner" in labels or "other" in labels or "moduleConst" not in labels or "exportedConst" not in labels:
        failures.append(f"js local const scope guard labels={labels}")
    arrow = extract_js(_write(tmp_path / "arrows.js", "function helper() { return 1; }\nconst handler = () => {\n  helper();\n};\n"))
    if not any("handler" in label for label in _labels(arrow)) or "calls" not in _relations(arrow):
        failures.append("module-level arrow function not extracted with calls")
    ts_scope = extract_js(_write(tmp_path / "scope_guard.ts", "describe('suite', () => {\n  const inner: Set<number> = new Set([1, 2]);\n});\nexport const topLevel = { a: 1 };\n"))
    labels = _labels(ts_scope)
    if "inner" in labels or "topLevel" not in labels:
        failures.append(f"ts local const scope guard labels={labels}")
    cjs = extract_js(FIXTURES / "cjs_require.js")
    cjs_targets = [e["target"] for e in cjs["edges"] if e["relation"] == "imports_from"]
    for target in ["foundation", "utils", "helpers"]:
        if not any(target in item for item in cjs_targets):
            failures.append(f"cjs require missing imports_from {target}: {cjs_targets}")
    if not all(e["confidence"] == "EXTRACTED" for e in cjs["edges"] if e["relation"] == "imports_from"):
        failures.append("cjs require imports_from confidence changed")
    sym_targets = [e["target"] for e in cjs["edges"] if e["relation"] == "imports"]
    for expected in [_make_id(_file_stem(FIXTURES / "foundation.js"), "loadFoundation"), _make_id(_file_stem(FIXTURES / "foundation.js"), "validateConfig"), _make_id(_file_stem(FIXTURES / "helpers.js"), "helperFn")]:
        if expected not in sym_targets:
            failures.append(f"cjs require missing symbol target {expected}")
    barrel = extract_js(FIXTURES / "barrel_reexport.ts")
    reexports = [e for e in barrel["edges"] if e["relation"] == "re_exports"]
    targets = [e["target"] for e in reexports]
    if len(reexports) < 4 or not all(e.get("context") == "re-export" and e["confidence"] == "EXTRACTED" for e in reexports):
        failures.append(f"barrel reexport edge metadata changed: {reexports}")
    for target in ["readcookie", "writecookie", "getfullurl", "basepathrewrite"]:
        if not any(target in item for item in targets):
            failures.append(f"barrel missing target {target}: {targets}")
    import_targets = [e["target"] for e in barrel["edges"] if e["relation"] == "imports_from"]
    for target in ["cookiehelpers", "urlhelpers", "storagehelpers"]:
        if not any(target in item for item in import_targets):
            failures.append(f"barrel missing imports_from {target}: {import_targets}")
    if not any(label in _labels(barrel) for label in ["localHelper()", "localHelper"]) or not any("barrel_reexport" in n["label"] for n in barrel["nodes"]):
        failures.append("barrel local export or file node missing")
    pure = extract_js(_write(tmp_path / "pure_export.ts", "const x = 1;\nexport { x };\n"))
    if [e for e in pure["edges"] if e["relation"] == "re_exports"]:
        failures.append("pure export emitted re_exports")
    markdown = extract_markdown(FIXTURES / "deploy_guide.md")
    if any(label.startswith("code:") for label in _labels(markdown)) or len(_edges(markdown, "contains")) < 5:
        failures.append("markdown fenced code/contains behavior changed")
    fenced = extract_markdown(_write(tmp_path / "fenced.md", "# Real Heading\n\n```bash\n## Not A Heading\necho hello\n```\n\n## Another Real Heading\n"))
    labels = _labels(fenced)
    if not any("Real Heading" in label for label in labels) or not any("Another Real Heading" in label for label in labels) or any("Not A Heading" in label for label in labels):
        failures.append(f"markdown fenced heading labels={labels}")
    bash_cases = [
        ("command_substitution.sh", "#!/usr/bin/env bash\nbuild() { echo build; }\n$(build)\n", []),
        ("process_substitution.sh", "#!/usr/bin/env bash\nhelper() { echo h; }\ndiff <(helper) <(helper)\n", []),
        ("shadowing.sh", "#!/usr/bin/env bash\ninstall() { echo install; }\ndeploy() { install; }\n", [("deploy()", "install()")]),
        ("nested.sh", "#!/usr/bin/env bash\nfunction do_work() { :; }\nfunction outer() {\nfunction inner() {\ndo_work\n}\ninner\n}\n", [("inner()", "do_work()")]),
    ]
    for name, source, expected in bash_cases:
        calls = _call_pairs(extract_bash(_write(tmp_path / name, source)))
        if expected:
            failures += [f"bash {name} missing call {pair}: {calls}" for pair in expected if pair not in calls]
        elif calls:
            failures.append(f"bash {name} emitted unwanted calls {calls}")
    source_shadow = extract_bash(_write(tmp_path / "run.sh", "#!/usr/bin/env bash\nfunction source() { echo custom; }\nsource ./helpers.sh\n"))
    if [e for e in source_shadow["edges"] if e["relation"] == "imports_from"]:
        failures.append("bash user-defined source emitted imports_from")
    entry = extract_bash(_write(tmp_path / "with_entrypoint.sh", "#!/usr/bin/env bash\nfoo() { :; }\n"))
    kinds = [n.get("metadata", {}).get("kind") for n in entry["nodes"]]
    if "bash_entrypoint" not in kinds or "file" not in kinds:
        failures.append(f"bash entrypoint kinds={kinds}")
    collision = extract_bash(_write(tmp_path / "deploy.sh", "#!/usr/bin/env bash\nfunction script() { echo hi; }\n"))
    entries = [n for n in collision["nodes"] if n.get("metadata", {}).get("kind") == "bash_entrypoint"]
    funcs = [n for n in collision["nodes"] if n.get("metadata", {}).get("kind") == "bash_function"]
    if not entries or not funcs or entries[0]["id"] == funcs[0]["id"]:
        failures.append(f"bash entrypoint collision entries={entries} funcs={funcs}")
    top = extract_bash(_write(tmp_path / "top_level_call.sh", "#!/usr/bin/env bash\nbuild() { echo build; }\nbuild\n"))
    entry_node = next((n for n in top["nodes"] if n.get("metadata", {}).get("kind") == "bash_entrypoint"), None)
    build_id = next((n["id"] for n in top["nodes"] if n["label"] == "build()"), None)
    if entry_node is None or build_id is None or not any(e["source"] == entry_node["id"] and e["target"] == build_id for e in top["edges"] if e["relation"] == "calls"):
        failures.append("bash top-level call was not attributed to entrypoint")
    import builtins
    real_import = builtins.__import__
    def patched_import(name, *args, **kwargs):
        if name == "tree_sitter_bash":
            raise ImportError("mocked")
        return real_import(name, *args, **kwargs)
    with patch("builtins.__import__", side_effect=patched_import):
        missing = extract_bash(FIXTURES / "sample.sh")
    if "error" not in missing or missing["nodes"] != []:
        failures.append(f"bash missing grammar result={missing}")
    for node in extract_bash(FIXTURES / "sample.sh")["nodes"]:
        for value in node.get("metadata", {}).values():
            if isinstance(value, str) and ("<" in value or "\x00" in value):
                failures.append(f"bash unsafe metadata {value!r}")
    bad_json = extract_json(_write(tmp_path / "broken.json", "{this is not: valid json!!!"))
    if not isinstance(bad_json, dict) or "nodes" not in bad_json:
        failures.append("invalid JSON did not return result dict")
    big_json = extract_json(_write(tmp_path / "big.json", b'{"x":"' + b"a" * 1_048_576 + b'"}'))
    if "error" not in big_json or big_json["nodes"] != []:
        failures.append("large JSON was not skipped")
    if any(e["source"] == e["target"] for e in extract_json(FIXTURES / "sample.json")["edges"]):
        failures.append("JSON self-loop emitted")
    if not [e for e in extract_json(FIXTURES / "sample_tsconfig.json")["edges"] if e["relation"] == "extends" and e.get("context") == "import"]:
        failures.append("JSON tsconfig extends edge missing")
    if _TSX_CONFIG.ts_language_fn != "language_tsx" or _TS_CONFIG.ts_language_fn != "language_typescript":
        failures.append("TSX grammar config changed")
    dart_file = _write(tmp_path / "mydir" / "sample.dart", "class MyClass {}\nvoid myFunc() {}\n")
    dart = extract_dart(dart_file)
    node_ids = {n["id"] for n in dart["nodes"]}
    stem = _file_stem(dart_file)
    for expected in [_make_id(stem, "MyClass"), _make_id(stem, "myFunc")]:
        if expected not in node_ids:
            failures.append(f"Dart missing stem-based id {expected}: {node_ids}")
    if "error" not in extract_csproj(_write(tmp_path / "bad.csproj", "<Project><Invalid></Project>")):
        failures.append("invalid csproj did not return error")
    if "error" not in extract_razor(tmp_path / "missing.razor"):
        failures.append("missing razor did not return error")
    binary = extract_delphi_form(_write(tmp_path / "binary.dfm", b"\xff\x0a\x00\x00some binary data"))
    if binary["nodes"] != [] or binary["edges"] != [] or "error" not in binary:
        failures.append(f"binary DFM result={binary}")
    assert not failures, failures


def test_inheritance_astro_sql_and_go_guards(tmp_path):
    failures = []
    def has_edge(result, src_file, src_sym, tgt_file, tgt_sym, relation="inherits"):
        source = _make_id(_file_stem(Path(src_file)), src_sym)
        target = _make_id(_file_stem(Path(tgt_file)), tgt_sym)
        return any((e["source"], e["target"], e["relation"]) == (source, target, relation) for e in result["edges"])
    ts_cases = [
        ({"src/a.ts": "export interface Base { x: number; }\nexport interface Derived extends Base { y: number; }\n"}, [("src/a.ts", "Derived", "src/a.ts", "Base", "inherits")]),
        ({"src/a.ts": "interface A { a: number; }\ninterface B { b: number; }\ninterface M extends A, B { m: number; }\n"}, [("src/a.ts", "M", "src/a.ts", "A", "inherits"), ("src/a.ts", "M", "src/a.ts", "B", "inherits")]),
        ({"src/a.ts": "class Animal {}\nclass Dog extends Animal {}\n"}, [("src/a.ts", "Dog", "src/a.ts", "Animal", "inherits")]),
        ({"src/a.ts": "interface Base<T> { x: T; }\ninterface G extends Base<number> { y: number; }\n"}, [("src/a.ts", "G", "src/a.ts", "Base", "inherits")]),
        ({"src/a.ts": "import { Imported } from './b';\nexport interface D extends Imported { d: number; }\n", "src/b.ts": "export interface Imported { z: number; }\n"}, [("src/a.ts", "D", "src/b.ts", "Imported", "inherits")]),
        ({"src/a.ts": "import { Imported } from './b';\nclass Cat extends Imported {}\n", "src/b.ts": "export class Imported {}\n"}, [("src/a.ts", "Cat", "src/b.ts", "Imported", "inherits")]),
        ({"src/a.ts": "interface Walker { walk(): void; }\nclass Person implements Walker { walk() {} }\n"}, [("src/a.ts", "Person", "src/a.ts", "Walker", "implements")]),
    ]
    for index, (files_by_rel, expected_edges) in enumerate(ts_cases):
        root = tmp_path / f"ts{index}"
        files = [_write(root / rel, source) for rel, source in files_by_rel.items()]
        result = extract(files, cache_root=tmp_path / f"ts-cache-{index}")
        for edge in expected_edges:
            if not has_edge(result, *edge):
                failures.append(f"TypeScript inheritance missing {edge}: {result['edges']}")
    astro_cases = []
    page = _write(tmp_path / "astro1" / "src" / "pages" / "index.astro", "---\nimport Layout from '../layouts/Layout.astro';\nimport Hero from '../components/Hero.astro';\n---\n<Layout><Hero /></Layout>\n")
    layout = _write(tmp_path / "astro1" / "src" / "layouts" / "Layout.astro", "---\n---\n<slot />\n")
    hero = _write(tmp_path / "astro1" / "src" / "components" / "Hero.astro", "---\n---\n<h1>hi</h1>\n")
    astro_cases.append((page, "imports_from", {_make_id(str(layout)), _make_id(str(hero))}))
    page = _write(tmp_path / "astro2" / "src" / "pages" / "lazy.astro", "---\nconst Mod = await import('./Other.astro');\n---\n<div>{Mod.default}</div>\n")
    other = _write(tmp_path / "astro2" / "src" / "pages" / "Other.astro", "---\n---\n<p>o</p>\n")
    astro_cases.append((page, "dynamic_import", {_make_id(str(other))}))
    page = _write(tmp_path / "astro3" / "src" / "pages" / "with-script.astro", "---\nimport Layout from '../layouts/Layout.astro';\n---\n<Layout></Layout>\n<script>import { hydrate } from '../client/hydrate.ts'; hydrate();</script>\n")
    layout = _write(tmp_path / "astro3" / "src" / "layouts" / "Layout.astro", "---\n---\n<slot />\n")
    hydrate = _write(tmp_path / "astro3" / "src" / "client" / "hydrate.ts", "export function hydrate(){}\n")
    astro_cases.append((page, "imports_from", {_make_id(str(layout)), _make_id(str(hydrate))}))
    _write(tmp_path / "astro4" / "tsconfig.json", '{"compilerOptions":{"baseUrl":".","paths":{"@components/*":["src/components/*"]}}}\n')
    page = _write(tmp_path / "astro4" / "src" / "pages" / "alias.astro", "---\nimport Hero from '@components/Hero.astro';\n---\n<Hero />\n")
    hero = _write(tmp_path / "astro4" / "src" / "components" / "Hero.astro", "---\n---\n<h1>h</h1>\n")
    astro_cases.append((page, "imports_from", {_make_id(str(hero))}))
    plain = extract_astro(_write(tmp_path / "astro5" / "src" / "pages" / "plain.astro", "<h1>no frontmatter here</h1>\n"))
    if not isinstance(plain, dict) or {e["target"] for e in plain.get("edges", []) if e["relation"] == "imports_from"}:
        failures.append(f"Astro plain result changed: {plain}")
    for page, relation, expected in astro_cases:
        targets = {e["target"] for e in extract_astro(page)["edges"] if e["relation"] == relation}
        missing = expected - targets
        if missing:
            failures.append(f"Astro missing {relation} targets {missing}; got {targets}")
    pytest.importorskip("tree_sitter_sql")
    for name, result, expected_labels, expected_relations in [
        ("sample", extract_sql(FIXTURES / "sample.sql"), ["users", "organizations", "active_users", "get_user"], {"references", "reads_from"}),
        ("alter_fk", extract_sql(FIXTURES / "sample_alter_fk.sql"), [], {"references"}),
        ("schema", extract_sql(FIXTURES / "sample_schema_qualified.sql"), ["Sales.Customer", "Sales.SalesOrder"], {"references"}),
    ]:
        labels = _labels(result)
        failures += [f"SQL {name} missing label {x}: {labels}" for x in expected_labels if not any(x in label for label in labels)]
        if expected_relations - _relations(result):
            failures.append(f"SQL {name} missing relations {expected_relations - _relations(result)}")
        failures += _dangling(result, f"SQL {name}", {"references", "reads_from", "contains"})
    tree = ast.parse(inspect.getsource(extract_go))
    def find_branch(root, literal):
        for child in ast.walk(root):
            if isinstance(child, ast.If) and isinstance(child.test, ast.Compare) and isinstance(child.test.left, ast.Name) and child.test.left.id == "t" and len(child.test.comparators) == 1 and isinstance(child.test.comparators[0], ast.Constant) and child.test.comparators[0].value == literal:
                return child
        return None
    def early(stmt):
        return isinstance(stmt, ast.If) and isinstance(stmt.test, ast.UnaryOp) and isinstance(stmt.test.op, ast.Not) and isinstance(stmt.test.operand, ast.Name) and stmt.test.operand.id == "name_node" and any(isinstance(x, (ast.Return, ast.Raise, ast.Continue, ast.Break)) for x in stmt.body)
    def guarded(branch, var_name):
        parents = {}
        for parent in ast.walk(branch):
            for child in ast.iter_child_nodes(parent):
                parents[id(child)] = parent
        def chain(start):
            out = []
            cur = start
            while cur is not None:
                parent = parents.get(id(cur))
                if parent is None:
                    break
                if isinstance(cur, ast.stmt):
                    for attr in ("body", "orelse", "finalbody"):
                        siblings = getattr(parent, attr, None)
                        if isinstance(siblings, list) and cur in siblings:
                            out.append((cur, siblings))
                            break
                cur = parent
            return out
        def is_guarded(use):
            for stmt, siblings in chain(use):
                parent = parents.get(id(stmt))
                if isinstance(parent, ast.If) and isinstance(parent.test, ast.Name) and parent.test.id == "name_node" and stmt in parent.body:
                    return True
                if any(early(item) for item in siblings[:siblings.index(stmt)]):
                    return True
            return False
        return all(is_guarded(n) for n in ast.walk(branch) if isinstance(n, ast.Name) and n.id == var_name)
    method_branch = find_branch(tree, "method_declaration")
    function_branch = find_branch(tree, "function_declaration")
    if method_branch is None or function_branch is None or not guarded(method_branch, "method_nid") or not guarded(function_branch, "func_nid"):
        failures.append("Go method/function name_node guard changed")
    bad_branch = find_branch(ast.parse("def walk(node):\n    if t == 'method_declaration':\n        name_node = node.child_by_field_name('name')\n        if name_node:\n            method_nid = make_id('x')\n        emit_go_method_refs(node, method_nid, 1)\n        return\n"), "method_declaration")
    if bad_branch is None or guarded(bad_branch, "method_nid"):
        failures.append("Go guard negative control failed")
    crate_result = extract([FIXTURES / "crate_a" / "src" / "lib.rs", FIXTURES / "crate_b" / "src" / "lib.rs"], cache_root=tmp_path / "crate-cache")
    node_ids_a = {n["id"] for n in crate_result["nodes"] if "crate_a" in (n.get("source_file") or "")}
    node_ids_b = {n["id"] for n in crate_result["nodes"] if "crate_b" in (n.get("source_file") or "")}
    cross = [e for e in crate_result["edges"] if e["relation"] == "calls" and e["source"] in node_ids_b and e["target"] in node_ids_a]
    if cross:
        failures.append(f"Rust cross-crate calls emitted: {cross}")
    assert not failures, failures


def test_dotnet_pascal_project_and_form_details():
    failures = []
    sln = extract_sln(FIXTURES / "sample.sln")
    if set(["WebApi", "Domain", "Tests"]) - set(_labels(sln)) or len(_edges(sln, "contains")) != 3 or "imports" not in _relations(sln):
        failures.append(f"sln details changed: labels={_labels(sln)} edges={sln['edges']}")
    csproj = extract_csproj(FIXTURES / "sample.csproj")
    if len(_edges(csproj, "imports")) != 6:
        failures.append(f"csproj expected 6 imports: {csproj['edges']}")
    razor = extract_razor(FIXTURES / "sample.razor")
    import_targets = {e["target"] for e in _edges(razor, "imports")}
    call_targets = {e["target"] for e in _edges(razor, "calls")}
    if not any("microsoft" in t for t in import_targets) or not any("counterservice" in t.lower() for t in import_targets):
        failures.append(f"razor missing using/inject imports {import_targets}")
    if not any("weatherdisplay" in t for t in call_targets) or not any("datagrid" in t for t in call_targets):
        failures.append(f"razor missing component calls {call_targets}")
    pascal = extract_pascal(FIXTURES / "sample.pas")
    if not all(e["confidence"] == "EXTRACTED" for e in pascal["edges"] if e["relation"] in {"contains", "method", "inherits", "imports"}):
        failures.append("pascal structural confidence changed")
    node_by_id = {n["id"]: n["label"] for n in pascal["nodes"]}
    if not any("TDataProcessor" in node_by_id.get(e["source"], "") for e in _edges(pascal, "inherits")):
        failures.append("pascal TDataProcessor inheritance missing")
    for ext in [".pas", ".pp", ".dpr", ".dpk", ".lpr", ".inc", ".lfm", ".lpk", ".dfm"]:
        if ext not in _DISPATCH:
            failures.append(f"pascal dispatch missing {ext}")
    for ext in [".pas", ".pp", ".dpr", ".lpr", ".lfm", ".lpk", ".dfm"]:
        if ext not in CODE_EXTENSIONS:
            failures.append(f"pascal detect missing {ext}")
    for name, result in [("pascal", pascal), ("lfm", extract_lazarus_form(FIXTURES / "sample.lfm")), ("lpk", extract_lazarus_package(FIXTURES / "sample.lpk")), ("dfm", extract_delphi_form(FIXTURES / "sample.dfm")), ("razor", razor)]:
        failures += _dangling(result, name, {"contains", "method", "inherits", "calls", "references"})
    assert not failures, failures


def test_devin_installation_and_platform_config(tmp_path, monkeypatch, capsys):
    failures = []
    def skill_user(home):
        return home / ".config" / "devin" / "skills" / "graph3d" / "SKILL.md"
    def skill_project(project):
        return project / ".devin" / "skills" / "graph3d" / "SKILL.md"
    def rules(project):
        return project / ".windsurf" / "rules" / "graph3d.md"
    from graph3d.__main__ import _PLATFORM_CONFIG, _devin_rules_install, _devin_rules_uninstall, _platform_skill_destination, _remove_skill_file, install, main
    old_cwd = Path.cwd()
    try:
        monkeypatch.chdir(tmp_path)
        with patch("graph3d.__main__.Path.home", return_value=tmp_path):
            install(platform="devin")
        path = skill_user(tmp_path)
        if not path.exists():
            failures.append("devin user skill missing")
        else:
            content = path.read_text(encoding="utf-8")
            for expected in ["name: graph3d", "argument-hint:", "triggers:", "graph3d query"]:
                if expected not in content:
                    failures.append(f"devin user skill missing {expected}")
        if rules(tmp_path).exists():
            failures.append("devin user install wrote project rules")
        with patch("graph3d.__main__.Path.home", return_value=tmp_path):
            _remove_skill_file("devin")
        if path.exists():
            failures.append("devin user uninstall left skill")
        with patch("graph3d.__main__.Path.home", return_value=tmp_path):
            monkeypatch.setattr(sys, "argv", ["graph3d", "devin", "uninstall"])
            main()
        if "nothing to remove" not in capsys.readouterr().out:
            failures.append("devin user uninstall noop message missing")
    finally:
        monkeypatch.chdir(old_cwd)
    project = tmp_path / "project"
    home = tmp_path / "home"
    project.mkdir()
    monkeypatch.chdir(project)
    with patch("graph3d.__main__.Path.home", return_value=home):
        monkeypatch.setattr(sys, "argv", ["graph3d", "devin", "install", "--project"])
        main()
    if not skill_project(project).exists() or skill_user(home).exists():
        failures.append("devin project install wrote wrong skill scope")
    if not rules(project).exists() or "graph3d" not in rules(project).read_text(encoding="utf-8") or "GRAPH_REPORT.md" not in rules(project).read_text(encoding="utf-8"):
        failures.append("devin project rules missing expected content")
    if "git add" not in capsys.readouterr().out:
        failures.append("devin project install missing git add hint")
    with patch("graph3d.__main__.Path.home", return_value=home):
        monkeypatch.setattr(sys, "argv", ["graph3d", "devin", "uninstall", "--project"])
        main()
    if skill_project(project).exists() or rules(project).exists():
        failures.append("devin project uninstall left files")
    user_skill = skill_user(home)
    user_skill.parent.mkdir(parents=True, exist_ok=True)
    user_skill.write_text("user skill", encoding="utf-8")
    with patch("graph3d.__main__.Path.home", return_value=home):
        monkeypatch.setattr(sys, "argv", ["graph3d", "devin", "install", "--project"])
        main()
        monkeypatch.setattr(sys, "argv", ["graph3d", "devin", "uninstall", "--project"])
        main()
    if not user_skill.exists():
        failures.append("devin project uninstall touched user scope")
    _devin_rules_install(tmp_path)
    first = rules(tmp_path).read_text(encoding="utf-8")
    _devin_rules_install(tmp_path)
    if first != rules(tmp_path).read_text(encoding="utf-8") or "no change" not in capsys.readouterr().out:
        failures.append("devin rules install not idempotent")
    _devin_rules_uninstall(tmp_path / "empty")
    import graph3d
    packaged = Path(graph3d.__file__).parent / "skill-devin.md"
    if not packaged.exists():
        failures.append("skill-devin.md missing")
    else:
        skill = packaged.read_text(encoding="utf-8")
        if '.graph3d_python) -c "' not in skill or "#!/bin/bash" in skill or "triggers:" not in skill or "model" not in skill:
            failures.append("skill-devin.md content changed")
    if "devin" not in _PLATFORM_CONFIG or _PLATFORM_CONFIG["devin"]["skill_file"] != "skill-devin.md" or _PLATFORM_CONFIG["devin"]["claude_md"] is not False:
        failures.append(f"devin platform config changed: {_PLATFORM_CONFIG.get('devin')}")
    with patch("graph3d.__main__.Path.home", return_value=tmp_path):
        if _platform_skill_destination("devin", project=False) != skill_user(tmp_path):
            failures.append("devin user destination changed")
    if _platform_skill_destination("devin", project=True, project_dir=tmp_path) != skill_project(tmp_path):
        failures.append("devin project destination changed")
    monkeypatch.setattr(sys, "argv", ["graph3d", "--help"])
    main()
    help_text = capsys.readouterr().out
    if not ("|devin)" in help_text or "|devin |" in help_text or "|devin" in help_text) or "devin install" not in help_text or "devin uninstall" not in help_text or "~/.config/devin" not in help_text:
        failures.append("devin help missing entries")
    if "devin install" in help_text and "--project" in help_text.split("devin install", 1)[1].split("\n\n", 1)[0]:
        failures.append("devin help unexpectedly documents --project")
    assert not failures, failures


def test_encoding_and_charmap_behaviors(tmp_path, monkeypatch, capsys):
    failures = []
    envelope = {"type": "result", "subtype": "success", "is_error": False, "result": json.dumps({"nodes": [{"id": "n1", "label": "N1", "file_type": "document", "source_file": "u.md"}], "edges": [], "hyperedges": [], "input_tokens": 0, "output_tokens": 0}), "stop_reason": "end_turn", "usage": {"input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}, "modelUsage": {"claude-opus-4-7": {"inputTokens": 1, "outputTokens": 1}}}
    completed = MagicMock(returncode=0, stdout=json.dumps(envelope), stderr="")
    monkeypatch.setattr(llm, "_response_is_hollow", lambda raw, parsed: False)
    with patch("shutil.which", return_value="C:\\fake\\bin\\claude"), patch("subprocess.run", return_value=completed) as mock_run:
        llm._call_claude_cli(UNICODE_CONTENT, max_tokens=8192)
    kwargs = mock_run.call_args.kwargs
    if kwargs.get("encoding") != "utf-8" or (kwargs.get("text") is not True and not isinstance(kwargs.get("input"), bytes)):
        failures.append(f"_call_claude_cli bad subprocess kwargs {kwargs}")
    unicode_file = _write(tmp_path / "unicode_chunk.md", UNICODE_CONTENT + " Threshold: \u2265 95%.")
    with patch("shutil.which", return_value="C:\\fake\\bin\\claude"), patch("subprocess.run", return_value=completed) as mock_run:
        direct = llm.extract_files_direct(files=[unicode_file], backend="claude-cli", root=tmp_path)
    kwargs = mock_run.call_args.kwargs
    if kwargs.get("encoding") != "utf-8" or not direct["nodes"] or not any(ch in kwargs.get("input", "") for ch in ["\u2192", "\u2705", "\u2265"]):
        failures.append(f"extract_files_direct bad kwargs/result {kwargs} {direct}")
    completed_llm = MagicMock(returncode=0, stdout=json.dumps({"result": "ok", "stop_reason": "end_turn"}), stderr="")
    with patch("shutil.which", return_value="C:\\fake\\bin\\claude"), patch("subprocess.run", return_value=completed_llm) as mock_run:
        llm._call_llm(UNICODE_CONTENT, backend="claude-cli", max_tokens=200)
    if mock_run.call_args.kwargs.get("encoding") != "utf-8":
        failures.append("_call_llm missing utf-8 encoding")
    prompt = llm._read_files([unicode_file], root=tmp_path)
    if "\u2192" not in prompt:
        failures.append("_read_files lost unicode content")
    try:
        prompt.encode("utf-8")
    except UnicodeEncodeError as exc:
        failures.append(f"UTF-8 encode failed: {exc}")
    try:
        prompt.encode("cp1252")
        failures.append("cp1252 encode unexpectedly succeeded")
    except UnicodeEncodeError:
        pass
    files = [_write(tmp_path / f"f{i}.py", f"x = {i}\n") for i in range(3)]
    monkeypatch.setattr(llm, "_extract_with_adaptive_retry", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("charmap error")))
    failed = llm.extract_corpus_parallel(files, backend="claude-cli")
    captured = capsys.readouterr()
    if failed.get("failed_chunks", 0) <= 0 or "failed" not in captured.err.lower():
        failures.append(f"chunk failure reporting changed: {failed} stderr={captured.err!r}")
    good = {"nodes": [{"id": "n1", "label": "N1", "file_type": "code", "source_file": str(files[0])}], "edges": [], "hyperedges": [], "input_tokens": 1, "output_tokens": 1, "elapsed_seconds": 0.1}
    monkeypatch.setattr(llm, "_extract_with_adaptive_retry", lambda *args, **kwargs: good)
    succeeded = llm.extract_corpus_parallel([files[0]], backend="claude-cli")
    captured = capsys.readouterr()
    if succeeded.get("failed_chunks", 0) != 0 or ("WARNING:" in captured.err and "0/" not in captured.err):
        failures.append(f"chunk success reporting changed: {succeeded} stderr={captured.err!r}")
    assert not failures, failures


def test_native_pdf_engine(tmp_path):
    """graph3d.pdf is a from-scratch PDF reader (no third-party PDF library):
    object tokenizer, classic xref tables, xref streams + object streams
    (PDF 1.5+), FlateDecode, page-tree traversal, simple-font encodings
    (WinAnsi/Differences) and Type0/ToUnicode CMap text decoding, plus the
    document-intelligence layer (summary/structure/search/tables/markdown)."""
    failures = []

    # -- structural cases: (fixture, expected substrings in extracted text, expected page count)
    case_table = [
        ("sample.pdf", ["Hello World", "Second line: caf\u00e9"], 1),
        ("sample_multipage.pdf", ["Page one content", "Page two content"], 2),
        ("sample_flate.pdf", ["Compressed content stream"], 1),
        ("sample_cidfont.pdf", ["Hij"], 1),  # Identity-H codes decoded via ToUnicode bfchar/bfrange
    ]
    for fixture, expected_substrings, expected_pages in case_table:
        path = FIXTURES / fixture
        pages = g3pdf.extract_pages(path)
        if len(pages) != expected_pages:
            failures.append(f"{fixture}: expected {expected_pages} pages, got {len(pages)}")
        full_text = g3pdf.extract_text(path)
        for expected in expected_substrings:
            if expected not in full_text:
                failures.append(f"{fixture}: missing {expected!r} in {full_text!r}")
        if g3pdf.get_page_count(path) != expected_pages:
            failures.append(f"{fixture}: get_page_count mismatch")

    # -- metadata: Info dict values decode as plain str, not raw PDF bytes
    meta = g3pdf.extract_metadata(FIXTURES / "sample.pdf")
    if not isinstance(meta["pages"], int) or meta["pages"] != 1:
        failures.append(f"extract_metadata pages wrong: {meta}")

    # -- document-intelligence layer, ported from Darbot PDF Viewer MCP
    # (github.com/darbotlabs/Darbot-PDF-Viewer-MCP), operating on real page
    # boundaries rather than that tool's form-feed-splitting fallback.
    summary = g3pdf.get_summary(FIXTURES / "sample_multipage.pdf")
    if "Pages: 2" not in summary or "Page one content" not in summary:
        failures.append(f"get_summary missing expected content: {summary!r}")

    structure = g3pdf.analyze_structure(FIXTURES / "sample_multipage.pdf")
    if structure["pages"] != 2 or structure["total_words"] < 4:
        failures.append(f"analyze_structure looks wrong: {structure}")

    doctype_cases = [
        ("An abstract of this paper. See references [1].", "academic_paper"),
        ("Invoice #123. Amount due: $50.", "invoice"),
        ("plain body text with nothing special", "general_document"),
    ]
    for text, expected in doctype_cases:
        got = g3pdf.detect_document_type(text)
        if got != expected:
            failures.append(f"detect_document_type({text!r}) = {got!r}, expected {expected!r}")

    hits = g3pdf.search_text(FIXTURES / "sample_multipage.pdf", "content")
    if len(hits) != 2 or hits[0]["page"] != 1 or hits[1]["page"] != 2:
        failures.append(f"search_text wrong hits: {hits}")

    markdown = g3pdf.to_markdown(FIXTURES / "sample.pdf")
    if not markdown.startswith("# ") or "Hello World" not in markdown:
        failures.append(f"to_markdown missing expected structure: {markdown!r}")

    # -- robustness: malformed input must degrade gracefully, never crash
    bad_path = tmp_path / "not_really_a_pdf.pdf"
    bad_path.write_bytes(b"this is not a PDF file at all")
    if g3pdf.extract_text(bad_path) != "":
        failures.append("extract_text should return '' for a non-PDF file")
    truncated = tmp_path / "truncated.pdf"
    truncated.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog")
    doc = g3pdf.Document(truncated.read_bytes())
    if doc.pages() != []:
        failures.append("truncated PDF should recover to an empty page list, not crash")

    # -- detect.py integration: the public entry point graph3d actually calls
    from graph3d.detect import extract_pdf_text
    if extract_pdf_text(FIXTURES / "sample.pdf") != g3pdf.extract_text(FIXTURES / "sample.pdf"):
        failures.append("detect.extract_pdf_text is no longer a thin wrapper over graph3d.pdf")

    assert not failures, failures


