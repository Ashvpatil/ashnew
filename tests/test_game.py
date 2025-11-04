from twgbg.engine.graphs import DiGraph
from twgbg.engine.game import Position, Move


def build_chain(prefix: str):
    graph = DiGraph()
    graph.add_edge(f"{prefix}0", f"{prefix}1")
    graph.add_edge(f"{prefix}1", f"{prefix}2")
    graph.add_node(f"{prefix}2")
    return graph


def test_spoiler_moves_and_responses():
    ga = build_chain("a")
    gb = build_chain("b")
    pos = Position(ga, gb, "a0", "b0")
    moves = pos.spoiler_legal_moves()
    assert any(m.move_type == "forward" for m in moves)
    move = next(m for m in moves if m.graph == "A")
    responses = pos.legal_responses(move)
    assert all(r.graph == "B" for r in responses)


def test_step_updates_nodes():
    ga = build_chain("a")
    gb = build_chain("b")
    pos = Position(ga, gb, "a0", "b0")
    move = Move("A", "forward", "a0", "a1")
    reply = Move("B", "forward", "b0", "b1")
    new_pos = pos.step(move, reply)
    assert new_pos.node_a == "a1"
    assert new_pos.node_b == "b1"
