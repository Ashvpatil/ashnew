from twgbg.engine.ai import AlphaBetaAI, MCTSAI, HybridAI
from twgbg.engine.game import Move, Position, RuleConfig, legal_responses
from twgbg.engine.graphs import DiGraph


def sample_graph():
    g = DiGraph()
    g.add_edge("S1", "S2")
    g.add_edge("S2", "S3")
    g.add_edge("S3", "S1")
    return g


def check_ai(ai):
    g = sample_graph()
    pos = Position("S1", "S1")
    move = ai.select_move(g, g, pos, RuleConfig(), [], 0, None)
    assert isinstance(move, Move)
    replies = legal_responses(g, pos.B_curr, move.mtype)
    assert replies


def test_alphabeta_move():
    check_ai(AlphaBetaAI())


def test_mcts_move():
    check_ai(MCTSAI())


def test_hybrid_move():
    check_ai(HybridAI())
