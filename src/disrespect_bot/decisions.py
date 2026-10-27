from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import chess

from .config import SafetyConfig, UnderpromotionConfig
from .engine import Candidate


class Analyzer(Protocol):
    def candidates(self, board: chess.Board, depth: int, multipv: int) -> list[Candidate]: ...
    def analyse_move(self, board: chess.Board, move: chess.Move, depth: int) -> Candidate: ...


@dataclass(frozen=True)
class Decision:
    move: chess.Move
    source: str
    best: Candidate
    chosen: Candidate
    event: str | None = None


class DisrespectEngine:
    """Safety-first selector. New behaviors are evaluated independently here."""

    _promotion_pieces = {
        "knight": chess.KNIGHT,
        "bishop": chess.BISHOP,
        "rook": chess.ROOK,
    }

    def __init__(self, safety: SafetyConfig, underpromotion: UnderpromotionConfig):
        self.safety = safety
        self.underpromotion = underpromotion

    def choose_move(self, board: chess.Board, analyzer: Analyzer, depth: int, multipv: int) -> Decision:
        candidates = analyzer.candidates(board, depth, multipv)
        if not candidates:
            raise RuntimeError("Engine returned no legal candidate")
        best = candidates[0]
        if self.underpromotion.enabled:
            underpromotion = self._choose_underpromotion(board, analyzer, best)
            if underpromotion is not None:
                return Decision(underpromotion.move, "underpromotion", best, underpromotion, "underpromotion")
        return Decision(best.move, "stockfish", best, best)

    def _choose_underpromotion(self, board: chess.Board, analyzer: Analyzer, initial_best: Candidate) -> Candidate | None:
        legal_promotions = {move.promotion: move for move in board.legal_moves if move.promotion}
        if not legal_promotions:
            return None
        # Compare at the same deeper confirmation depth, never just against a shallow score.
        best = analyzer.analyse_move(board, initial_best.move, self.safety.confirmation_depth)
        for name in self.underpromotion.priority:
            piece = self._promotion_pieces.get(name)
            move = legal_promotions.get(piece)
            if move is None:
                continue
            candidate = analyzer.analyse_move(board, move, self.safety.confirmation_depth)
            if self._safe_underpromotion(best, candidate):
                return candidate
        return None

    def _safe_underpromotion(self, best: Candidate, candidate: Candidate) -> bool:
        if candidate.mate_in is not None and candidate.mate_in < 0:
            return False
        if best.mate_in is not None:
            return best.mate_in > 0 and candidate.mate_in is not None and candidate.mate_in > 0
        floor = max(
            self.safety.minimum_evaluation_centipawns,
            best.centipawns - min(self.safety.max_centipawn_loss, self.underpromotion.max_centipawn_loss),
        )
        return candidate.centipawns >= floor
