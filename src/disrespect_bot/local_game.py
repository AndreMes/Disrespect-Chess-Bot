from __future__ import annotations

import argparse
import chess
import chess.pgn
from .config import load_config
from .engine import StockfishAnalyzer
from .logging import GameLogger
from .openings import OpeningManager


def main() -> None:
    parser = argparse.ArgumentParser(description="Partida local para validar o bot.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--white", choices=["bot", "engine"], default="bot")
    parser.add_argument("--depth", type=int, default=None)
    parser.add_argument("--opponent-rating", type=int, default=None)
    args = parser.parse_args()
    config, board, game = load_config(args.config), chess.Board(), chess.pgn.Game()
    depth, bot_color = args.depth or config.engine.analysis_depth, chess.WHITE if args.white == "bot" else chess.BLACK
    manager = OpeningManager(config.openings)
    if errors := manager.validate():
        raise ValueError("Invalid opening configuration:\n- " + "\n- ".join(errors))
    choice, node, logger = manager.choose(bot_color, args.opponent_rating), game, GameLogger(config.log_directory)
    with StockfishAnalyzer(config.engine.path) as engine:
        while not board.is_game_over(claim_draw=True):
            move, source = (manager.next_move(board, choice, bot_color), "opening") if board.turn == bot_color and choice else (None, "stockfish")
            if move is None:
                move, source = engine.best_move(board, depth), "stockfish"
            logger.event(ply=board.ply(), fen=board.fen(), kind="move", detail={"uci": move.uci(), "source": source})
            board.push(move)
            node = node.add_variation(move)
    outcome = board.outcome(claim_draw=True)
    game.headers["Result"] = outcome.result() if outcome else "*"
    print(*logger.save(game), sep="\n")


if __name__ == "__main__":
    main()
