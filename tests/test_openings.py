import chess
from disrespect_bot.openings import OpeningManager


def test_valid_branch_returns_configured_continuation():
    openings = [{"name": "Bird", "color": "white", "enabled": True, "weight": 1, "moves": [{"uci": "f2f4", "children": [{"uci": "d7d5", "children": [{"uci": "g1f3"}]}]}]}]
    manager, board = OpeningManager(openings), chess.Board()
    assert manager.validate() == []
    choice = manager.choose(chess.WHITE, 1500)
    assert manager.next_move(board, choice, chess.WHITE) == chess.Move.from_uci("f2f4")
    board.push_uci("f2f4")
    board.push_uci("d7d5")
    assert manager.next_move(board, choice, chess.WHITE) == chess.Move.from_uci("g1f3")


def test_deviation_abandons_opening():
    manager = OpeningManager([{"name": "Bird", "color": "white", "moves": [{"uci": "f2f4", "children": [{"uci": "d7d5"}]}]}])
    board, choice = chess.Board(), manager.choose(chess.WHITE, None)
    board.push_uci("f2f4")
    board.push_uci("e7e5")
    assert manager.next_move(board, choice, chess.WHITE) is None


def test_illegal_opening_is_reported():
    assert OpeningManager([{"name": "bad", "color": "white", "moves": [{"uci": "e2e5"}]}]).validate()
