from __future__ import annotations

from dataclasses import dataclass

import chess


@dataclass(frozen=True)
class TimeManagementConfig:
    enabled: bool = True
    reserve_seconds: float = 0.20
    minimum_think_seconds: float = 0.03
    maximum_think_seconds: float = 0.80
    clock_fraction: float = 0.012
    increment_fraction: float = 0.50


@dataclass(frozen=True)
class MateClockTauntConfig:
    enabled: bool = True
    minimum_disrespect_level: int = 45
    target_remaining_seconds: float = 1.0
    network_margin_seconds: float = 0.25


def move_time_budget_seconds(clock_ms: int | None, increment_ms: int | None, config: TimeManagementConfig) -> float | None:
    """Return a conservative total engine budget for one Lichess move."""
    if not config.enabled or clock_ms is None:
        return None
    available = max(0.0, clock_ms / 1000 - config.reserve_seconds)
    if available <= 0:
        return 0.0
    increment = max(0, increment_ms or 0) / 1000
    desired = clock_ms / 1000 * config.clock_fraction + increment * config.increment_fraction
    return min(available, config.maximum_think_seconds, max(config.minimum_think_seconds, desired))


def mate_clock_taunt_delay_seconds(
    board: chess.Board,
    move: chess.Move,
    clock_ms: int | None,
    disrespect_level: int,
    config: MateClockTauntConfig,
) -> float:
    """Wait only before a legal checkmating move, preserving a network margin."""
    if not config.enabled or clock_ms is None or disrespect_level < config.minimum_disrespect_level:
        return 0.0
    after = board.copy(stack=False)
    after.push(move)
    if not after.is_checkmate():
        return 0.0
    safe_target = config.target_remaining_seconds + config.network_margin_seconds
    return max(0.0, clock_ms / 1000 - safe_target)
