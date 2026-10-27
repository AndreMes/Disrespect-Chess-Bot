from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any
import chess


@dataclass
class OpeningChoice:
    name: str
    bot_moves: tuple[str, ...] = ()
    next_index: int = 0


class OpeningManager:
    """Escolhe somente árvores cadastradas e jamais devolve um lance ilegal."""

    def __init__(self, openings: list[dict[str, Any]], rng: random.Random | None = None):
        self.openings = openings
        self.rng = rng or random.Random()

    def validate(self) -> list[str]:
        errors: list[str] = []
        for opening in self.openings:
            name = opening.get("name", "<unnamed>")
            if opening.get("color") not in {"white", "black"}:
                errors.append(f"{name}: color must be white or black")
                continue
            if "bot_moves" in opening:
                for uci in opening["bot_moves"]:
                    try:
                        chess.Move.from_uci(uci)
                    except ValueError as error:
                        errors.append(f"{name}: invalid bot move {uci}: {error}")
                continue
            errors.extend(self._validate_nodes(chess.Board(), opening.get("moves", []), name))
        return errors

    def _validate_nodes(self, board: chess.Board, nodes: list[dict], name: str) -> list[str]:
        errors: list[str] = []
        for node in nodes:
            try:
                move = chess.Move.from_uci(node["uci"])
                if move not in board.legal_moves:
                    raise ValueError("illegal in this position")
            except (KeyError, ValueError) as error:
                errors.append(f"{name}: invalid move {node.get('uci', '<missing>')}: {error}")
                continue
            after = board.copy(stack=False)
            after.push(move)
            errors.extend(self._validate_nodes(after, node.get("children", []), name))
        return errors

    def choose(self, color: chess.Color, opponent_rating: int | None, board: chess.Board | None = None) -> OpeningChoice | None:
        color_name = "white" if color == chess.WHITE else "black"
        eligible = [item for item in self.openings if item.get("enabled", True) and item.get("color") == color_name and (item.get("max_opponent_rating") is None or opponent_rating is None or opponent_rating <= int(item["max_opponent_rating"]))]
        if board is not None:
            eligible = [
                item for item in eligible
                if item.get("bot_moves") or self._has_next_bot_move(board, item, color)
            ]
        if not eligible:
            return None
        picked = self.rng.choices(eligible, weights=[item.get("weight", 1) for item in eligible], k=1)[0]
        return OpeningChoice(picked["name"], tuple(picked.get("bot_moves", [])))

    def _has_next_bot_move(self, board: chess.Board, opening: dict, color: chess.Color) -> bool:
        nodes = self._match_tree(chess.Board(), opening.get("moves", []), list(board.move_stack))
        if nodes is None or board.turn != color:
            return False
        for node in nodes:
            try:
                if chess.Move.from_uci(node["uci"]) in board.legal_moves:
                    return True
            except (KeyError, ValueError):
                continue
        return False

    def next_move(self, board: chess.Board, choice: OpeningChoice, color: chess.Color) -> chess.Move | None:
        if choice.bot_moves:
            if choice.next_index >= len(choice.bot_moves) or board.turn != color:
                return None
            try:
                move = chess.Move.from_uci(choice.bot_moves[choice.next_index])
            except ValueError:
                choice.next_index = len(choice.bot_moves)
                return None
            if move not in board.legal_moves:
                choice.next_index = len(choice.bot_moves)
                return None
            choice.next_index += 1
            return move
        for opening in (item for item in self.openings if item.get("name") == choice.name):
            nodes = self._match_tree(chess.Board(), opening.get("moves", []), list(board.move_stack))
            if nodes is not None:
                for node in nodes:
                    move = chess.Move.from_uci(node["uci"])
                    if board.turn == color and move in board.legal_moves:
                        return move
        return None

    def _match_tree(self, board: chess.Board, nodes: list[dict], history: list[chess.Move]) -> list[dict] | None:
        if not history:
            return nodes
        for node in nodes:
            try:
                move = chess.Move.from_uci(node["uci"])
            except (KeyError, ValueError):
                continue
            if move == history[0] and move in board.legal_moves:
                board.push(move)
                return self._match_tree(board, node.get("children", []), history[1:])
        return None
