"""Canonical object-model terminology for graph3d / 3dkg — semantic strong-name linking.

Every core concept has ONE canonical *strong name* (e.g. ``g3dkg:core.Node``).
Friendly human words ("node", "link", "cluster", "path pattern", "dataflow",
"knowledge graph", ...) and the equivalent terms in other systems (Obsidian,
txt2kg, GraphRAG, Neo4j, RDF, NetworkX, and Karpathy's "LLM OS" framing) all
*resolve* to that strong name. This lets humans, agents, UIs, and queries use
easy words while the engine keeps one stable, versioned object model.

Source of truth: the ``TERMS`` registry below. ``schemas/terms.json`` is a
generated mirror for non-Python consumers (the 3dkg UI / agents); keep it in
sync with ``write_terms_json`` (a test asserts equality).

Strong-name grammar:  ``g3dkg:<namespace>.<Concept>``
  namespace in {core, cluster, query, flow, schema, meta, ui}
  Concept is PascalCase and globally unique.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

REGISTRY_VERSION = "1.0"

# Systems we provide a cross-walk to. "graph3d" is the home system.
SYSTEMS: tuple[str, ...] = (
    "graph3d",
    "obsidian",
    "txt2kg",
    "graphrag",
    "neo4j",
    "rdf",
    "networkx",
    "karpathy_llmos",
)


@dataclass(frozen=True)
class Term:
    """One canonical concept with its friendly words and cross-system map."""

    strong_name: str
    friendly: str
    aliases: tuple[str, ...]
    definition: str
    maps: dict[str, str]


# ---------------------------------------------------------------------------
# Canonical registry.  Aliases MUST be globally unique (enforced at import).
# ---------------------------------------------------------------------------
TERMS: tuple[Term, ...] = (
    Term(
        "g3dkg:core.KnowledgeGraph",
        "knowledge graph",
        ("graph", "kg", "knowledge-graph", "network", "web", "second-brain"),
        "The whole typed graph of nodes, links, clusters, and provenance — the graph3d.json document.",
        {
            "graph3d": "graph.json document (NetworkX node_link_data)",
            "obsidian": "the vault",
            "txt2kg": "the knowledge graph (set of triples)",
            "graphrag": "the index (entities + relationships + communities)",
            "neo4j": "the graph / database",
            "rdf": "RDF dataset / named graph",
            "networkx": "Graph",
            "karpathy_llmos": "the disk / long-term memory store",
        },
    ),
    Term(
        "g3dkg:core.Node",
        "node",
        ("entity", "bitdot", "vertex", "point"),
        "A named thing in the graph: a function, file, doc-section, or concept.",
        {
            "graph3d": "nodes[] {id,label,file_type,source_file,community}",
            "obsidian": "note (.md file)",
            "txt2kg": "entity (head/tail of a triple)",
            "graphrag": "Entity {title,type,description}",
            "neo4j": "node (:Label)",
            "rdf": "subject / resource (IRI)",
            "networkx": "node",
            "karpathy_llmos": "a memory record / page",
        },
    ),
    Term(
        "g3dkg:core.Link",
        "link",
        ("edge", "relationship", "connection", "association", "arc"),
        "A typed, directional, confidence-scored connection between two nodes (source -> target).",
        {
            "graph3d": "links[] {source,target,relation,confidence,confidence_score}",
            "obsidian": "[[wikilink]] / backlink",
            "txt2kg": "relation (the middle of a triple)",
            "graphrag": "Relationship {source,target,weight,description}",
            "neo4j": "relationship [:TYPE]",
            "rdf": "predicate (triple)",
            "networkx": "edge",
            "karpathy_llmos": "an association / pointer",
        },
    ),
    Term(
        "g3dkg:core.NodeType",
        "shape",
        ("kind", "node-type", "file-type", "category", "node-shape"),
        "The class of a node, rendered as a SHAPE in 3dkg (code, document, schema, ...).",
        {
            "graph3d": "file_type in {code,document,paper,image,rationale,concept,schema,data}",
            "obsidian": "frontmatter `type:` / tag",
            "txt2kg": "entity type",
            "graphrag": "entity type (PERSON/ORG/GEO/EVENT)",
            "neo4j": "node label (:Label)",
            "rdf": "rdf:type / class",
            "networkx": "node attribute",
            "karpathy_llmos": "—",
        },
    ),
    Term(
        "g3dkg:core.Predicate",
        "relation",
        ("link-type", "predicate", "relationship-type", "verb", "edge-label"),
        "The controlled-vocabulary label on a link (calls, imports, contains, references, ...).",
        {
            "graph3d": "relation (string on each link)",
            "obsidian": "implicit (all wikilinks share one untyped relation)",
            "txt2kg": "predicate",
            "graphrag": "relationship description",
            "neo4j": "relationship type",
            "rdf": "predicate (property IRI)",
            "networkx": "edge 'relation' attribute",
            "karpathy_llmos": "—",
        },
    ),
    Term(
        "g3dkg:cluster.Cluster",
        "cluster",
        ("community", "region", "group", "neighborhood", "module"),
        "A densely-connected group of nodes found by Leiden; colors nodes in 3dkg.",
        {
            "graph3d": "community (int) via cluster.py Leiden",
            "obsidian": "folder / MOC grouping",
            "txt2kg": "entity cluster",
            "graphrag": "community (hierarchical Leiden)",
            "neo4j": "community / partition",
            "rdf": "named graph (loosely)",
            "networkx": "community partition",
            "karpathy_llmos": "a region of memory",
        },
    ),
    Term(
        "g3dkg:cluster.ClusterReport",
        "cluster summary",
        ("community-report", "region-summary", "moc", "map-of-content", "overview"),
        "A structured/LLM summary of a cluster (title, summary, findings) for global sensemaking.",
        {
            "graph3d": "GRAPH_REPORT.md / community labels / community_reports.py (planned)",
            "obsidian": "MOC note (Map of Content)",
            "txt2kg": "—",
            "graphrag": "community report {title,summary,findings}",
            "neo4j": "—",
            "rdf": "—",
            "networkx": "—",
            "karpathy_llmos": "a precomputed summary page",
        },
    ),
    Term(
        "g3dkg:query.PathPattern",
        "path pattern",
        ("path", "route", "trail", "walk", "traversal", "link-chain"),
        "An ordered sequence of nodes joined by links (a shortest path, call chain, or schema path).",
        {
            "graph3d": "shortest_path() / BFS in serve.py / relation chains",
            "obsidian": "a link path between notes",
            "txt2kg": "path (chain of triples)",
            "graphrag": "relationship path / multi-hop traversal",
            "neo4j": "Cypher path pattern (a)-[]->(b)",
            "rdf": "SPARQL property path",
            "networkx": "path",
            "karpathy_llmos": "a reasoning trace / chain",
        },
    ),
    Term(
        "g3dkg:flow.Dataflow",
        "dataflow",
        ("flow", "call-flow", "pipeline", "control-flow", "data-lineage"),
        "A directed flow of execution or data through the graph (calls, imports, reads/writes).",
        {
            "graph3d": "callflow_html.py + calls/imports edges",
            "obsidian": "—",
            "txt2kg": "—",
            "graphrag": "—",
            "neo4j": "directed traversal",
            "rdf": "—",
            "networkx": "directed subgraph",
            "karpathy_llmos": "the wiring between modules (Software 1.0 control flow)",
        },
    ),
    Term(
        "g3dkg:schema.SchemaPath",
        "schema path",
        ("data-shape", "schema-pattern", "key-path", "structural-path", "json-path"),
        "A structural path through a data schema (JSON/SQLite) extracted as schema nodes/edges.",
        {
            "graph3d": "schema_paths.py (schema_pattern/schema_terminal/schema_type/sqlite_*)",
            "obsidian": "—",
            "txt2kg": "—",
            "graphrag": "covariate / claim (loosely)",
            "neo4j": "property key path",
            "rdf": "SHACL shape (loosely)",
            "networkx": "—",
            "karpathy_llmos": "the shape of the data (Software 2.0 dataset schema)",
        },
    ),
    Term(
        "g3dkg:core.Hyperedge",
        "hyperedge",
        ("group-relation", "n-ary-link", "hypergraph-edge"),
        "A relation among three or more nodes (a group / region relationship).",
        {
            "graph3d": "hyperedges[] {id,label,nodes[]}",
            "obsidian": "group / MOC",
            "txt2kg": "n-ary relation",
            "graphrag": "—",
            "neo4j": "reified node",
            "rdf": "reified statement / RDF*",
            "networkx": "—",
            "karpathy_llmos": "—",
        },
    ),
    Term(
        "g3dkg:meta.Provenance",
        "source",
        ("provenance", "citation", "origin", "evidence", "reference", "source-file", "source-location"),
        "Where a node/link came from (file, location, extractor, model, commit) — for citation and trust. "
        "Note: a link's structural endpoints are the source_node/target_node fields, distinct from this origin.",
        {
            "graph3d": "source_file, source_location, provenance{extractor,model}, built_at_commit",
            "obsidian": "the source note / link target",
            "txt2kg": "source text span",
            "graphrag": "text_unit_ids",
            "neo4j": "property metadata",
            "rdf": "PROV-O / named graph",
            "networkx": "node/edge attribute",
            "karpathy_llmos": "the citation that grounds the memory",
        },
    ),
    Term(
        "g3dkg:meta.Confidence",
        "confidence",
        ("trust", "certainty", "strength", "score", "weight"),
        "How sure we are a node/link is real: an enum plus a 0-1 score.",
        {
            "graph3d": "confidence in {EXTRACTED,INFERRED,AMBIGUOUS} + confidence_score (0-1)",
            "obsidian": "— (links are binary)",
            "txt2kg": "extraction score",
            "graphrag": "relationship weight (1-10)",
            "neo4j": "property",
            "rdf": "—",
            "networkx": "edge attribute",
            "karpathy_llmos": "signal vs noise in memory",
        },
    ),
    Term(
        "g3dkg:ui.ViewState",
        "view",
        ("lens", "camera", "viewpoint", "focus", "scene"),
        "The current 3dkg view: focus node, slice, path highlight, cluster isolation, camera.",
        {
            "graph3d": "graph3d.viewstate/1 (bitdot_cube template JSON)",
            "obsidian": "Graph View settings / local graph",
            "txt2kg": "—",
            "graphrag": "—",
            "neo4j": "browser view",
            "rdf": "—",
            "networkx": "—",
            "karpathy_llmos": "what is currently in RAM (the context window)",
        },
    ),
    Term(
        "g3dkg:core.Label",
        "label",
        ("name", "title", "display-name", "caption"),
        "The human-readable name of a node.",
        {
            "graph3d": "label (+ norm_label normalized form)",
            "obsidian": "note title / [[alias]]",
            "txt2kg": "entity name",
            "graphrag": "title",
            "neo4j": "name property",
            "rdf": "rdfs:label",
            "networkx": "node 'label' attribute",
            "karpathy_llmos": "—",
        },
    ),
    Term(
        "g3dkg:core.Identifier",
        "id",
        ("node-id", "key", "identifier", "canonical-id", "slug"),
        "The stable unique identifier of a node.",
        {
            "graph3d": "id (+ canonical_id planned)",
            "obsidian": "filename / slug",
            "txt2kg": "entity id",
            "graphrag": "id / human_readable_id",
            "neo4j": "element id / key",
            "rdf": "IRI",
            "networkx": "node key",
            "karpathy_llmos": "the address / pointer",
        },
    ),
)


def _normalize(term: str) -> str:
    """Lowercase and unify separators so 'Path Pattern' == 'path_pattern' == 'path-pattern'."""
    return "-".join(str(term).strip().lower().replace("_", " ").replace("-", " ").split())


def _build_index() -> dict[str, str]:
    index: dict[str, str] = {}

    def _add(key: str, strong_name: str) -> None:
        norm = _normalize(key)
        if not norm:
            return
        existing = index.get(norm)
        if existing is not None and existing != strong_name:
            raise ValueError(
                f"terminology alias collision: {norm!r} -> {existing} and {strong_name}"
            )
        index[norm] = strong_name

    for t in TERMS:
        _add(t.strong_name, t.strong_name)
        _add(t.strong_name.split(":")[-1], t.strong_name)  # core.Node
        _add(t.strong_name.split(".")[-1], t.strong_name)  # Node
        _add(t.friendly, t.strong_name)
        for a in t.aliases:
            _add(a, t.strong_name)
    return index


_BY_STRONG_NAME: dict[str, Term] = {t.strong_name: t for t in TERMS}
_ALIAS_INDEX: dict[str, str] = _build_index()


def resolve(term: str) -> str | None:
    """Resolve any friendly word / alias / strong name to its canonical strong name."""
    return _ALIAS_INDEX.get(_normalize(term))


def get(term: str) -> Term | None:
    """Return the canonical Term for any friendly word, alias, or strong name."""
    sn = resolve(term)
    return _BY_STRONG_NAME.get(sn) if sn else None


def to_system(term: str, system: str) -> str | None:
    """Translate any term into another system's vocabulary (e.g. to_system('node','obsidian'))."""
    if system not in SYSTEMS:
        raise ValueError(f"unknown system {system!r}; choose from {SYSTEMS}")
    entry = get(term)
    return entry.maps.get(system) if entry else None


# ---------------------------------------------------------------------------
# Predicate groups — friendly umbrella words that expand to a set of concrete
# graph3d ``relation`` values. Powers friendly-word query parsing ("show the
# dataflow into X" -> {calls, imports, ...}).
# ---------------------------------------------------------------------------
PREDICATE_GROUPS: dict[str, tuple[str, ...]] = {
    "dataflow": ("calls", "method", "imports", "imports_from", "re_exports", "instantiates", "reads_from"),
    "call": ("calls", "method"),
    "import": ("imports", "imports_from", "re_exports"),
    "containment": ("contains", "defines", "embeds", "contains_schema_path"),
    "reference": ("references", "uses", "references_constant", "uses_config", "uses_static_prop"),
    "schema": ("contains_schema_path", "matches_schema_pattern", "matches_schema_terminal", "has_schema_type"),
    "hierarchy": ("inherits", "implements", "mixes_in", "case_of"),
    "rationale": ("rationale_for",),
}

# Friendly synonyms that map onto a PREDICATE_GROUPS key (normalized form).
_PREDICATE_GROUP_ALIASES: dict[str, str] = {
    "flow": "dataflow",
    "call-flow": "dataflow",
    "callflow": "dataflow",
    "control-flow": "dataflow",
    "pipeline": "dataflow",
    "lineage": "dataflow",
    "data-lineage": "dataflow",
    "calls": "call",
    "invocation": "call",
    "imports": "import",
    "containment": "containment",
    "contains": "containment",
    "reference": "reference",
    "references": "reference",
    "schema-path": "schema",
    "schema-pattern": "schema",
    "inheritance": "hierarchy",
    "inherits": "hierarchy",
    "rationale": "rationale",
    "docstring": "rationale",
}


def resolve_relations(word: str) -> set[str]:
    """Expand a friendly umbrella word into its set of graph3d ``relation`` values.

    Returns an empty set for words that are not a known predicate group/alias,
    so callers can fall back to a literal/substring match (e.g. an exact
    relation like ``embeds``).
    """
    norm = _normalize(word)
    key = _PREDICATE_GROUP_ALIASES.get(norm)
    if key is None and norm in PREDICATE_GROUPS:
        key = norm
    return set(PREDICATE_GROUPS[key]) if key else set()


def relations_in_query(question: str) -> set[str]:
    """Scan a free-text question for predicate-group words and union their relations.

    Considers single words and adjacent bigrams ("data flow" -> "data-flow") so
    multi-word umbrellas resolve.
    """
    import re as _re

    words = [_normalize(w) for w in _re.findall(r"[A-Za-z_]+", question)]
    candidates: set[str] = set(words)
    for a, b in zip(words, words[1:]):
        candidates.add(f"{a}-{b}")
    out: set[str] = set()
    for c in candidates:
        out |= resolve_relations(c)
    return out


def all_strong_names() -> list[str]:
    return [t.strong_name for t in TERMS]


def as_document() -> dict:
    """Serialize the registry to the canonical terms.json shape."""
    return {
        "registry_version": REGISTRY_VERSION,
        "systems": list(SYSTEMS),
        "terms": [
            {
                "strong_name": t.strong_name,
                "friendly": t.friendly,
                "aliases": list(t.aliases),
                "definition": t.definition,
                "maps": dict(t.maps),
            }
            for t in TERMS
        ],
    }


def write_terms_json(path: str | Path | None = None) -> Path:
    """Write/refresh the generated terms.json mirror next to this module."""
    target = Path(path) if path else Path(__file__).parent / "schemas" / "terms.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(as_document(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target
