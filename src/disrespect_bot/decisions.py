from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import chess

from .config import ClockPressureConfig, DisrespectConfig, EarlySacrificeConfig, MateDelayConfig, SafetyConfig, UnderpromotionConfig, WinningUnderpromotionConfig
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
    _piece_values = {chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}

    def __init__(self, safety: SafetyConfig, underpromotion: UnderpromotionConfig, early_sacrifice: EarlySacrificeConfig | None = None, disrespect: DisrespectConfig | None = None, estimated_bot_rating: int = 2000, winning_underpromotion: WinningUnderpromotionConfig | None = None, mate_delay: MateDelayConfig | None = None, clock_pressure: ClockPressureConfig | None = None):
        self.safety = safety
        self.underpromotion = underpromotion
        self.early_sacrifice = early_sacrifice or EarlySacrificeConfig()
        self.disrespect = disrespect or DisrespectConfig()
        self.estimated_bot_rating = estimated_bot_rating
        self.winning_underpromotion = winning_underpromotion or WinningUnderpromotionConfig()
        self.mate_delay = mate_delay or MateDelayConfig()
        self.clock_pressure = clock_pressure or ClockPressureConfig()

    def choose_move(self, board: chess.Board, analyzer: Analyzer, depth: int, multipv: int, bot_rating: int | None = None, opponent_rating: int | None = None, opponent_clock_ms: int | None = None) -> Decision:
        candidates = analyzer.candidates(board, depth, multipv)
        if not candidates:
            raise RuntimeError("Engine returned no legal candidate")
        best = candidates[0]
        level = self.effective_disrespect_level(bot_rating, opponent_rating, opponent_clock_ms)
        if self.underpromotion.enabled:
            underpromotion = self._choose_underpromotion(board, analyzer, best)
            if underpromotion is not None:
                return Decision(underpromotion.move, "underpromotion", best, underpromotion, "underpromotion")
        pawn_push = self._choose_pawn_first_move(board, analyzer, best)
        if pawn_push is not None:
            return Decision(pawn_push.move, "pawn_first_endgame", best, pawn_push, "pawn_first_endgame")
        delayed_mate = self._choose_mate_delay_pawn_move(board, analyzer, best, level)
        if delayed_mate is not None:
            return Decision(delayed_mate.move, "mate_delay", best, delayed_mate, "mate_delayed_for_pawn_promotion")
        sacrifice = self._choose_early_sacrifice(board, analyzer, best, level, opponent_clock_ms)
        if sacrifice is not None:
            event = "clock_pressure_sacrifice" if self.clock_pressure_bonus(opponent_clock_ms) else "material_sacrifice"
            return Decision(sacrifice.move, "early_sacrifice", best, sacrifice, event)
        return Decision(best.move, "stockfish", best, best)

    def disrespect_level(self, bot_rating: int | None, opponent_rating: int | None) -> int:
        if opponent_rating is None:
            return self.disrespect.base_level
        advantage = max(0, (bot_rating or self.estimated_bot_rating) - opponent_rating)
        return min(self.disrespect.maximum_level, self.disrespect.base_level + advantage // self.disrespect.rating_points_per_level)

    def clock_pressure_bonus(self, opponent_clock_ms: int | None) -> int:
        config = self.clock_pressure
        if not config.enabled or opponent_clock_ms is None:
            return 0
        seconds = opponent_clock_ms / 1000
        if seconds >= config.trigger_seconds:
            return 0
        if seconds <= config.critical_seconds:
            return config.maximum_bonus_level
        span = config.trigger_seconds - config.critical_seconds
        if span <= 0:
            return config.maximum_bonus_level
        return round(config.maximum_bonus_level * (config.trigger_seconds - seconds) / span)

    def effective_disrespect_level(self, bot_rating: int | None, opponent_rating: int | None, opponent_clock_ms: int | None) -> int:
        return min(self.disrespect.maximum_level, self.disrespect_level(bot_rating, opponent_rating) + self.clock_pressure_bonus(opponent_clock_ms))

    def _choose_early_sacrifice(self, board: chess.Board, analyzer: Analyzer, initial_best: Candidate, level: int, opponent_clock_ms: int | None) -> Candidate | None:
        config = self.early_sacrifice
        max_ply = self.clock_pressure.expanded_sacrifice_max_ply if self.clock_pressure_bonus(opponent_clock_ms) else config.max_ply
        if not config.enabled or board.ply() >= max_ply:
            return None
        candidate_count = self._interpolate(config.min_candidates, config.max_candidates, level)
        offered = self._offered_piece_moves(board)[:candidate_count]
        if not offered:
            return None
        best = analyzer.analyse_move(board, initial_best.move, self.safety.confirmation_depth)
        for move in offered:
            candidate = analyzer.analyse_move(board, move, self.safety.confirmation_depth)
            if self._safe_sacrifice(best, candidate, level):
                return candidate
        return None

    def _offered_piece_moves(self, board: chess.Board) -> list[chess.Move]:
        mover = board.turn
        offered: list[tuple[int, chess.Move]] = []
        for move in board.legal_moves:
            piece = board.piece_at(move.from_square)
            if piece is None or piece.piece_type not in self._piece_values:
                continue
            after = board.copy(stack=False)
            after.push(move)
            if after.attackers(not mover, move.to_square):
                offered.append((self._piece_values[piece.piece_type], move))
        return [move for _, move in sorted(offered, key=lambda item: item[0], reverse=True)]

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
            if self._safe_underpromotion(board, best, candidate):
                return candidate
        return None

    def _safe_underpromotion(self, board: chess.Board, best: Candidate, candidate: Candidate) -> bool:
        if candidate.mate_in is not None and candidate.mate_in < 0:
            return False
        if best.mate_in is not None:
            if best.mate_in <= 0:
                return False
            if candidate.mate_in is not None and candidate.mate_in > 0:
                return True
            return self._is_clearly_won_endgame(board, best) and candidate.centipawns >= self.winning_underpromotion.minimum_candidate_evaluation
        if self._is_clearly_won_endgame(board, best):
            return candidate.centipawns >= self.winning_underpromotion.minimum_candidate_evaluation
        floor = max(
            self.safety.minimum_evaluation_centipawns,
            best.centipawns - min(self.safety.max_centipawn_loss, self.underpromotion.max_centipawn_loss),
        )
        return candidate.centipawns >= floor

    def _is_clearly_won_endgame(self, board: chess.Board, best: Candidate) -> bool:
        config = self.winning_underpromotion
        if not config.enabled or best.centipawns < config.minimum_best_evaluation:
            return False
        opponent = not board.turn
        material = sum(
            len(board.pieces(piece, opponent)) * value
            for piece, value in self._piece_values.items()
        ) + len(board.pieces(chess.PAWN, opponent))
        return material <= config.max_opponent_material

    def _choose_pawn_first_move(self, board: chess.Board, analyzer: Analyzer, best: Candidate) -> Candidate | None:
        config = self.winning_underpromotion
        if not config.complete_all_pawn_promotions or not self._is_clearly_won_endgame(board, best):
            return None
        pawns = [
            move for move in board.legal_moves
            if board.piece_at(move.from_square) and board.piece_at(move.from_square).piece_type == chess.PAWN and not move.promotion
        ]
        if not pawns:
            return None
        baseline_threats = self._opponent_pawn_capture_threats(board) if config.prioritize_pawn_safety else 0

        def priority(move: chess.Move) -> tuple[int, int]:
            after = board.copy(stack=False)
            after.push(move)
            threats = self._opponent_pawn_capture_threats(after) if config.prioritize_pawn_safety else 0
            progress = chess.square_rank(move.to_square) if board.turn == chess.WHITE else 7 - chess.square_rank(move.to_square)
            return threats, -progress

        advancing = sorted(
            pawns,
            key=priority,
        )
        for move in advancing:
            after = board.copy(stack=False)
            after.push(move)
            if config.prioritize_pawn_safety and self._opponent_pawn_capture_threats(after) > baseline_threats:
                continue
            candidate = analyzer.analyse_move(board, move, self.safety.confirmation_depth)
            if candidate.mate_in is not None and candidate.mate_in < 0:
                continue
            if candidate.centipawns >= config.minimum_candidate_evaluation:
                return candidate
        return None

    @staticmethod
    def _opponent_pawn_capture_threats(board: chess.Board) -> int:
        """Count legal immediate captures of the side that just moved's pawns."""
        pawn_color = not board.turn
        threats = 0
        for reply in board.legal_moves:
            if not board.is_capture(reply):
                continue
            captured = board.piece_at(reply.to_square)
            if captured and captured.color == pawn_color and captured.piece_type == chess.PAWN:
                threats += 1
        return threats

    def _choose_mate_delay_pawn_move(self, board: chess.Board, analyzer: Analyzer, best: Candidate, level: int) -> Candidate | None:
        config = self.mate_delay
        if not config.enabled or level < config.minimum_disrespect_level or best.mate_in is None or best.mate_in <= 0:
            return None
        pawns = [
            move for move in board.legal_moves
            if board.piece_at(move.from_square) and board.piece_at(move.from_square).piece_type == chess.PAWN and not move.promotion
        ]
        advancing = sorted(
            pawns,
            key=lambda move: chess.square_rank(move.to_square) if board.turn == chess.WHITE else 7 - chess.square_rank(move.to_square),
            reverse=True,
        )[:config.max_pawn_candidates]
        for move in advancing:
            candidate = analyzer.analyse_move(board, move, self.safety.confirmation_depth)
            if candidate.mate_in is not None and candidate.mate_in < 0:
                continue
            if candidate.mate_in is not None and candidate.mate_in > 0:
                return candidate
            if candidate.centipawns >= config.minimum_candidate_evaluation:
                return candidate
        return None

    @staticmethod
    def _interpolate(low: int, high: int, level: int) -> int:
        return low + (high - low) * max(0, min(level, 100)) // 100

    def _safe_sacrifice(self, best: Candidate, candidate: Candidate, level: int) -> bool:
        if candidate.mate_in is not None and candidate.mate_in < 0:
            return False
        if best.mate_in is not None:
            return best.mate_in > 0 and candidate.mate_in is not None and candidate.mate_in > 0
        floor = max(
            self._interpolate(self.early_sacrifice.minimum_evaluation_at_level_0, self.early_sacrifice.minimum_evaluation_at_level_100, level),
            best.centipawns - self._interpolate(self.early_sacrifice.max_centipawn_loss_at_level_0, self.early_sacrifice.max_centipawn_loss_at_level_100, level),
        )
        return candidate.centipawns >= floor
