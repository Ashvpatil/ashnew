from twgbg.engine.graphs import DiGraph
from twgbg.engine.game import Position
from twgbg.ai.alphabeta import AlphaBetaSpoiler, SearchConfig
from twgbg.ai.mcts import MCTSSpoiler, MCTSConfig


def simple_graph(prefix: str) -> DiGraph:
    graph = DiGraph()
    graph.add_edge(f"{prefix}0", f"{prefix}1")
    graph.add_edge(f"{prefix}1", f"{prefix}2")
    graph.add_node(f"{prefix}2")
    return graph


def test_alphabeta_returns_move():
    g1 = simple_graph("a")
    g2 = simple_graph("b")
    pos = Position(g1, g2, "a0", "b0")
    ai = AlphaBetaSpoiler(SearchConfig(max_depth=2, time_budget=0.2))
    info = ai.choose_move(pos)
    assert info.best_move is not None


def test_mcts_returns_move_and_heat():
    g1 = simple_graph("a")
    g2 = simple_graph("b")
    pos = Position(g1, g2, "a0", "b0")
    ai = MCTSSpoiler(MCTSConfig(iterations=50, time_budget=0.2, rollout_depth=10))
    move, heat = ai.choose_move(pos)
    assert move is not None
    assert isinstance(heat, dict)
