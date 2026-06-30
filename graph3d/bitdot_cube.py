from __future__ import annotations

import html as _html
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import networkx as nx

from graph3d.analyze import _node_community_map
from graph3d.export import _viz_node_limit
from graph3d.security import sanitize_label
from graph3d import terminology


BITDOT_CUBE_SCHEMA_KIND = "graph3d.bitdot-cube"
BITDOT_CUBE_SCHEMA_VERSION = "1.1"


def _js_safe(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _normalize_layout(pos: dict[str, tuple[float, float, float]]) -> dict[str, tuple[float, float, float]]:
    if not pos:
        return {}

    axes = list(zip(*pos.values()))
    mins = [min(axis) for axis in axes]
    maxs = [max(axis) for axis in axes]

    normalized: dict[str, tuple[float, float, float]] = {}
    for node_id, coords in pos.items():
        scaled = []
        for idx, value in enumerate(coords):
            span = maxs[idx] - mins[idx]
            if span == 0:
                scaled.append(0.0)
            else:
                scaled.append(((value - mins[idx]) / span) * 2.0 - 1.0)
        normalized[node_id] = (round(scaled[0], 6), round(scaled[1], 6), round(scaled[2], 6))
    return normalized


def _layout_positions(G: nx.Graph) -> dict[str, tuple[float, float, float]]:
    """Return deterministic 3D node positions in the normalized [-1, 1] cube."""
    node_ids = [str(n) for n in G.nodes()]
    if not node_ids:
        return {}
    if len(node_ids) == 1:
        return {node_ids[0]: (0.0, 0.0, 0.0)}

    try:
        raw = nx.spring_layout(G, dim=3, seed=42, iterations=80)
    except Exception:
        raw = {}

    if not raw:
        count = len(node_ids)
        raw = {}
        for i, node_id in enumerate(node_ids):
            angle = (2 * math.pi * i) / max(count, 1)
            z = -1 + (2 * i / max(count - 1, 1))
            radius = math.sqrt(max(0.0, 1 - z * z))
            raw[node_id] = (radius * math.cos(angle), radius * math.sin(angle), z)

    pos = {
        str(node_id): (float(coords[0]), float(coords[1]), float(coords[2]))
        for node_id, coords in raw.items()
    }
    return _normalize_layout(pos)


# Distinct color per connection pattern (relation type). The dominant patterns
# each get a hue so a reader can tell a `calls` path from a `contains` or
# schema-path pattern at a glance; everything else falls back to neutral gray.
RELATION_COLORS = {
    "calls": "#f0883e",          # orange - invocation
    "method": "#79c0ff",         # light blue - method binding
    "contains": "#58a6ff",       # blue - structural containment
    "imports": "#3fb950",        # green - module import
    "imports_from": "#3fb950",
    "re_exports": "#3fb950",
    "references": "#bc8cff",     # purple - symbol reference
    "uses": "#bc8cff",
    "rationale_for": "#8b949e",  # gray - docstring / comment link
    "inherits": "#f778ba",       # pink - type hierarchy
    "implements": "#f778ba",
    "mixes_in": "#f778ba",
    "defines": "#56d364",        # bright green - definition
    "contains_schema_path": "#d29922",   # amber - schema path
    "matches_schema_pattern": "#e3b341",  # gold - schema pattern
    "matches_schema_terminal": "#bb8009",  # dark amber - schema terminal
}
_RELATION_DEFAULT_COLOR = "#6e7681"


def _relation_color(relation: str) -> str:
    return RELATION_COLORS.get(relation, _RELATION_DEFAULT_COLOR)


def _hsl_to_hex(h: float, s: float, lightness: float) -> str:
    """Convert HSL (h in [0,360), s/l in [0,1]) to a #rrggbb hex string."""
    c = (1 - abs(2 * lightness - 1)) * s
    hp = (h % 360) / 60.0
    x = c * (1 - abs(hp % 2 - 1))
    if hp < 1:
        r, g, b = c, x, 0.0
    elif hp < 2:
        r, g, b = x, c, 0.0
    elif hp < 3:
        r, g, b = 0.0, c, x
    elif hp < 4:
        r, g, b = 0.0, x, c
    elif hp < 5:
        r, g, b = x, 0.0, c
    else:
        r, g, b = c, 0.0, x
    m = lightness - c / 2
    return "#{:02x}{:02x}{:02x}".format(
        round((r + m) * 255), round((g + m) * 255), round((b + m) * 255)
    )


def _community_color(cid: int) -> str:
    """Give every cluster a visually distinct hue via the golden-angle rule.

    A fixed palette collapses hundreds of clusters onto a handful of hues;
    spreading hue by the golden angle keeps neighbouring cluster ids far apart
    in color space so clusters stay distinguishable even at 400+ groups.
    """
    hue = (int(cid) * 137.508) % 360
    lightness = 0.62 if int(cid) % 2 == 0 else 0.52
    return _hsl_to_hex(hue, 0.62, lightness)


def _resolve_community(node_id, data: dict, node_community: dict) -> int:
    """Resolve a node's cluster id, robust to a stale analysis sidecar.

    Prefer the canonical clustering map, but fall back to the per-node
    `community` attribute that `to_json` writes onto graph.json. This keeps the
    cube's colors correct even when `.graph3d_analysis.json` is stale relative to
    graph.json (a common state right after `graph3d update`).
    """
    cid = node_community.get(node_id)
    if cid is None:
        raw = data.get("community")
        try:
            cid = int(raw)
        except (TypeError, ValueError):
            cid = 0
    return int(cid)


# Node shape encodes the source-file "shape" (file_type), giving a second visual
# channel alongside cluster color: color = cluster, shape = node kind.
SHAPE_BY_FILETYPE = {
    "code": "square",
    "document": "circle",
    "rationale": "diamond",
    "schema": "triangle",
    "concept": "hexagon",
    "paper": "circle",
    "image": "hexagon",
    "data": "square",
}


def _node_shape(file_type: str) -> str:
    return SHAPE_BY_FILETYPE.get(str(file_type or "").lower(), "square")


def _bitdot_nodes(
    G: nx.Graph,
    communities: dict[int, list[str]],
    community_labels: dict[int, str] | None,
) -> list[dict[str, Any]]:
    node_community = _node_community_map(communities)
    degree = dict(G.degree())
    max_degree = max(degree.values(), default=1) or 1
    positions = _layout_positions(G)

    # Directed in/out degree from the true (un-canonicalized) edge endpoints.
    out_deg: Counter[str] = Counter()
    in_deg: Counter[str] = Counter()
    for u, v, data in G.edges(data=True):
        s = str(data.get("_src", u))
        t = str(data.get("_tgt", v))
        out_deg[s] += 1
        in_deg[t] += 1

    # Occurrence = how many nodes share the same label text (duplicate fan-out).
    label_occurrence: Counter[str] = Counter(
        sanitize_label(data.get("label", str(node_id)))
        for node_id, data in G.nodes(data=True)
    )

    nodes: list[dict[str, Any]] = []
    for node_id, data in G.nodes(data=True):
        node_key = str(node_id)
        x, y, z = positions.get(node_key, (0.0, 0.0, 0.0))
        cid = _resolve_community(node_id, data, node_community)
        deg = degree.get(node_id, 0)
        is_god_node = deg >= max(2, max_degree * 0.35)
        label = sanitize_label(data.get("label", node_key))
        file_type = str(data.get("file_type") or "")
        nodes.append(
            {
                "id": node_key,
                "label": label,
                "x": x,
                "y": y,
                "z": z,
                "community": cid,
                "communityName": sanitize_label(
                    (community_labels or {}).get(cid, f"Cluster {cid}")
                ),
                "color": _community_color(cid),
                "shape": _node_shape(file_type),
                "degree": deg,
                "inDegree": in_deg.get(node_key, 0),
                "outDegree": out_deg.get(node_key, 0),
                "occurrence": label_occurrence.get(label, 1),
                "size": round(4 + 14 * (deg / max_degree), 2),
                "god": is_god_node,
                "fileType": file_type,
                "sourceFile": sanitize_label(str(data.get("source_file") or "")),
                "sourceLocation": sanitize_label(str(data.get("source_location") or "")),
            }
        )
    return nodes


def _bitdot_edges(G: nx.Graph) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for u, v, data in G.edges(data=True):
        confidence = str(data.get("confidence", "EXTRACTED"))
        relation = str(data.get("relation", ""))
        true_src = str(data.get("_src", u))
        true_tgt = str(data.get("_tgt", v))
        edges.append(
            {
                "from": true_src,
                "to": true_tgt,
                "relation": sanitize_label(relation),
                "confidence": confidence,
                "color": _relation_color(relation),
                "opacity": 0.5 if confidence == "EXTRACTED" else 0.2,
                "width": 1.25 if confidence == "EXTRACTED" else 0.75,
            }
        )
    return edges


def _bitdot_clusters(
    nodes: list[dict[str, Any]],
    community_labels: dict[int, str] | None,
    limit: int = 60,
) -> list[dict[str, Any]]:
    """Cluster legend built from resolved node clusters, sorted by membership."""
    counts: Counter[int] = Counter(n["community"] for n in nodes)
    clusters: list[dict[str, Any]] = []
    for cid, count in counts.most_common(limit):
        clusters.append(
            {
                "cid": cid,
                "label": sanitize_label((community_labels or {}).get(cid, f"Cluster {cid}")),
                "color": _community_color(cid),
                "count": count,
            }
        )
    return clusters


def _pattern_summary(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Connection patterns (relation types) present, with occurrence counts.

    Each pattern is tagged with its canonical umbrella word from
    ``graph3d.terminology`` (dataflow, schema, hierarchy, reference, ...) so the
    legend speaks the shared vocabulary used across the engine and 3dkg.
    """
    # Most-specific-first so e.g. contains_schema_path reads as "schema".
    _group_priority = ("schema", "hierarchy", "dataflow", "reference", "containment", "rationale")

    def _relation_group(relation: str) -> str:
        rel = str(relation).lower()
        for g in _group_priority:
            if rel in terminology.PREDICATE_GROUPS.get(g, ()):
                return g
        return ""

    counts: Counter[str] = Counter(e["relation"] for e in edges)
    patterns: list[dict[str, Any]] = []
    for relation, count in counts.most_common():
        patterns.append(
            {
                "relation": relation,
                "color": _relation_color(relation),
                "count": count,
                "schema": "schema" in relation,
                "group": _relation_group(relation),
            }
        )
    return patterns


def _bitdot_styles() -> str:
    return """<style>
  * { box-sizing: border-box; }
  body { margin: 0; height: 100vh; overflow: hidden; background: #070812; color: #e6edf3;
         font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         display: grid; grid-template-columns: 1fr 360px; }
  #cube-wrap { position: relative; min-width: 0; min-height: 0;
               background: radial-gradient(circle at center, #151a2f 0, #070812 70%); }
  #cube { display: block; width: 100%; height: 100%; cursor: grab; }
  #cube.dragging { cursor: grabbing; }
  #hud { position: absolute; left: 14px; top: 14px; padding: 10px 12px;
         border: 1px solid rgba(125,193,255,.25); border-radius: 10px;
         background: rgba(7,8,18,.82); backdrop-filter: blur(8px); font-size: 12px; color: #b7c2d4; }
  #hud .tag { display: inline-block; margin-top: 4px; margin-right: 4px; padding: 1px 7px;
              border-radius: 999px; font-size: 11px; background: #1a2544; border: 1px solid #334061; }
  #zoombar { position: absolute; right: 14px; bottom: 14px; display: flex; gap: 6px; align-items: center;
             background: rgba(7,8,18,.82); border: 1px solid #26304d; border-radius: 10px; padding: 6px 8px; }
  #zoombar button { width: 30px; height: 28px; }
  #sidebar { background: #111426; border-left: 1px solid #26304d; overflow: auto; padding: 14px; }
  h1 { margin: 0 0 6px; font-size: 18px; letter-spacing: .02em; }
  h2 { margin: 16px 0 8px; font-size: 12px; text-transform: uppercase; letter-spacing: .09em; color: #8b9aba; }
  p { margin: 0 0 10px; color: #9aa8bd; line-height: 1.45; font-size: 13px; }
  label { display: block; margin: 8px 0 4px; font-size: 12px; color: #aebbd0; }
  select, input[type="range"], input[type="search"] { width: 100%; }
  select, input[type="search"] { background: #070812; color: #e6edf3; border: 1px solid #334061;
            border-radius: 7px; padding: 8px; outline: none; }
  input[type="range"] { accent-color: #7dc1ff; }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
  button { border: 1px solid #334061; background: #1a2544; color: #e6edf3; border-radius: 7px;
           padding: 8px 10px; cursor: pointer; font-size: 12px; }
  button:hover { background: #26355d; }
  button.active { background: #1f6feb; border-color: #388bfd; }
  #info { min-height: 96px; padding: 11px; border: 1px solid #273451; border-radius: 9px;
          background: #0a0d1a; font-size: 12px; line-height: 1.5; }
  .ititle { font-weight: 700; font-size: 13px; margin-bottom: 6px; word-break: break-word; }
  .irow { display: grid; grid-template-columns: 92px 1fr; gap: 4px 8px; }
  .irow span { color: #8b9aba; } .irow b { color: #e6edf3; font-weight: 600; word-break: break-word; }
  .iacts { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0 6px; }
  .iacts button { padding: 5px 8px; }
  .iconn { margin-top: 8px; }
  .ihdr { color: #8b9aba; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 3px; }
  .conn { display: block; padding: 3px 6px; margin: 2px 0; border-radius: 5px; cursor: pointer;
          background: #0e1424; border-left: 3px solid #334061; white-space: nowrap; overflow: hidden;
          text-overflow: ellipsis; }
  .conn:hover { background: #1a2544; }
  .conn b { color: #7dc1ff; font-weight: 600; }
  #clusters, #patterns { display: flex; flex-direction: column; gap: 4px; max-height: 220px; overflow: auto; }
  .legend-item { display: grid; grid-template-columns: 14px 1fr auto; gap: 8px; align-items: center;
                 font-size: 12px; color: #b8c5d8; cursor: pointer; padding: 2px 4px; border-radius: 5px; }
  .legend-item:hover { background: #1a2544; }
  .legend-item.active { background: #1f3a66; }
  .legend-item.off { opacity: .4; }
  .legend-item .count { color: #697894; }
  .swatch { width: 13px; height: 13px; border-radius: 3px; flex-shrink: 0; }
  .patrow { display: grid; grid-template-columns: 16px 13px 1fr auto; gap: 8px; align-items: center;
            font-size: 12px; color: #b8c5d8; padding: 2px 2px; }
  .patrow .count { color: #697894; }
  .shapes { display: flex; flex-wrap: wrap; gap: 10px; margin: 4px 0 2px; font-size: 11px; color: #aebbd0; }
  .shapes span { display: inline-flex; align-items: center; gap: 5px; }
  .sh { width: 12px; height: 12px; background: #aebbd0; display: inline-block; }
  .sh-circle { border-radius: 50%; }
  .sh-diamond { transform: rotate(45deg); }
  .sh-triangle { width: 0; height: 0; background: transparent;
                 border-left: 7px solid transparent; border-right: 7px solid transparent;
                 border-bottom: 12px solid #aebbd0; }
  .sh-hexagon { clip-path: polygon(25% 0,75% 0,100% 50%,75% 100%,25% 100%,0 50%); }
  .chip { display: inline-flex; align-items: center; gap: 6px; padding: 3px 8px; border-radius: 999px;
          font-size: 12px; border: 1px solid #334061; background: #0e1424; margin: 2px 4px 2px 0;
          max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .chip.source { border-color: #3fb950; } .chip.dest { border-color: #f85149; }
  .hint { color: #6f7d96; font-size: 11px; }
</style>"""


def _bitdot_script(
    nodes_json: str, edges_json: str, clusters_json: str, patterns_json: str
) -> str:
    return f"""<script>
const RAW_NODES = {nodes_json};
const RAW_EDGES = {edges_json};
const CLUSTERS = {clusters_json};
const PATTERNS = {patterns_json};
const TEMPLATE_KIND = "{BITDOT_CUBE_SCHEMA_KIND}";
const TEMPLATE_VERSION = "{BITDOT_CUBE_SCHEMA_VERSION}";

const canvas = document.getElementById('cube');
const ctx = canvas.getContext('2d');
const info = document.getElementById('info');
const nodeById = new Map(RAW_NODES.map(n => [n.id, n]));

// Adjacency for neighborhood focus and path finding.
const adj = new Map();
function addAdj(a, b, relation, dir) {{
  if (!adj.has(a)) adj.set(a, []);
  adj.get(a).push({{ id: b, relation, dir }});
}}
for (const e of RAW_EDGES) {{ addAdj(e.from, e.to, e.relation, 'out'); addAdj(e.to, e.from, e.relation, 'in'); }}
const SEP = String.fromCharCode(0);
const edgeKey = (a, b) => (a < b ? a + SEP + b : b + SEP + a);

const state = {{
  yaw: -0.72, pitch: 0.54, zoom: 1.0, panX: 0, panY: 0,
  sliceMode: 'all', layer: 50, thickness: 18,
  showEdges: true, showLabels: false, search: '',
  hover: null, selected: null,
  focus: null, focusDepth: 1, focusSet: null,
  clusterOnly: null, hiddenPatterns: new Set(),
  source: null, dest: null, pathNodes: new Set(), pathEdges: new Set(),
}};

function esc(s) {{
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}}
const $ = id => document.getElementById(id);

function resize() {{
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.floor(rect.width * dpr));
  canvas.height = Math.max(1, Math.floor(rect.height * dpr));
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  draw();
}}

function rotatePoint(p) {{
  const cy = Math.cos(state.yaw), sy = Math.sin(state.yaw);
  const cp = Math.cos(state.pitch), sp = Math.sin(state.pitch);
  const x1 = p.x * cy - p.z * sy, z1 = p.x * sy + p.z * cy;
  const y1 = p.y * cp - z1 * sp, z2 = p.y * sp + z1 * cp;
  return {{ x: x1, y: y1, z: z2 }};
}}

function project(p) {{
  const r = rotatePoint(p);
  const rect = canvas.getBoundingClientRect();
  const base = Math.min(rect.width, rect.height) * 0.36 * state.zoom;
  const persp = 1 / (2.7 - r.z * 0.55);
  return {{
    x: rect.width / 2 + state.panX + r.x * base * persp * 2.1,
    y: rect.height / 2 + state.panY - r.y * base * persp * 2.1,
    z: r.z, scale: persp,
  }};
}}

function normalizedForSlice(n) {{
  if (state.sliceMode === 'vertical-x') return (n.x + 1) / 2;
  if (state.sliceMode === 'vertical-y') return (n.y + 1) / 2;
  if (state.sliceMode === 'horizontal-z') return (n.z + 1) / 2;
  if (state.sliceMode === 'crosswise') return (n.x + n.y + n.z + 3) / 6;
  return 0.5;
}}
function isInSlice(n) {{
  if (state.sliceMode === 'all') return true;
  const t = state.layer / 100, th = state.thickness / 100;
  return Math.abs(normalizedForSlice(n) - t) <= th / 2;
}}
function matchesSearch(n) {{
  const q = state.search.toLowerCase();
  return n.label.toLowerCase().includes(q) || n.sourceFile.toLowerCase().includes(q)
      || n.communityName.toLowerCase().includes(q);
}}

function computeFocusSet() {{
  if (!state.focus) {{ state.focusSet = null; return; }}
  const seen = new Set([state.focus]);
  let frontier = [state.focus];
  for (let d = 0; d < state.focusDepth; d++) {{
    const next = [];
    for (const id of frontier)
      for (const nb of (adj.get(id) || []))
        if (!seen.has(nb.id)) {{ seen.add(nb.id); next.push(nb.id); }}
    frontier = next;
  }}
  state.focusSet = seen;
}}

function computePath() {{
  state.pathNodes = new Set(); state.pathEdges = new Set();
  if (!state.source || !state.dest || state.source === state.dest) return;
  const prev = new Map(), seen = new Set([state.source]);
  let q = [state.source], found = false;
  while (q.length && !found) {{
    const next = [];
    for (const id of q) {{
      for (const nb of (adj.get(id) || [])) {{
        if (seen.has(nb.id)) continue;
        seen.add(nb.id); prev.set(nb.id, id);
        if (nb.id === state.dest) {{ found = true; break; }}
        next.push(nb.id);
      }}
      if (found) break;
    }}
    q = next;
  }}
  if (!found) return;
  let cur = state.dest;
  while (cur !== undefined) {{
    state.pathNodes.add(cur);
    const p = prev.get(cur);
    if (p !== undefined) state.pathEdges.add(edgeKey(cur, p));
    cur = p;
  }}
}}

function visibleNodes() {{
  return RAW_NODES.filter(n => {{
    if (!isInSlice(n)) return false;
    if (state.search && !matchesSearch(n)) return false;
    if (state.clusterOnly !== null && n.community !== state.clusterOnly) return false;
    if (state.focusSet && !state.focusSet.has(n.id)) return false;
    return true;
  }});
}}

function drawCube() {{
  const verts = [];
  for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) verts.push({{x,y,z}});
  ctx.save();
  ctx.strokeStyle = 'rgba(125,193,255,.22)';
  ctx.lineWidth = 1;
  for (let i = 0; i < verts.length; i++)
    for (let j = i + 1; j < verts.length; j++) {{
      const d = Math.abs(verts[i].x-verts[j].x)+Math.abs(verts[i].y-verts[j].y)+Math.abs(verts[i].z-verts[j].z);
      if (d === 2) {{ const pa = project(verts[i]), pb = project(verts[j]);
        ctx.beginPath(); ctx.moveTo(pa.x,pa.y); ctx.lineTo(pb.x,pb.y); ctx.stroke(); }}
    }}
  ctx.restore();
}}

function drawSlicePlane() {{
  if (state.sliceMode === 'all') return;
  const v = state.layer / 50 - 1;
  let c;
  if (state.sliceMode === 'vertical-x') c = [{{x:v,y:-1,z:-1}},{{x:v,y:1,z:-1}},{{x:v,y:1,z:1}},{{x:v,y:-1,z:1}}];
  else if (state.sliceMode === 'vertical-y') c = [{{x:-1,y:v,z:-1}},{{x:1,y:v,z:-1}},{{x:1,y:v,z:1}},{{x:-1,y:v,z:1}}];
  else if (state.sliceMode === 'horizontal-z') c = [{{x:-1,y:-1,z:v}},{{x:1,y:-1,z:v}},{{x:1,y:1,z:v}},{{x:-1,y:1,z:v}}];
  else c = [{{x:-1,y:1,z:1}},{{x:1,y:-1,z:1}},{{x:1,y:1,z:-1}},{{x:-1,y:-1,z:-1}}];
  ctx.save();
  ctx.fillStyle = 'rgba(125,193,255,.07)'; ctx.strokeStyle = 'rgba(125,193,255,.4)';
  ctx.beginPath(); c.map(project).forEach((p,i)=> i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));
  ctx.closePath(); ctx.fill(); ctx.stroke(); ctx.restore();
}}

function drawEdges(visibleIds) {{
  if (!state.showEdges) return;
  const dimAll = state.pathNodes.size > 0;
  ctx.save();
  for (const e of RAW_EDGES) {{
    if (state.hiddenPatterns.has(e.relation)) continue;
    if (!visibleIds.has(e.from) || !visibleIds.has(e.to)) continue;
    const a = nodeById.get(e.from), b = nodeById.get(e.to);
    if (!a || !b) continue;
    const pa = project(a), pb = project(b);
    const onPath = state.pathEdges.has(edgeKey(e.from, e.to));
    if (onPath) {{ ctx.globalAlpha = 0.95; ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 2.6; }}
    else {{ ctx.globalAlpha = dimAll ? e.opacity * 0.35 : e.opacity; ctx.strokeStyle = e.color; ctx.lineWidth = e.width; }}
    ctx.beginPath(); ctx.moveTo(pa.x,pa.y); ctx.lineTo(pb.x,pb.y); ctx.stroke();
  }}
  ctx.globalAlpha = 1; ctx.restore();
}}

function drawShape(x, y, s, shape) {{
  if (shape === 'circle') {{ ctx.beginPath(); ctx.arc(x,y,s,0,Math.PI*2); ctx.fill(); ctx.stroke(); }}
  else if (shape === 'diamond') {{ ctx.beginPath(); ctx.moveTo(x,y-s); ctx.lineTo(x+s,y); ctx.lineTo(x,y+s); ctx.lineTo(x-s,y); ctx.closePath(); ctx.fill(); ctx.stroke(); }}
  else if (shape === 'triangle') {{ ctx.beginPath(); ctx.moveTo(x,y-s); ctx.lineTo(x+s,y+s); ctx.lineTo(x-s,y+s); ctx.closePath(); ctx.fill(); ctx.stroke(); }}
  else if (shape === 'hexagon') {{ ctx.beginPath(); for (let i=0;i<6;i++){{ const a=Math.PI/3*i-Math.PI/6, px=x+s*Math.cos(a), py=y+s*Math.sin(a); i?ctx.lineTo(px,py):ctx.moveTo(px,py); }} ctx.closePath(); ctx.fill(); ctx.stroke(); }}
  else {{ ctx.fillRect(x-s,y-s,2*s,2*s); ctx.strokeRect(x-s,y-s,2*s,2*s); }}
}}

function drawNodes(visible) {{
  const projected = visible.map(n => ({{ n, p: project(n) }})).sort((a,b)=>a.p.z-b.p.z);
  const dimAll = state.pathNodes.size > 0;
  for (const item of projected) {{
    const n = item.n, p = item.p;
    const half = Math.max(2.5, n.size * p.scale * 1.45);
    const isHover = n.id === state.hover, isSel = n.id === state.selected;
    const isSource = n.id === state.source, isDest = n.id === state.dest;
    const onPath = state.pathNodes.has(n.id);
    ctx.save();
    ctx.globalAlpha = (dimAll && !onPath && !isSource && !isDest) ? 0.32 : 1;
    ctx.fillStyle = (isHover || isSel) ? '#ffffff' : n.color;
    ctx.strokeStyle = isSource ? '#3fb950' : isDest ? '#f85149' : (onPath || isHover || isSel) ? '#ffffff'
                      : n.god ? '#ffd166' : n.color;
    ctx.lineWidth = (isHover || isSel || isSource || isDest || onPath) ? 2.4 : 1;
    drawShape(p.x, p.y, half, n.shape);
    if (state.showLabels && (n.god || isHover || isSel || onPath || isSource || isDest)) {{
      ctx.globalAlpha = 1; ctx.fillStyle = 'rgba(230,237,243,.96)'; ctx.font = '11px sans-serif';
      ctx.fillText(n.label, p.x + half + 4, p.y - half);
    }}
    ctx.restore();
  }}
}}

function draw() {{
  const rect = canvas.getBoundingClientRect();
  ctx.clearRect(0, 0, rect.width, rect.height);
  const visible = visibleNodes();
  const visibleIds = new Set(visible.map(n => n.id));
  drawCube(); drawSlicePlane(); drawEdges(visibleIds); drawNodes(visible);
  $('visible-count').textContent = String(visible.length);
  $('layer-value').textContent = state.layer + '%';
  $('thickness-value').textContent = state.thickness + '%';
  $('zoom-value').textContent = state.zoom.toFixed(1) + 'x';
  $('depth-value').textContent = state.focusDepth;
  const tags = [];
  if (state.focus) tags.push('focus: ' + esc((nodeById.get(state.focus)||{{}}).label || ''));
  if (state.clusterOnly !== null) tags.push('cluster only');
  if (state.hiddenPatterns.size) tags.push(state.hiddenPatterns.size + ' patterns hidden');
  if (state.pathNodes.size) tags.push('path: ' + state.pathNodes.size + ' nodes');
  $('hud-tags').innerHTML = tags.map(t => '<span class="tag">' + t + '</span>').join('');
}}

function nearestNode(x, y) {{
  let best = null, bestD = 16;
  for (const n of visibleNodes()) {{ const p = project(n); const d = Math.hypot(p.x-x, p.y-y); if (d < bestD) {{ best = n; bestD = d; }} }}
  return best;
}}

function showNode(n) {{
  if (!n) {{ info.innerHTML = '<span class="hint">Click a node to inspect its cluster, shape, occurrence, and source/destination connections.</span>'; return; }}
  const outs = (adj.get(n.id) || []).filter(x => x.dir === 'out');
  const ins  = (adj.get(n.id) || []).filter(x => x.dir === 'in');
  const dest = x => '<span class="conn" data-id="' + esc(x.id) + '"><b>' + esc(x.relation) + '</b> &rarr; ' + esc((nodeById.get(x.id)||{{}}).label || x.id) + '</span>';
  const src  = x => '<span class="conn" data-id="' + esc(x.id) + '">' + esc((nodeById.get(x.id)||{{}}).label || x.id) + ' <b>' + esc(x.relation) + '</b> &rarr;</span>';
  info.innerHTML =
    '<div class="ititle">' + esc(n.label) + '</div>' +
    '<div class="irow"><span>Shape</span><b>' + esc(n.fileType || 'unknown') + '</b></div>' +
    '<div class="irow"><span>Cluster</span><b>' + esc(n.communityName) + '</b></div>' +
    '<div class="irow"><span>Occurrence</span><b>' + n.occurrence + 'x in graph</b></div>' +
    '<div class="irow"><span>Degree</span><b>' + n.degree + ' (in ' + n.inDegree + ' / out ' + n.outDegree + ')</b></div>' +
    '<div class="irow"><span>Source</span><b>' + esc(n.sourceFile || '-') + (n.sourceLocation ? ' :' + esc(n.sourceLocation) : '') + '</b></div>' +
    '<div class="iacts">' +
      '<button data-act="focus" class="' + (state.focus === n.id ? 'active' : '') + '">Focus neighborhood</button>' +
      '<button data-act="source">Set as Source</button>' +
      '<button data-act="dest">Set as Destination</button>' +
    '</div>' +
    '<div class="iconn"><div class="ihdr">Destinations (outgoing ' + outs.length + ')</div>' +
      (outs.slice(0,40).map(dest).join('') || '<span class="hint">none</span>') + '</div>' +
    '<div class="iconn"><div class="ihdr">Sources (incoming ' + ins.length + ')</div>' +
      (ins.slice(0,40).map(src).join('') || '<span class="hint">none</span>') + '</div>';
  info.querySelectorAll('.conn').forEach(el => el.onclick = () => selectNode(el.getAttribute('data-id')));
  info.querySelectorAll('[data-act]').forEach(btn => btn.onclick = () => {{
    const a = btn.getAttribute('data-act');
    if (a === 'focus') {{ state.focus = (state.focus === n.id) ? null : n.id; computeFocusSet(); }}
    if (a === 'source') {{ state.source = n.id; computePath(); }}
    if (a === 'dest') {{ state.dest = n.id; computePath(); }}
    syncChips(); showNode(n); draw();
  }});
}}

function selectNode(id) {{ const n = nodeById.get(id); if (!n) return; state.selected = id; showNode(n); draw(); }}

function syncChips() {{
  const s = state.source ? nodeById.get(state.source) : null;
  const d = state.dest ? nodeById.get(state.dest) : null;
  $('chip-source').innerHTML = s ? '<span class="chip source">Source: ' + esc(s.label) + '</span>' : '<span class="hint">Source: not set</span>';
  $('chip-dest').innerHTML = d ? '<span class="chip dest">Destination: ' + esc(d.label) + '</span>' : '<span class="hint">Destination: not set</span>';
}}

// ---- pointer interaction: left-drag rotate, right-drag pan, wheel zoom ----
let drag = null;
canvas.addEventListener('contextmenu', e => e.preventDefault());
canvas.addEventListener('pointerdown', e => {{
  canvas.classList.add('dragging');
  drag = {{ x: e.clientX, y: e.clientY, yaw: state.yaw, pitch: state.pitch,
           panX: state.panX, panY: state.panY, pan: (e.button === 2 || e.shiftKey) }};
  canvas.setPointerCapture(e.pointerId);
}});
canvas.addEventListener('pointermove', e => {{
  const rect = canvas.getBoundingClientRect();
  if (drag) {{
    if (drag.pan) {{ state.panX = drag.panX + (e.clientX - drag.x); state.panY = drag.panY + (e.clientY - drag.y); }}
    else {{ state.yaw = drag.yaw + (e.clientX - drag.x) * 0.008;
            state.pitch = Math.max(-1.35, Math.min(1.35, drag.pitch + (e.clientY - drag.y) * 0.008)); }}
    draw();
  }} else {{
    const n = nearestNode(e.clientX - rect.left, e.clientY - rect.top);
    state.hover = n ? n.id : null; canvas.style.cursor = n ? 'pointer' : 'grab'; draw();
  }}
}});
canvas.addEventListener('pointerup', e => {{ canvas.classList.remove('dragging'); drag = null; canvas.releasePointerCapture(e.pointerId); }});
canvas.addEventListener('click', e => {{
  const rect = canvas.getBoundingClientRect();
  const n = nearestNode(e.clientX - rect.left, e.clientY - rect.top);
  state.selected = n ? n.id : null; showNode(n); draw();
}});
canvas.addEventListener('dblclick', e => {{
  const rect = canvas.getBoundingClientRect();
  const n = nearestNode(e.clientX - rect.left, e.clientY - rect.top);
  if (n) {{ state.focus = n.id; computeFocusSet(); state.zoom = Math.min(10, Math.max(state.zoom, 2.4)); state.selected = n.id; showNode(n); draw(); }}
}});
canvas.addEventListener('wheel', e => {{
  e.preventDefault();
  state.zoom = Math.max(0.35, Math.min(10, state.zoom * (e.deltaY < 0 ? 1.1 : 0.9)));
  draw();
}}, {{ passive: false }});

// ---- controls ----
$('slice-mode').onchange = e => {{ state.sliceMode = e.target.value; draw(); }};
$('slice-layer').oninput = e => {{ state.layer = +e.target.value; draw(); }};
$('slice-thickness').oninput = e => {{ state.thickness = +e.target.value; draw(); }};
$('focus-depth').oninput = e => {{ state.focusDepth = +e.target.value; computeFocusSet(); draw(); }};
$('show-edges').onchange = e => {{ state.showEdges = e.target.checked; draw(); }};
$('show-labels').onchange = e => {{ state.showLabels = e.target.checked; draw(); }};
$('search').oninput = e => {{ state.search = e.target.value.trim(); draw(); }};
$('prev-layer').onclick = () => {{ $('slice-layer').value = Math.max(0, state.layer - 5); state.layer = +$('slice-layer').value; draw(); }};
$('next-layer').onclick = () => {{ $('slice-layer').value = Math.min(100, state.layer + 5); state.layer = +$('slice-layer').value; draw(); }};
$('zoom-in').onclick = () => {{ state.zoom = Math.min(10, state.zoom * 1.25); draw(); }};
$('zoom-out').onclick = () => {{ state.zoom = Math.max(0.35, state.zoom * 0.8); draw(); }};
$('reset-view').onclick = () => {{ state.yaw = -0.72; state.pitch = 0.54; state.zoom = 1.0; state.panX = 0; state.panY = 0; draw(); }};
$('clear-focus').onclick = () => {{ state.focus = null; state.focusSet = null; state.clusterOnly = null; document.querySelectorAll('.legend-item.active').forEach(el=>el.classList.remove('active')); draw(); }};
$('clear-path').onclick = () => {{ state.source = null; state.dest = null; state.pathNodes = new Set(); state.pathEdges = new Set(); syncChips(); draw(); }};
$('reset-filters').onclick = () => {{
  state.focus = null; state.focusSet = null; state.clusterOnly = null; state.hiddenPatterns = new Set();
  state.source = null; state.dest = null; state.pathNodes = new Set(); state.pathEdges = new Set();
  state.search = ''; $('search').value = '';
  document.querySelectorAll('.legend-item.active').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('.legend-item.off').forEach(el=>el.classList.remove('off'));
  document.querySelectorAll('.patrow input').forEach(cb => cb.checked = true);
  syncChips(); draw();
}};
$('export-png').onclick = () => {{
  const a = document.createElement('a'); a.download = 'bitdot-cube.png'; a.href = canvas.toDataURL('image/png'); a.click();
}};
$('copy-json').onclick = async () => {{
  const tpl = {{
    kind: TEMPLATE_KIND, version: TEMPLATE_VERSION,
    camera: {{ yaw: state.yaw, pitch: state.pitch, zoom: state.zoom, panX: state.panX, panY: state.panY }},
    slice: {{ mode: state.sliceMode, layer: state.layer, thickness: state.thickness }},
    focus: state.focus, focusDepth: state.focusDepth, clusterOnly: state.clusterOnly,
    hiddenPatterns: Array.from(state.hiddenPatterns), source: state.source, destination: state.dest,
    nodes: RAW_NODES, edges: RAW_EDGES,
  }};
  try {{ await navigator.clipboard.writeText(JSON.stringify(tpl, null, 2)); }} catch (err) {{}}
}};

// ---- cluster legend (click a cluster to isolate it) ----
const clustersEl = $('clusters');
for (const c of CLUSTERS) {{
  const el = document.createElement('div');
  el.className = 'legend-item';
  el.innerHTML = '<span class="swatch" style="background:' + c.color + '"></span><span>' + esc(c.label) + '</span><span class="count">' + c.count + '</span>';
  el.onclick = () => {{
    if (state.clusterOnly === c.cid) {{ state.clusterOnly = null; el.classList.remove('active'); }}
    else {{ state.clusterOnly = c.cid; document.querySelectorAll('#clusters .legend-item').forEach(x=>x.classList.remove('active')); el.classList.add('active'); }}
    draw();
  }};
  clustersEl.appendChild(el);
}}

// ---- connection pattern filter (toggle relation types, incl. schema paths) ----
const patternsEl = $('patterns');
for (const p of PATTERNS) {{
  const row = document.createElement('div');
  row.className = 'patrow';
  const cb = document.createElement('input');
  cb.type = 'checkbox'; cb.checked = true; cb.style.width = '14px';
  cb.onchange = () => {{ if (cb.checked) state.hiddenPatterns.delete(p.relation); else state.hiddenPatterns.add(p.relation); draw(); }};
  const sw = document.createElement('span'); sw.className = 'swatch'; sw.style.background = p.color;
  const lbl = document.createElement('span'); lbl.textContent = p.relation + (p.group ? ' (' + p.group + ')' : '');
  const cnt = document.createElement('span'); cnt.className = 'count'; cnt.textContent = p.count;
  row.appendChild(cb); row.appendChild(sw); row.appendChild(lbl); row.appendChild(cnt);
  patternsEl.appendChild(row);
}}

window.addEventListener('resize', resize);
syncChips();
resize();
</script>"""


def _bitdot_html(
    *,
    title: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    clusters: list[dict[str, Any]],
    patterns: list[dict[str, Any]],
    cluster_count: int,
) -> str:
    nodes_json = _js_safe(nodes)
    edges_json = _js_safe(edges)
    clusters_json = _js_safe(clusters)
    patterns_json = _js_safe(patterns)
    cluster_note = f" (top {len(clusters)})" if cluster_count > len(clusters) else ""
    stats = (
        f"{len(nodes)} nodes &middot; {len(edges)} connections &middot; "
        f"{cluster_count} clusters &middot; {len(patterns)} patterns"
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>graph3d bitdot cube - {_html.escape(title)}</title>
{_bitdot_styles()}
</head>
<body>
<main id="cube-wrap">
  <canvas id="cube" aria-label="Bitdot cube node-cluster plotter"></canvas>
  <div id="hud">
    <div><b>Bitdot Cube</b></div>
    <div>Showing <span id="visible-count">0</span> / {len(nodes)} nodes</div>
    <div id="hud-tags"></div>
  </div>
  <div id="zoombar">
    <button id="zoom-out" type="button" title="Zoom out">-</button>
    <span id="zoom-value" style="min-width:46px;text-align:center">1.0x</span>
    <button id="zoom-in" type="button" title="Zoom in">+</button>
  </div>
</main>
<aside id="sidebar">
  <h1>Bitdot Cube Plotter</h1>
  <p>Left-drag rotates, right-drag (or Shift-drag) pans, scroll zooms. Click a node
     to inspect it; double-click to focus its neighborhood.</p>

  <h2>Shapes (node kind)</h2>
  <div class="shapes">
    <span><i class="sh"></i>code</span>
    <span><i class="sh sh-circle"></i>document</span>
    <span><i class="sh sh-diamond"></i>rationale</span>
    <span><i class="sh sh-triangle"></i>schema</span>
    <span><i class="sh sh-hexagon"></i>concept</span>
  </div>

  <h2>Slice (layer)</h2>
  <label for="slice-mode">Slice direction</label>
  <select id="slice-mode">
    <option value="all">All layers</option>
    <option value="vertical-x">Vertical slice: X plane</option>
    <option value="vertical-y">Vertical slice: Y plane</option>
    <option value="horizontal-z">Horizontal slice: Z plane</option>
    <option value="crosswise">Crosswise diagonal slice</option>
  </select>
  <label for="slice-layer">Layer: <span id="layer-value">50%</span></label>
  <input id="slice-layer" type="range" min="0" max="100" value="50">
  <label for="slice-thickness">Thickness: <span id="thickness-value">18%</span></label>
  <input id="slice-thickness" type="range" min="2" max="100" value="18">
  <div class="row">
    <button id="prev-layer" type="button">Previous layer</button>
    <button id="next-layer" type="button">Next layer</button>
  </div>

  <h2>Focus &amp; path</h2>
  <label for="focus-depth">Neighborhood depth: <span id="depth-value">1</span> hop(s)</label>
  <input id="focus-depth" type="range" min="1" max="3" value="1">
  <div id="chip-source"></div>
  <div id="chip-dest"></div>
  <div class="row">
    <button id="clear-focus" type="button">Clear focus/cluster</button>
    <button id="clear-path" type="button">Clear path</button>
  </div>

  <h2>View</h2>
  <label><input id="show-edges" type="checkbox" checked> Show connections</label>
  <label><input id="show-labels" type="checkbox"> Show labels (hubs)</label>
  <label for="search">Search nodes</label>
  <input id="search" type="search" placeholder="Filter by node label, source file, or cluster">
  <div class="row">
    <button id="reset-view" type="button">Reset view</button>
    <button id="export-png" type="button">Export PNG</button>
  </div>
  <div class="row" style="margin-top:8px">
    <button id="reset-filters" type="button">Reset all filters</button>
    <button id="copy-json" type="button">Copy template JSON</button>
  </div>

  <h2>Selected node</h2>
  <div id="info"><span class="hint">Click a node to inspect its cluster, shape, occurrence, and source/destination connections.</span></div>

  <h2>Stats</h2>
  <div class="irow"><span>Nodes</span><b>{len(nodes)}</b></div>
  <div class="irow"><span>Connections</span><b>{len(edges)}</b></div>
  <div class="irow"><span>Clusters</span><b>{cluster_count}</b></div>
  <div class="irow"><span>Patterns</span><b>{len(patterns)}</b></div>
  <p class="hint" style="margin-top:8px">{stats}</p>

  <h2>Connection patterns</h2>
  <p class="hint">Toggle a pattern to map only those connections (schema paths included).</p>
  <div id="patterns"></div>

  <h2>Clusters{cluster_note}</h2>
  <p class="hint">Click a cluster to isolate it.</p>
  <div id="clusters"></div>
</aside>
{_bitdot_script(nodes_json, edges_json, clusters_json, patterns_json)}
</body>
</html>"""


def to_bitdot_cube_html(
    G: nx.Graph,
    communities: dict[int, list[str]],
    output_path: str,
    community_labels: dict[int, str] | None = None,
    node_limit: int | None = None,
) -> None:
    """Generate a self-contained 3D bitdot cube node/cluster plotter.

    Tools: layer slicing (vertical/horizontal/crosswise), single-node
    neighborhood focus, cluster isolation, a source->destination path finder,
    connection-pattern (relation) filtering including schema paths, node shapes
    by kind, pan/zoom, occurrence counts, and PNG/JSON export.

    The renderer intentionally uses plain HTML canvas and embedded JSON so the
    artifact stays portable, CDN-free, and aligned with graph3d's existing
    no-server visualization model.
    """
    limit = node_limit if node_limit is not None else _viz_node_limit()
    if limit <= 0:
        raise ValueError("Bitdot cube visualization disabled by node limit")
    if G.number_of_nodes() > limit:
        raise ValueError(
            f"Graph has {G.number_of_nodes()} nodes - too large for bitdot cube "
            f"(limit: {limit}). Raise GRAPH3D_VIZ_NODE_LIMIT or use --node-limit."
        )

    nodes = _bitdot_nodes(G, communities, community_labels)
    edges = _bitdot_edges(G)
    clusters = _bitdot_clusters(nodes, community_labels)
    patterns = _pattern_summary(edges)
    cluster_count = len({n["community"] for n in nodes})
    title = sanitize_label(str(output_path))
    html = _bitdot_html(
        title=title,
        nodes=nodes,
        edges=edges,
        clusters=clusters,
        patterns=patterns,
        cluster_count=cluster_count,
    )
    Path(output_path).write_text(html, encoding="utf-8")  # nosec
