from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import yaml


@dataclass(frozen=True)
class EngineConfig:
    path: str
    analysis_depth: int = 12
    multipv: int = 4


@dataclass(frozen=True)
class SafetyConfig:
    max_centipawn_loss: int = 80
    minimum_evaluation_centipawns: int = -30
    confirmation_depth: int = 16


@dataclass(frozen=True)
class UnderpromotionConfig:
    enabled: bool = True
    max_centipawn_loss: int = 50
    priority: tuple[str, ...] = ("knight", "bishop", "rook")


@dataclass(frozen=True)
class AppConfig:
    engine: EngineConfig
    safety: SafetyConfig
    underpromotion: UnderpromotionConfig
    openings: list[dict]
    log_directory: Path
    estimated_rating: int


def load_config(path: str | Path) -> AppConfig:
    with Path(path).open(encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}
    engine_raw = raw.get("engine", {})
    safety_raw = raw.get("safety", {})
    underpromotion_raw = raw.get("behaviors", {}).get("underpromotion", {})
    engine_path = os.getenv("STOCKFISH_PATH", engine_raw.get("path", ""))
    if not engine_path:
        raise ValueError("Configure engine.path or STOCKFISH_PATH.")
    return AppConfig(
        engine=EngineConfig(engine_path, int(engine_raw.get("analysis_depth", 12)), int(engine_raw.get("multipv", 4))),
        safety=SafetyConfig(
            max_centipawn_loss=int(safety_raw.get("max_centipawn_loss", 80)),
            minimum_evaluation_centipawns=int(safety_raw.get("minimum_evaluation_centipawns", -30)),
            confirmation_depth=int(safety_raw.get("confirmation_depth", 16)),
        ),
        underpromotion=UnderpromotionConfig(
            enabled=bool(underpromotion_raw.get("enabled", True)),
            max_centipawn_loss=int(underpromotion_raw.get("max_centipawn_loss", 50)),
            priority=tuple(underpromotion_raw.get("priority", ["knight", "bishop", "rook"])),
        ),
        openings=list(raw.get("openings", [])),
        log_directory=Path(raw.get("logging", {}).get("directory", "logs")),
        estimated_rating=int(raw.get("bot", {}).get("estimated_rating", 2000)),
    )
