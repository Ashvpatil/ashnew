from twgbg.engine.graphs import DiGraph
from twgbg.engine.game import Move, Position, RuleSet, legal_responses, spoiler_legal_moves, step


def test_legal_moves_and_responses():
    g = DiGraph.path(3)
    rules = RuleSet(allow_jump=False)
    pos = Position("0", "0")
    moves = spoiler_legal_moves(g, g, pos, rules)
    assert any(m.move_type == "forward" for m in moves)
    move = moves[0]
    responses = legal_responses(g, g, pos, move, rules)
    assert responses


def test_step_changes_position():
    g = DiGraph.path(3)
    rules = RuleSet()
    pos = Position("0", "0")
    move = Move("A", "forward", "0", "1")
    reply = Move("B", "forward", "0", "1")
    new_pos = step(g, g, pos, move, reply)
    assert new_pos.vertex_a == "1"
    assert new_pos.vertex_b == "1"
