from pathlib import Path

import chess.pgn

from disrespect_bot.reports import render_history_dashboard


def test_history_dashboard_links_saved_game_files(tmp_path: Path):
    game = chess.pgn.Game()
    game.headers["White"] = "DisrespectBot"
    game.headers["Black"] = "zAmazed"
    game.headers["Result"] = "1-0"
    with (tmp_path / "lichess-demo.pgn").open("w", encoding="utf-8") as file:
        print(game, file=file)
    (tmp_path / "lichess-demo.json").write_text("[]", encoding="utf-8")
    (tmp_path / "lichess-demo.report.md").write_text("# Report", encoding="utf-8")

    dashboard = render_history_dashboard(tmp_path)

    page = dashboard.read_text(encoding="utf-8")
    assert "DisrespectBot" in page
    assert "lichess-demo.report.md" in page
