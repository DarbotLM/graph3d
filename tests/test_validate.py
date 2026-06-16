import pytest
from graph3d.validate import (
    assert_valid,
    validate_extraction,
    validate_graph_export,
    validate_provenance_metadata,
    validate_relation_endpoints,
    validate_schema_path_metadata,
    validate_source_refs,
)

VALID = {
    "nodes": [
        {"id": "n1", "label": "Foo", "file_type": "code", "source_file": "foo.py"},
        {"id": "n2", "label": "Bar", "file_type": "document", "source_file": "bar.md"},
    ],
    "edges": [
        {"source": "n1", "target": "n2", "relation": "references",
         "confidence": "EXTRACTED", "source_file": "foo.py", "weight": 1.0},
    ],
}

def test_valid_passes():
    assert validate_extraction(VALID) == []

def test_missing_nodes_key():
    errors = validate_extraction({"edges": []})
    assert any("nodes" in e for e in errors)

def test_missing_edges_key():
    errors = validate_extraction({"nodes": []})
    assert any("edges" in e for e in errors)

def test_not_a_dict():
    errors = validate_extraction([])
    assert len(errors) == 1

def test_invalid_file_type():
    data = {
        "nodes": [{"id": "n1", "label": "X", "file_type": "video", "source_file": "x.mp4"}],
        "edges": [],
    }
    errors = validate_extraction(data)
    assert any("file_type" in e for e in errors)

def test_invalid_confidence():
    data = {
        "nodes": [
            {"id": "n1", "label": "A", "file_type": "code", "source_file": "a.py"},
            {"id": "n2", "label": "B", "file_type": "code", "source_file": "b.py"},
        ],
        "edges": [
            {"source": "n1", "target": "n2", "relation": "calls",
             "confidence": "CERTAIN", "source_file": "a.py"},
        ],
    }
    errors = validate_extraction(data)
    assert any("confidence" in e for e in errors)

def test_dangling_edge_source():
    data = {
        "nodes": [{"id": "n1", "label": "A", "file_type": "code", "source_file": "a.py"}],
        "edges": [
            {"source": "missing_id", "target": "n1", "relation": "calls",
             "confidence": "EXTRACTED", "source_file": "a.py"},
        ],
    }
    errors = validate_extraction(data)
    assert any("source" in e and "missing_id" in e for e in errors)

def test_dangling_edge_target():
    data = {
        "nodes": [{"id": "n1", "label": "A", "file_type": "code", "source_file": "a.py"}],
        "edges": [
            {"source": "n1", "target": "ghost", "relation": "calls",
             "confidence": "EXTRACTED", "source_file": "a.py"},
        ],
    }
    errors = validate_extraction(data)
    assert any("target" in e and "ghost" in e for e in errors)

def test_missing_node_field():
    data = {
        "nodes": [{"id": "n1", "label": "A", "source_file": "a.py"}],  # missing file_type
        "edges": [],
    }
    errors = validate_extraction(data)
    assert any("file_type" in e for e in errors)

def test_assert_valid_raises_on_errors():
    with pytest.raises(ValueError, match="error"):
        assert_valid({"nodes": [], "edges": [], "oops": True, **{"nodes": "bad"}})

def test_assert_valid_passes_silently():
    assert_valid(VALID)  # should not raise


def test_validate_graph_export_accepts_legacy_node_link_json():
    legacy = {
        "directed": False,
        "multigraph": False,
        "graph": {},
        "nodes": [{"id": "n1", "label": "Legacy"}],
        "links": [],
    }
    assert validate_graph_export(legacy) == []


def test_validate_graph_export_checks_source_summary_refs():
    data = {
        "nodes": [{"id": "n1", "label": "A", "file_type": "code", "source_file": "a.py"}],
        "links": [],
        "graph3d_metadata": {
            "source_documents": {
                "source_files": [],
                "source_file_count": 0,
                "file_type_counts": {"code": 1},
            }
        },
    }
    errors = validate_graph_export(data)
    assert any("source_files" in error for error in errors)


def test_validate_schema_path_metadata_accepts_optional_schema_fields():
    node = {
        "metadata": {
            "schema_path": "$.properties.name",
            "schema_kind": "schema_property",
            "schema_pattern": "$.properties.*",
        }
    }
    assert validate_schema_path_metadata(node) == []
    assert validate_schema_path_metadata({"metadata": {"other": "value"}}) == []
    assert validate_schema_path_metadata({}) == []


def test_validate_schema_path_metadata_rejects_bad_types():
    errors = validate_schema_path_metadata(
        {"metadata": {"schema_path": ["$"], "schema_kind": "", "schema_pattern": 3}}
    )
    assert any("schema_path" in error for error in errors)
    assert any("schema_kind" in error for error in errors)
    assert any("schema_pattern" in error for error in errors)


def test_validate_source_refs_accepts_metadata_or_export_shape():
    metadata = {
        "source_refs": [
            {
                "source_file": "docs/a.md",
                "source_location": "L10-L12",
                "node_id": "n1",
                "confidence_score": 0.9,
            }
        ]
    }
    assert validate_source_refs(metadata) == []
    assert validate_source_refs({"graph3d_metadata": metadata}) == []


def test_validate_source_refs_rejects_bad_list_shape():
    errors = validate_source_refs({"source_refs": {"source_file": "a.py"}})
    assert any("source_refs" in error and "list" in error for error in errors)

    errors = validate_source_refs({"source_refs": [{}]})
    assert any("source identifier" in error for error in errors)


def test_validate_relation_endpoints_checks_endpoint_strings_and_node_ids():
    errors = validate_relation_endpoints(
        {"source": "n1", "target": "ghost", "relation": "calls"},
        {"n1", "n2"},
    )
    assert any("target" in error and "ghost" in error for error in errors)

    errors = validate_relation_endpoints({"source": 123, "target": "n2"})
    assert any("source" in error and "string" in error for error in errors)


def test_validate_provenance_metadata_keeps_confidence_score_optional():
    assert validate_provenance_metadata({"source_file": "a.py"}) == []
    errors = validate_provenance_metadata({"confidence_score": 1.5})
    assert any("confidence_score" in error for error in errors)


def test_validate_graph_export_keeps_legacy_bad_endpoints_compatible_without_metadata():
    legacy = {
        "nodes": [{"id": "n1", "label": "Legacy"}],
        "links": [{"source": 1, "target": "n1"}],
    }
    assert validate_graph_export(legacy) == []


def test_validate_graph_export_checks_relation_endpoints_when_metadata_present():
    data = {
        "nodes": [{"id": "n1", "label": "A", "file_type": "code", "source_file": "a.py"}],
        "links": [{"source": 1, "target": "n1", "relation": "references"}],
        "graph3d_metadata": {},
    }
    errors = validate_graph_export(data)
    assert any("links[0].source" in error and "string" in error for error in errors)


def test_validate_graph_export_checks_node_schema_metadata_when_metadata_present():
    data = {
        "nodes": [
            {
                "id": "n1",
                "label": "Schema",
                "file_type": "schema",
                "source_file": "schema.json",
                "metadata": {"schema_path": 123},
            }
        ],
        "links": [],
        "graph3d_metadata": {},
    }
    errors = validate_graph_export(data)
    assert any("metadata.schema_path" in error for error in errors)
