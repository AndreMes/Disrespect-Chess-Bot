import chess

from disrespect_bot.time_control import (
    MateClockTauntConfig,
    TimeManagementConfig,
    mate_clock_taunt_delay_seconds,
    move_time_budget_seconds,
)


CONFIG = TimeManagementConfig(
    reserve_seconds=0.20,
    minimum_think_seconds=0.03,
    maximum_think_seconds=0.80,
    clock_fraction=0.012,
    increment_fraction=0.50,
)


def test_bullet_budget_is_capped_and_keeps_clock_reserve():
    assert move_time_budget_seconds(60_000, 0, CONFIG) == 0.72
    assert move_time_budget_seconds(5_000, 0, CONFIG) == 0.06
    assert move_time_budget_seconds(100, 0, CONFIG) == 0.0


def test_increment_contributes_without_exceeding_cap():
    assert move_time_budget_seconds(10_000, 2_000, CONFIG) == 0.8


def test_disabled_time_management_leaves_depth_based_analysis():
    assert move_time_budget_seconds(10_000, 0, TimeManagementConfig(enabled=False)) is None


def test_clock_taunt_waits_only_for_an_actual_checkmate():
    board = chess.Board("7k/6Q1/6K1/8/8/8/8/8 w - - 0 1")
    mate = chess.Move.from_uci("g7h7")
    config = MateClockTauntConfig(minimum_disrespect_level=45, target_remaining_seconds=1, network_margin_seconds=0.25)

    assert mate_clock_taunt_delay_seconds(board, mate, 10_000, 65, config) == 8.75
    assert mate_clock_taunt_delay_seconds(board, mate, 10_000, 20, config) == 0.0
