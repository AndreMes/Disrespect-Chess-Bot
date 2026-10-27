from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
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

    def best_move(self, board: chess.Board, depth: int) -> chess.Move:
        return self.candidates(board, depth, multipv=1)[0].move

    def candidates(self, board: chess.Board, depth: int, multipv: int) -> list[Candidate]:
        info = self.engine.analyse(board, chess.engine.Limit(depth=depth), multipv=multipv)
        return [self._candidate(item, board.turn, board.ply()) for item in info if item.get("pv")]

    def analyse_move(self, board: chess.Board, move: chess.Move, depth: int) -> Candidate:
        """Confirm one candidate after it has been played, from the mover's view."""
        mover = board.turn
        after = board.copy(stack=False)
        after.push(move)
        info = self.engine.analyse(after, chess.engine.Limit(depth=depth))
        return self._candidate(info, mover, after.ply(), move)

    @staticmethod
    def _candidate(info: dict, pov: chess.Color, ply: int, move: chess.Move | None = None) -> Candidate:
        selected_move = move or info["pv"][0]
        score = info["score"].pov(pov)
        mate_in = score.mate()
        centipawns = score.score(mate_score=100_000)
        wdl_score = score.wdl(ply=ply)
        return Candidate(selected_move, centipawns, mate_in, (wdl_score.wins, wdl_score.draws, wdl_score.losses))

    def close(self) -> None:
        self.engine.quit()

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
