from twgbg.engine.game import Move, Position, RuleConfig, legal_responses, spoiler_legal_moves, step
from twgbg.engine.graphs import DiGraph


def tiny_graph():
    g = DiGraph()
    g.add_edge("A1", "A2")
    g.add_edge("A2", "A1")
    return g


def test_legal_moves_forward_only():
    g = tiny_graph()
    moves = spoiler_legal_moves(g, "A1", allow_backward=False, allow_jump=False)
    assert len(moves) == 1
    assert moves[0].dest == "A2"


def test_step_invalid_reply():
    g = tiny_graph()
    pos = Position("A1", "A1")
    move = Move("A", "forward", "A2")
    new_pos, alive, info, reply = step(g, g, pos, move, "A2", config=RuleConfig(), history=[], round_no=0)
    assert alive is True
    assert new_pos.A_curr == "A2"


def test_no_reply_loss():
    g = tiny_graph()
    g2 = DiGraph()
    g2.add_vertex("B1")
    pos = Position("A1", "B1")
    move = Move("A", "forward", "A2")
    new_pos, alive, info, reply = step(g, g2, pos, move, None, config=RuleConfig(), history=[], round_no=0)
    assert alive is False
    assert "Duplicator" in info
