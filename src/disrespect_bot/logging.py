from __future__ import annotations

from datetime import datetime, timezone
from collections import Counter
import json
from pathlib import Path
import chess.pgn


class GameLogger:
    def __init__(self, directory: Path):
        self.directory, self.events = directory, []

    def event(self, *, ply: int, fen: str, kind: str, detail: dict | None = None) -> None:
        self.events.append({"ply": ply, "fen": fen, "kind": kind, "detail": detail or {}})

    def save(self, game: chess.pgn.Game, stem: str | None = None) -> tuple[Path, Path, Path]:
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = stem or f"game-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        pgn_path = self.directory / f"{stamp}.pgn"
        json_path = self.directory / f"{stamp}.json"
        report_path = self.directory / f"{stamp}.report.md"
        with pgn_path.open("w", encoding="utf-8") as file:
            print(game, file=file)
        json_path.write_text(json.dumps(self.events, ensure_ascii=False, indent=2), encoding="utf-8")
        report_path.write_text(self._report(game), encoding="utf-8")
        return pgn_path, json_path, report_path

    def _report(self, game: chess.pgn.Game) -> str:
        details = [event["detail"] for event in self.events if event["kind"] == "move"]
        sources = Counter(detail.get("source", "unknown") for detail in details)
        events = Counter(detail["event"] for detail in details if detail.get("event"))
        levels = [detail["disrespect_level"] for detail in details if isinstance(detail.get("disrespect_level"), int)]
        bonuses = [detail["clock_pressure_bonus"] for detail in details if isinstance(detail.get("clock_pressure_bonus"), int)]
        opponent_clocks = [detail["opponent_clock_ms"] for detail in details if isinstance(detail.get("opponent_clock_ms"), int)]
        mate_waits = [detail["mate_clock_taunt_wait_ms"] for detail in details if isinstance(detail.get("mate_clock_taunt_wait_ms"), int)]

        lines = [
            "# Relatório pós-partida — Disrespect Bot",
            "",
            f"- Brancas: {game.headers.get('White', '?')}",
            f"- Pretas: {game.headers.get('Black', '?')}",
            f"- Resultado: {game.headers.get('Result', '*')}",
            f"- Lances registrados do bot: {len(details)}",
        ]
        if levels:
            lines.append(f"- Maior nível de desrespeito: {max(levels)}")
        if opponent_clocks:
            lines.append(f"- Menor relógio do adversário visto: {min(opponent_clocks) / 1000:.2f} s")
        if bonuses:
            lines.append(f"- Maior bônus por pressão de relógio: {max(bonuses)}")
        if mate_waits:
            lines.append(f"- Pausa antes do mate: {max(mate_waits) / 1000:.2f} s")

        lines.extend(["", "## Origem dos lances", "", "| Origem | Quantidade |", "| --- | ---: |"])
        lines.extend(f"| {source} | {count} |" for source, count in sorted(sources.items()))
        if events:
            lines.extend(["", "## Eventos especiais", "", "| Evento | Quantidade |", "| --- | ---: |"])
            lines.extend(f"| {event} | {count} |" for event, count in sorted(events.items()))
        return "\n".join(lines) + "\n"
