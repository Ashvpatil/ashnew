from twgbg.engine.ai.alphabeta import AlphaBetaEngine
from twgbg.engine.ai.hybrid import HybridEngine, HybridSettings
from twgbg.engine.ai.mcts import MCTSEngine
from twgbg.engine.game import JumpWindow, Position, RuleConfig
from twgbg.engine.graphs import path_graph


def test_alpha_beta_move():
    g = path_graph(4)
    engine = AlphaBetaEngine()
    pos = Position("P0", "P0")
    result = engine.search(g, g, pos, config=RuleConfig(), jump_window=JumpWindow(history=[], limit=(2, 5)), max_depth=2)
    assert result.move is not None


def test_mcts_move():
    g = path_graph(4)
    engine = MCTSEngine()
    pos = Position("P0", "P0")
    move = engine.search(g, g, pos, config=RuleConfig(), jump_window=JumpWindow(history=[], limit=(2, 5)), iterations=20)
    assert move is not None


def test_hybrid_move():
    g = path_graph(4)
    engine = HybridEngine()
    pos = Position("P0", "P0")
    move = engine.choose_move(
        g,
        g,
        pos,
        config=RuleConfig(),
        jump_window=JumpWindow(history=[], limit=(2, 5)),
        settings=HybridSettings(depth=2, mcts_iterations=20),
    )
    assert move is not None
