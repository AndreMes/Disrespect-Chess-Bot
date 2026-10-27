import chess

from disrespect_bot.config import EarlySacrificeConfig, SafetyConfig, UnderpromotionConfig
from disrespect_bot.decisions import DisrespectEngine
from disrespect_bot.engine import Candidate


BOARD = chess.Board("7k/P7/8/8/8/8/8/K7 w - - 0 1")
QUEEN = chess.Move.from_uci("a7a8q")
KNIGHT = chess.Move.from_uci("a7a8n")
BISHOP = chess.Move.from_uci("a7a8b")
ROOK = chess.Move.from_uci("a7a8r")


def candidate(move, score):
    return Candidate(move, score, None, (900, 50, 50))


class FakeAnalyzer:
    def __init__(self, evaluations):
        self.evaluations = evaluations

    def candidates(self, *_):
        return [self.evaluations[QUEEN]]

    def analyse_move(self, _, move, __):
        return self.evaluations[move]


class BestMoveFakeAnalyzer(FakeAnalyzer):
    def __init__(self, evaluations, best_move):
        super().__init__(evaluations)
        self.best_move = best_move

    def candidates(self, *_):
        return [self.evaluations[self.best_move]]


def selector():
    return DisrespectEngine(SafetyConfig(max_centipawn_loss=50, minimum_evaluation_centipawns=0, confirmation_depth=10), UnderpromotionConfig(True, 50, ("knight", "bishop", "rook")))


def test_underpromotion_prefers_knight_when_safe():
    analyzer = FakeAnalyzer({QUEEN: candidate(QUEEN, 100), KNIGHT: candidate(KNIGHT, 60), BISHOP: candidate(BISHOP, 90), ROOK: candidate(ROOK, 95)})
    decision = selector().choose_move(BOARD, analyzer, 8, 3)
    assert decision.move == KNIGHT
    assert decision.source == "underpromotion"


def test_underpromotion_falls_back_from_knight_to_bishop():
    analyzer = FakeAnalyzer({QUEEN: candidate(QUEEN, 100), KNIGHT: candidate(KNIGHT, 40), BISHOP: candidate(BISHOP, 60), ROOK: candidate(ROOK, 90)})
    assert selector().choose_move(BOARD, analyzer, 8, 3).move == BISHOP


def test_underpromotion_uses_queen_when_none_is_safe():
    analyzer = FakeAnalyzer({QUEEN: candidate(QUEEN, 100), KNIGHT: candidate(KNIGHT, 40), BISHOP: candidate(BISHOP, 45), ROOK: candidate(ROOK, 49)})
    decision = selector().choose_move(BOARD, analyzer, 8, 3)
    assert decision.move == QUEEN
    assert decision.source == "stockfish"


def test_early_sacrifice_offers_a_piece_when_the_position_stays_playable():
    board = chess.Board("4k3/8/4p3/8/2B5/8/8/4K3 w - - 0 1")
    best_move = chess.Move.from_uci("c4b5")
    sacrifice = chess.Move.from_uci("c4d5")  # The e6-pawn can capture this bishop.
    analyzer = BestMoveFakeAnalyzer({best_move: candidate(best_move, 100), sacrifice: candidate(sacrifice, -100)}, best_move)
    engine = DisrespectEngine(
        SafetyConfig(confirmation_depth=10),
        UnderpromotionConfig(False),
        EarlySacrificeConfig(True, 14, 8, 350, -200),
    )
    decision = engine.choose_move(board, analyzer, 8, 3)
    assert decision.move == sacrifice
    assert decision.event == "material_sacrifice"
