from pathlib import Path

import chess.pgn

from disrespect_bot.logging import GameLogger


def test_post_game_report_summarizes_special_decisions(tmp_path: Path):
    logger = GameLogger(tmp_path)
    logger.event(
        ply=12,
        fen="test",
        kind="move",
        detail={
            "source": "early_sacrifice",
            "event": "clock_pressure_sacrifice",
            "disrespect_level": 100,
            "clock_pressure_bonus": 85,
            "opponent_clock_ms": 4_000,
            "mate_clock_taunt_wait_ms": 7_000,
        },
    )
    game = chess.pgn.Game()
    game.headers["White"] = "DisrespectBot"
    game.headers["Black"] = "Opponent"
    game.headers["Result"] = "1-0"

    _, _, report_path = logger.save(game, stem="sample")

    report = report_path.read_text(encoding="utf-8")
    assert "Maior nível de desrespeito: 100" in report
    assert "clock_pressure_sacrifice" in report
    assert "Pausa antes do mate: 7.00 s" in report
