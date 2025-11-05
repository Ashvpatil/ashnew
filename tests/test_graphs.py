from twgbg.engine.graphs import DiGraph, graph_to_dict, dict_to_graph, path_graph


def test_roundtrip():
    graph, start = path_graph(3)
    data = graph_to_dict(graph, start)
    graph2, start2 = dict_to_graph(data)
    assert graph2.succ == graph.succ
    assert start2 == start


def test_add_remove():
    g = DiGraph()
    g.add_vertex("A")
    g.add_edge("A", "B")
    assert "B" in g.successors("A")
    g.remove_edge("A", "B")
    assert "B" not in g.successors("A")
    g.remove_vertex("A")
    assert "A" not in list(g.vertices())
