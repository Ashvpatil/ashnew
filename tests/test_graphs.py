from twgbg.engine.graphs import DiGraph


def test_graph_roundtrip():
    graph = DiGraph()
    graph.add_edge("a", "b")
    graph.add_edge("b", "c")
    payload = graph.to_dict()
    clone = DiGraph.from_dict(payload)
    assert set(graph.edges()) == set(clone.edges())
    assert graph.partitions() == clone.partitions()


def test_random_graph_seed():
    g1 = DiGraph.random_graph(4, 0.5, seed=42)
    g2 = DiGraph.random_graph(4, 0.5, seed=42)
    assert g1.to_dict() == g2.to_dict()
