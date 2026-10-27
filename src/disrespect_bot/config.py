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
class AppConfig:
    engine: EngineConfig
    openings: list[dict]
    log_directory: Path
    estimated_rating: int


def load_config(path: str | Path) -> AppConfig:
    with Path(path).open(encoding="utf-8") as file:
        raw = yaml.safe_load(file) or {}
    engine_raw = raw.get("engine", {})
    engine_path = os.getenv("STOCKFISH_PATH", engine_raw.get("path", ""))
    if not engine_path:
        raise ValueError("Configure engine.path or STOCKFISH_PATH.")
    return AppConfig(
        engine=EngineConfig(engine_path, int(engine_raw.get("analysis_depth", 12)), int(engine_raw.get("multipv", 4))),
        openings=list(raw.get("openings", [])),
        log_directory=Path(raw.get("logging", {}).get("directory", "logs")),
        estimated_rating=int(raw.get("bot", {}).get("estimated_rating", 2000)),
    )
