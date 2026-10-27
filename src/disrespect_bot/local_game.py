from __future__ import annotations

import argparse
import chess
import chess.pgn
from .config import load_config
from .decisions import DisrespectEngine
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
    choice, opening_attempted, node, logger = None, False, game, GameLogger(config.log_directory)
    selector = DisrespectEngine(config.safety, config.underpromotion, config.early_sacrifice, config.disrespect, config.estimated_rating, config.winning_underpromotion)
    with StockfishAnalyzer(config.engine.path) as engine:
        while not board.is_game_over(claim_draw=True):
            if board.turn == bot_color and not opening_attempted:
                choice = manager.choose(bot_color, args.opponent_rating, board)
                opening_attempted = True
            move, source = (manager.next_move(board, choice, bot_color), "opening") if board.turn == bot_color and choice else (None, "stockfish")
            detail = {"source": source}
            if move is None:
                if board.turn == bot_color:
                    decision = selector.choose_move(board, engine, depth, config.engine.multipv, config.estimated_rating, args.opponent_rating)
                    move, source = decision.move, decision.source
                    detail = {
                        "source": source,
                        "best_centipawns": decision.best.centipawns,
                        "chosen_centipawns": decision.chosen.centipawns,
                        "best_wdl": decision.best.wdl,
                    }
                    if decision.event:
                        detail["event"] = decision.event
                else:
                    move, source = engine.best_move(board, depth), "stockfish"
                    detail = {"source": source}
            detail["uci"] = move.uci()
            logger.event(ply=board.ply(), fen=board.fen(), kind="move", detail=detail)
            board.push(move)
            node = node.add_variation(move)
    outcome = board.outcome(claim_draw=True)
    game.headers["Result"] = outcome.result() if outcome else "*"
    print(*logger.save(game), sep="\n")


if __name__ == "__main__":
    main()
