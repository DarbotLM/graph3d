# validate extraction JSON against the graph3d schema before graph assembly
from __future__ import annotations

VALID_FILE_TYPES = {"code", "document", "paper", "image", "rationale", "concept", "schema", "data"}
VALID_CONFIDENCES = {"EXTRACTED", "INFERRED", "AMBIGUOUS"}
REQUIRED_NODE_FIELDS = {"id", "label", "file_type", "source_file"}
REQUIRED_EDGE_FIELDS = {"source", "target", "relation", "confidence", "source_file"}
GRAPH3D_EXPORT_SCHEMA_VERSION = "1.0"
GRAPH3D_EXPORT_SCHEMA_KIND = "graph3d.graph.json.schema-core"
SCHEMA_PATH_METADATA_FIELDS = ("schema_path", "schema_kind", "schema_pattern")
SOURCE_REF_IDENTIFIER_FIELDS = (
    "source_file",
    "source_location",
    "url",
    "uri",
    "source_uri",
    "node_id",
    "edge_id",
    "id",
)
SOURCE_REF_STRING_FIELDS = SOURCE_REF_IDENTIFIER_FIELDS + (
    "kind",
    "source_kind",
    "label",
)
PROVENANCE_STRING_FIELDS = (
    "schema_version",
    "schema_kind",
    "built_at_commit",
    "generated_by",
    "generated_at",
    "created_at",
    "updated_at",
    "extracted_by",
    "extractor",
    "model",
    "source_file",
    "source_location",
)
PROVENANCE_SCORE_FIELDS = ("confidence_score",)


def validate_extraction(data: dict) -> list[str]:
    """
    Validate an extraction JSON dict against the graph3d schema.
    Returns a list of error strings - empty list means valid.
    """
    if not isinstance(data, dict):
        return ["Extraction must be a JSON object"]

    errors: list[str] = []

    # Nodes
    if "nodes" not in data:
        errors.append("Missing required key 'nodes'")
    elif not isinstance(data["nodes"], list):
        errors.append("'nodes' must be a list")
    else:
        for i, node in enumerate(data["nodes"]):
            if not isinstance(node, dict):
                errors.append(f"Node {i} must be an object")
                continue
            for field in REQUIRED_NODE_FIELDS:
                if field not in node:
                    errors.append(f"Node {i} (id={node.get('id', '?')!r}) missing required field '{field}'")
            if "file_type" in node and node["file_type"] not in VALID_FILE_TYPES:
                errors.append(
                    f"Node {i} (id={node.get('id', '?')!r}) has invalid file_type "
                    f"'{node['file_type']}' - must be one of {sorted(VALID_FILE_TYPES)}"
                )

    # Edges - accept "links" (NetworkX <= 3.1) as fallback for "edges"
    edge_list = data.get("edges") if "edges" in data else data.get("links")
    if edge_list is None:
        errors.append("Missing required key 'edges'")
    elif not isinstance(edge_list, list):
        errors.append("'edges' must be a list")
    else:
        node_ids = {n["id"] for n in data.get("nodes", []) if isinstance(n, dict) and "id" in n}
        for i, edge in enumerate(edge_list):
            if not isinstance(edge, dict):
                errors.append(f"Edge {i} must be an object")
                continue
            for field in REQUIRED_EDGE_FIELDS:
                if field not in edge:
                    errors.append(f"Edge {i} missing required field '{field}'")
            if "confidence" in edge and edge["confidence"] not in VALID_CONFIDENCES:
                errors.append(
                    f"Edge {i} has invalid confidence '{edge['confidence']}' "
                    f"- must be one of {sorted(VALID_CONFIDENCES)}"
                )
            if "source" in edge and node_ids and edge["source"] not in node_ids:
                errors.append(f"Edge {i} source '{edge['source']}' does not match any node id")
            if "target" in edge and node_ids and edge["target"] not in node_ids:
                errors.append(f"Edge {i} target '{edge['target']}' does not match any node id")

    return errors


def assert_valid(data: dict) -> None:
    """Raise ValueError with all errors if extraction is invalid."""
    errors = validate_extraction(data)
    if errors:
        msg = f"Extraction JSON has {len(errors)} error(s):\n" + "\n".join(f"  • {e}" for e in errors)
        raise ValueError(msg)


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_endpoint_string(value: object, field_path: str) -> list[str]:
    """Validate a node, relation, or source-reference endpoint-ish string."""
    if not isinstance(value, str):
        return [f"{field_path} must be a string"]
    if not value.strip():
        return [f"{field_path} must be a non-empty string"]
    if any(ord(ch) < 32 for ch in value):
        return [f"{field_path} must not contain control characters"]
    return []


def validate_relation_endpoints(
    relation: object,
    node_ids: set[str] | None = None,
    *,
    context: str = "relation",
) -> list[str]:
    """Validate source/target endpoint shape and optional node-id membership."""
    if not isinstance(relation, dict):
        return [f"{context} must be an object"]

    errors: list[str] = []
    for key in ("source", "target"):
        if key not in relation:
            errors.append(f"{context} missing required endpoint '{key}'")
            continue
        endpoint = relation[key]
        endpoint_errors = validate_endpoint_string(endpoint, f"{context}.{key}")
        errors.extend(endpoint_errors)
        if not endpoint_errors and node_ids is not None and endpoint not in node_ids:
            errors.append(f"{context}.{key} '{endpoint}' does not match any node id")

    if "relation" in relation:
        errors.extend(validate_endpoint_string(relation["relation"], f"{context}.relation"))
    return errors


def validate_schema_path_metadata(node: object, *, context: str = "node") -> list[str]:
    """Validate optional schema-path fields stored under node metadata."""
    if not isinstance(node, dict):
        return [f"{context} must be an object"]

    metadata = node.get("metadata")
    if metadata is None:
        return []
    if not isinstance(metadata, dict):
        return [f"{context}.metadata must be an object when present"]

    errors: list[str] = []
    for key in SCHEMA_PATH_METADATA_FIELDS:
        if key not in metadata:
            continue
        value = metadata[key]
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{context}.metadata.{key} must be a non-empty string when present")
    return errors


def _validate_confidence_score(value: object, field_path: str) -> list[str]:
    if not _is_number(value):
        return [f"{field_path} must be a number between 0 and 1"]
    score = float(value)
    if score != score or not 0 <= score <= 1:
        return [f"{field_path} must be a number between 0 and 1"]
    return []


def validate_source_refs(container: object, *, context: str = "metadata") -> list[str]:
    """Validate optional source_refs whether called with metadata or an export object."""
    if not isinstance(container, dict):
        return [f"{context} must be an object"]

    metadata = container
    metadata_context = context
    if "source_refs" not in metadata and "graph3d_metadata" in container:
        graph_metadata = container.get("graph3d_metadata")
        if graph_metadata is None:
            return []
        if not isinstance(graph_metadata, dict):
            return [f"{context}.graph3d_metadata must be an object"]
        metadata = graph_metadata
        metadata_context = f"{context}.graph3d_metadata"

    if "source_refs" not in metadata:
        return []
    source_refs = metadata.get("source_refs")
    if source_refs is None:
        return []
    if not isinstance(source_refs, list):
        return [f"{metadata_context}.source_refs must be a list when present"]

    errors: list[str] = []
    for i, source_ref in enumerate(source_refs):
        ref_context = f"{metadata_context}.source_refs[{i}]"
        if not isinstance(source_ref, dict):
            errors.append(f"{ref_context} must be an object")
            continue
        if not any(key in source_ref for key in SOURCE_REF_IDENTIFIER_FIELDS):
            errors.append(f"{ref_context} must include at least one source identifier")

        for key in SOURCE_REF_STRING_FIELDS:
            value = source_ref.get(key)
            if value is not None:
                errors.extend(validate_endpoint_string(value, f"{ref_context}.{key}"))

        for key in ("line", "column", "start_line", "end_line"):
            value = source_ref.get(key)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                errors.append(f"{ref_context}.{key} must be a non-negative integer")

        confidence = source_ref.get("confidence")
        if confidence is not None and confidence not in VALID_CONFIDENCES:
            errors.append(
                f"{ref_context}.confidence must be one of {sorted(VALID_CONFIDENCES)}"
            )

        if source_ref.get("confidence_score") is not None:
            errors.extend(
                _validate_confidence_score(
                    source_ref["confidence_score"],
                    f"{ref_context}.confidence_score",
                )
            )

    return errors


def validate_provenance_metadata(metadata: object, *, context: str = "metadata") -> list[str]:
    """Validate optional provenance-like metadata fields without requiring them."""
    if not isinstance(metadata, dict):
        return [f"{context} must be an object"]

    errors: list[str] = []
    for key in PROVENANCE_STRING_FIELDS:
        value = metadata.get(key)
        if value is not None and not isinstance(value, str):
            errors.append(f"{context}.{key} must be a string when present")

    for key in PROVENANCE_SCORE_FIELDS:
        value = metadata.get(key)
        if value is not None:
            errors.extend(_validate_confidence_score(value, f"{context}.{key}"))

    errors.extend(validate_source_refs(metadata, context=context))
    return errors


def validate_graph_export(data: dict) -> list[str]:
    """
    Validate optional graph.json export extensions without rejecting legacy node-link JSON.

    NetworkX node-link output that only contains nodes/links and no graph3d metadata
    remains valid. When graph3d_schema or graph3d_metadata is present, this helper
    checks that the metadata shape matches the schema-core extension and that source
    summaries agree with the exported nodes/links.
    """
    if not isinstance(data, dict):
        return ["Graph export must be a JSON object"]

    errors: list[str] = []
    nodes = data.get("nodes", [])
    links = data.get("links") if "links" in data else data.get("edges", [])

    if "nodes" in data and not isinstance(nodes, list):
        errors.append("'nodes' must be a list when present")
        nodes = []
    if ("links" in data or "edges" in data) and not isinstance(links, list):
        errors.append("'links'/'edges' must be a list when present")
        links = []

    schema = data.get("graph3d_schema")
    if schema is not None:
        if not isinstance(schema, dict):
            errors.append("'graph3d_schema' must be an object")
        else:
            version = schema.get("version")
            kind = schema.get("kind")
            if not isinstance(version, str) or not version:
                errors.append("'graph3d_schema.version' must be a non-empty string")
            if not isinstance(kind, str) or not kind:
                errors.append("'graph3d_schema.kind' must be a non-empty string")

    metadata = data.get("graph3d_metadata")
    if metadata is None:
        return errors
    if not isinstance(metadata, dict):
        errors.append("'graph3d_metadata' must be an object")
        return errors

    errors.extend(validate_provenance_metadata(metadata, context="'graph3d_metadata'"))

    source_summary = metadata.get("source_documents")
    if source_summary is not None:
        errors.extend(_validate_source_document_summary(source_summary, nodes, links))

    validation = metadata.get("validation")
    if validation is not None:
        errors.extend(_validate_export_validation_summary(validation))

    node_ids: set[str] = set()
    for i, node in enumerate(nodes):
        node_context = f"nodes[{i}]"
        if not isinstance(node, dict):
            errors.append(f"{node_context} must be an object")
            continue
        node_id = node.get("id")
        if node_id is None:
            errors.append(f"{node_context} missing required endpoint 'id'")
        else:
            endpoint_errors = validate_endpoint_string(node_id, f"{node_context}.id")
            errors.extend(endpoint_errors)
            if not endpoint_errors and isinstance(node_id, str):
                node_ids.add(node_id)
        errors.extend(validate_schema_path_metadata(node, context=node_context))
        errors.extend(validate_provenance_metadata(node, context=node_context))

    for i, link in enumerate(links):
        link_context = f"links[{i}]"
        if not isinstance(link, dict):
            errors.append(f"{link_context} must be an object")
            continue
        errors.extend(
            validate_relation_endpoints(link, node_ids if node_ids else None, context=link_context)
        )
        errors.extend(validate_provenance_metadata(link, context=link_context))

    return errors


def _validate_source_document_summary(source_summary: object, nodes: list, links: list) -> list[str]:
    errors: list[str] = []
    if not isinstance(source_summary, dict):
        return ["'graph3d_metadata.source_documents' must be an object"]

    observed_sources: set[str] = set()
    observed_file_types: dict[str, int] = {}
    for item in list(nodes) + list(links):
        if not isinstance(item, dict):
            continue
        source_file = item.get("source_file")
        if source_file:
            observed_sources.add(str(source_file))
        file_type = item.get("file_type")
        if file_type:
            key = str(file_type)
            observed_file_types[key] = observed_file_types.get(key, 0) + 1

    source_files = source_summary.get("source_files")
    if source_files is not None:
        if not isinstance(source_files, list) or not all(isinstance(x, str) for x in source_files):
            errors.append("'graph3d_metadata.source_documents.source_files' must be a list of strings")
        else:
            missing = sorted(observed_sources.difference(source_files))
            if missing:
                errors.append(
                    "'graph3d_metadata.source_documents.source_files' is missing "
                    f"{len(missing)} observed source_file value(s)"
                )

    source_file_count = source_summary.get("source_file_count")
    if source_file_count is not None:
        if not isinstance(source_file_count, int) or source_file_count < 0:
            errors.append("'graph3d_metadata.source_documents.source_file_count' must be a non-negative integer")
        elif isinstance(source_files, list) and source_file_count != len(source_files):
            errors.append(
                "'graph3d_metadata.source_documents.source_file_count' does not match "
                "source_files length"
            )

    file_type_counts = source_summary.get("file_type_counts")
    if file_type_counts is not None:
        if not isinstance(file_type_counts, dict):
            errors.append("'graph3d_metadata.source_documents.file_type_counts' must be an object")
        else:
            for key, value in file_type_counts.items():
                if not isinstance(key, str) or not isinstance(value, int) or value < 0:
                    errors.append(
                        "'graph3d_metadata.source_documents.file_type_counts' values must "
                        "be non-negative integers"
                    )
                    break
            if not errors and observed_file_types and file_type_counts != observed_file_types:
                errors.append(
                    "'graph3d_metadata.source_documents.file_type_counts' does not match "
                    "exported node file_type counts"
                )

    documents = source_summary.get("documents")
    if documents is not None:
        if not isinstance(documents, list):
            errors.append("'graph3d_metadata.source_documents.documents' must be a list")
        else:
            for i, document in enumerate(documents):
                if not isinstance(document, dict):
                    errors.append(f"Source document {i} must be an object")
                    continue
                if not isinstance(document.get("source_file"), str):
                    errors.append(f"Source document {i} missing string 'source_file'")
                for count_key in ("node_count", "link_count"):
                    value = document.get(count_key)
                    if value is not None and (not isinstance(value, int) or value < 0):
                        errors.append(f"Source document {i} '{count_key}' must be a non-negative integer")

    return errors


def _validate_export_validation_summary(validation: object) -> list[str]:
    if not isinstance(validation, dict):
        return ["'graph3d_metadata.validation' must be an object"]

    errors: list[str] = []
    for key in ("node_count", "link_count", "hyperedge_count", "dangling_link_count"):
        value = validation.get(key)
        if value is not None and (not isinstance(value, int) or value < 0):
            errors.append(f"'graph3d_metadata.validation.{key}' must be a non-negative integer")
    return errors
