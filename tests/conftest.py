from __future__ import annotations

# Shared pytest configuration for the graph3d test suite.
#
# NOTE: Warning suppression for the analyze tests (umap/hyppo/numba deprecations)
# now lives as @pytest.mark.filterwarnings decorators on the analyze test in
# tests/test_graph.py, so no collection-time hook is required here.
