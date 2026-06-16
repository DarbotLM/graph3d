from __future__ import annotations

from pathlib import Path

from graph3d.extractor_registry import ExtractorRegistry


def _fake_a(path: Path) -> dict:
    return {"nodes": [], "edges": [], "path": str(path)}


def _fake_b(path: Path) -> dict:
    return {"nodes": [], "edges": [], "path": str(path)}


def test_registry_registers_suffixes_with_or_without_dot():
    registry = ExtractorRegistry()

    assert registry.register_suffix("artifact", _fake_a) is _fake_a

    assert registry.lookup(Path("sample.artifact")) is _fake_a
    assert ".artifact" in set(registry.suffixes())


def test_registry_filename_predicates_override_suffix_lookup():
    registry = ExtractorRegistry({".json": _fake_a})

    registry.register_filename_predicate(
        lambda path: path.name == "special.json",
        _fake_b,
        name="special_json",
    )

    assert registry.lookup(Path("special.json")) is _fake_b
    assert registry.lookup(Path("package.json")) is _fake_a
    assert registry.filename_routes()[0].name == "special_json"


def test_registry_uses_backing_dispatch_mapping_for_compatibility():
    dispatch = {}
    registry = ExtractorRegistry(dispatch)

    registry.register_suffix(".foo", _fake_a)
    dispatch[".bar"] = _fake_b

    assert dispatch[".foo"] is _fake_a
    assert registry.lookup(Path("one.foo")) is _fake_a
    assert registry.lookup(Path("two.bar")) is _fake_b


def test_extract_module_preserves_existing_dispatch_priority():
    from graph3d.extract import _DISPATCH, _get_extractor, extract_blade, extract_json
    from graph3d.mcp_ingest import extract_mcp_config
    from graph3d.schema_paths import extract_sqlite_schema

    assert _DISPATCH[".json"] is extract_json
    assert _get_extractor(Path("package.json")) is extract_json
    assert _get_extractor(Path(".mcp.json")) is extract_mcp_config
    assert _get_extractor(Path("claude_desktop_config.json")) is extract_mcp_config
    assert _get_extractor(Path("component.blade.php")) is extract_blade
    assert _get_extractor(Path("events.sqlite")) is extract_sqlite_schema


def test_extract_module_suffix_helper_updates_dispatch_and_lookup():
    from graph3d.extract import _DISPATCH, _get_extractor, register_suffix_extractor

    old = _DISPATCH.get(".g3dtest")
    try:
        assert register_suffix_extractor(".g3dtest", _fake_a) is _fake_a
        assert _DISPATCH[".g3dtest"] is _fake_a
        assert _get_extractor(Path("artifact.g3dtest")) is _fake_a
    finally:
        if old is None:
            _DISPATCH.pop(".g3dtest", None)
        else:
            _DISPATCH[".g3dtest"] = old
