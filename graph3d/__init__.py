"""graph3d - extract · build · cluster · analyze · report."""


def __getattr__(name):
    # Lazy imports so `graph3d install` works before heavy deps are in place.
    _map = {
        "extract": ("graph3d.extract", "extract"),
        "collect_files": ("graph3d.extract", "collect_files"),
        "build_from_json": ("graph3d.build", "build_from_json"),
        "cluster": ("graph3d.cluster", "cluster"),
        "score_all": ("graph3d.cluster", "score_all"),
        "cohesion_score": ("graph3d.cluster", "cohesion_score"),
        "god_nodes": ("graph3d.analyze", "god_nodes"),
        "surprising_connections": ("graph3d.analyze", "surprising_connections"),
        "suggest_questions": ("graph3d.analyze", "suggest_questions"),
        "generate": ("graph3d.report", "generate"),
        "to_json": ("graph3d.export", "to_json"),
        "to_html": ("graph3d.export", "to_html"),
        "to_svg": ("graph3d.export", "to_svg"),
        "to_canvas": ("graph3d.export", "to_canvas"),
        "to_wiki": ("graph3d.wiki", "to_wiki"),
    }
    if name in _map:
        import importlib
        mod_name, attr = _map[name]
        mod = importlib.import_module(mod_name)
        return getattr(mod, attr)
    raise AttributeError(f"module 'graph3d' has no attribute {name!r}")
