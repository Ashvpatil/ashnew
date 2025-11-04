from twgbg.engine.ai.alphabeta import AlphaBetaSpoiler, SearchConfig
from twgbg.engine.ai.mcts import MCTSSpoiler, MCTSConfig
from twgbg.engine.game import Position, RuleSet
from twgbg.engine.graphs import DiGraph


def make_graphs():
    graph_a = DiGraph.path(3)
    graph_b = DiGraph.path(3)
    return graph_a, graph_b


def test_alphabeta_smoke():
    graph_a, graph_b = make_graphs()
    spoiler = AlphaBetaSpoiler(
        graph_a,
        graph_b,
        RuleSet(),
        config=SearchConfig(depth=2, iterative_deepening=False, time_budget_ms=500),
    )
    result = spoiler.search(Position("0", "0"))
    assert result.best_move is not None


def test_mcts_smoke():
    graph_a, graph_b = make_graphs()
    spoiler = MCTSSpoiler(
        graph_a,
        graph_b,
        RuleSet(),
        config=MCTSConfig(rollouts=30, playout_depth=3, seed=1),
    )
    result = spoiler.run(Position("0", "0"))
    assert result.best_move is not None
