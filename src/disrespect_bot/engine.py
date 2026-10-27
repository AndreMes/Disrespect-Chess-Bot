from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
import chess
import chess.engine


@dataclass(frozen=True)
class Candidate:
    move: chess.Move
    centipawns: int
    mate_in: int | None
    wdl: tuple[int, int, int]


class StockfishAnalyzer:
    def __init__(self, executable: str | Path):
        self.engine = chess.engine.SimpleEngine.popen_uci(str(executable))
        self._move_deadline: float | None = None

    def set_move_time_budget(self, seconds: float | None) -> None:
        self._move_deadline = None if seconds is None else time.monotonic() + max(0, seconds)

    def clear_move_time_budget(self) -> None:
        self._move_deadline = None

    def best_move(self, board: chess.Board, depth: int) -> chess.Move:
        return self.candidates(board, depth, multipv=1)[0].move

    def candidates(self, board: chess.Board, depth: int, multipv: int) -> list[Candidate]:
        info = self.engine.analyse(board, self._limit(depth), multipv=multipv)
        return [self._candidate(item, board.turn, board.ply()) for item in info if item.get("pv")]

    def analyse_move(self, board: chess.Board, move: chess.Move, depth: int) -> Candidate:
        """Confirm one candidate after it has been played, from the mover's view."""
        mover = board.turn
        after = board.copy(stack=False)
        after.push(move)
        info = self.engine.analyse(after, self._limit(depth))
        return self._candidate(info, mover, after.ply(), move)

    @staticmethod
    def _candidate(info: dict, pov: chess.Color, ply: int, move: chess.Move | None = None) -> Candidate:
        selected_move = move or info["pv"][0]
        score = info["score"].pov(pov)
        mate_in = score.mate()
        centipawns = score.score(mate_score=100_000)
        wdl_score = score.wdl(ply=ply)
        return Candidate(selected_move, centipawns, mate_in, (wdl_score.wins, wdl_score.draws, wdl_score.losses))

    def _limit(self, depth: int) -> chess.engine.Limit:
        if self._move_deadline is None:
            return chess.engine.Limit(depth=depth)
        remaining = self._move_deadline - time.monotonic()
        # A very short final probe is preferable to silently overrunning the clock.
        return chess.engine.Limit(time=max(0.001, remaining))

    def close(self) -> None:
        self.engine.quit()

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
