import pytest

from twgbg.engine.graphs import DiGraph, random_digraph, path_graph


def test_random_graph_vertices():
    g = random_digraph(4, 0.5, seed=1)
    assert len(g.vertices()) == 4


def test_add_remove_vertex():
    g = path_graph(3)
    g.add_vertex("extra")
    assert "extra" in g.vertices()
    g.remove_vertex("extra")
    assert "extra" not in g.vertices()
