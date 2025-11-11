from twgbg.engine.game import JumpWindow, Move, Position, RuleConfig, spoiler_legal_moves, step
from twgbg.engine.game import JumpWindow, Move, Position, RuleConfig, spoiler_legal_moves, step
from twgbg.engine.graphs import path_graph


def test_legal_moves_forward():
    g = path_graph(3)
    pos = Position("P0", "P0")
    config = RuleConfig(allow_backward=True, allow_jump=False)
    moves = spoiler_legal_moves(g, g, pos, config, JumpWindow(history=[], limit=(2, 5)), 0)
    assert any(m.mtype == "forward" for m in moves)


def test_step_updates_position():
    g = path_graph(3)
    pos = Position("P0", "P0")
    config = RuleConfig()
    move = Move("A", "forward", "P1")
    new_pos, alive, info = step(
        g,
        g,
        pos,
        move,
        "P1",
        config=config,
        jump_window=JumpWindow(history=[], limit=(2, 5)),
        round_number=0,
    )
    assert new_pos.A_curr == "P1"
    assert alive
