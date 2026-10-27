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


def test_black_opening_is_selected_after_the_opponents_first_move():
    manager = OpeningManager([
        {"name": "after e4", "color": "black", "moves": [{"uci": "e2e4", "children": [{"uci": "g7g5"}]}]},
        {"name": "after d4", "color": "black", "moves": [{"uci": "d2d4", "children": [{"uci": "b8a6"}]}]},
    ])
    board = chess.Board()
    board.push_uci("d2d4")
    choice = manager.choose(chess.BLACK, None, board)
    assert choice.name == "after d4"
    assert manager.next_move(board, choice, chess.BLACK) == chess.Move.from_uci("b8a6")


def test_bot_only_line_ignores_the_opponents_response():
    manager = OpeningManager([{"name": "return", "color": "white", "bot_moves": ["g1f3", "f3g1"]}])
    board = chess.Board()
    choice = manager.choose(chess.WHITE, None, board)
    assert manager.next_move(board, choice, chess.WHITE) == chess.Move.from_uci("g1f3")
    board.push_uci("g1f3")
    board.push_uci("d7d5")
    assert manager.next_move(board, choice, chess.WHITE) == chess.Move.from_uci("f3g1")


def test_king_walk_line_ignores_the_opponents_response():
    manager = OpeningManager([{"name": "e4 king e2", "color": "white", "bot_moves": ["e2e4", "e1e2"]}])
    board = chess.Board()
    choice = manager.choose(chess.WHITE, None, board)
    assert manager.next_move(board, choice, chess.WHITE) == chess.Move.from_uci("e2e4")
    board.push_uci("e2e4")
    board.push_uci("a7a6")
    assert manager.next_move(board, choice, chess.WHITE) == chess.Move.from_uci("e1e2")
