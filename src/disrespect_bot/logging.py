from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import chess.pgn


class GameLogger:
    def __init__(self, directory: Path):
        self.directory, self.events = directory, []

    def event(self, *, ply: int, fen: str, kind: str, detail: dict | None = None) -> None:
        self.events.append({"ply": ply, "fen": fen, "kind": kind, "detail": detail or {}})

    def save(self, game: chess.pgn.Game) -> tuple[Path, Path]:
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        pgn_path, json_path = self.directory / f"game-{stamp}.pgn", self.directory / f"game-{stamp}.json"
        with pgn_path.open("w", encoding="utf-8") as file:
            print(game, file=file)
        json_path.write_text(json.dumps(self.events, ensure_ascii=False, indent=2), encoding="utf-8")
        return pgn_path, json_path
