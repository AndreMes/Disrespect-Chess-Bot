from __future__ import annotations

from pathlib import Path
import chess
import chess.engine


class StockfishAnalyzer:
    def __init__(self, executable: str | Path):
        self.engine = chess.engine.SimpleEngine.popen_uci(str(executable))

    def best_move(self, board: chess.Board, depth: int) -> chess.Move:
        result = self.engine.play(board, chess.engine.Limit(depth=depth))
        if result.move is None:
            raise RuntimeError("Stockfish returned no move")
        return result.move

    def close(self) -> None:
        self.engine.quit()

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
