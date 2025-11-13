from twgbg.engine.graphs import DiGraph


def test_add_and_remove_vertices():
    g = DiGraph()
    g.add_vertex("a")
    g.add_edge("a", "b")
    assert "a" in g
    assert "b" in g
    g.remove_vertex("b")
    assert "b" not in g


def test_json_roundtrip(tmp_path):
    g = DiGraph.path(3)
    path = tmp_path / "graph.json"
    g.dump_json(path)
    g2 = DiGraph.load_json(path)
    assert set(g2.vertices()) == {"0", "1", "2"}
