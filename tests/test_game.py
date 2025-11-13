from twgbg.engine.graphs import DiGraph
from twgbg.engine.game import (
    MOVE_JUMP,
    Move,
    Position,
    RuleSet,
    legal_responses,
    spoiler_legal_moves,
    step,
)


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
    new_pos, alive, info = step(g, g, pos, move, reply, rules)
    assert new_pos.vertex_a == "1"
    assert new_pos.vertex_b == "1"
    assert alive
    assert not info["spoiler_wins"]


def test_jump_cooldown_blocks_moves():
    g = DiGraph.path(3)
    rules = RuleSet(jump_cooldown=2)
    pos = Position("0", "0", jump_cooldown=1)
    moves = spoiler_legal_moves(g, g, pos, rules)
    assert not any(m.move_type == MOVE_JUMP for m in moves)


def test_round_limit_survival():
    g = DiGraph.path(2)
    rules = RuleSet(round_limit=1)
    pos = Position("0", "0")
    move = Move("A", "forward", "0", "1")
    reply = Move("B", "forward", "0", "1")
    _, alive, info = step(g, g, pos, move, reply, rules)
    assert not alive
    assert info["duplicator_survives"]
