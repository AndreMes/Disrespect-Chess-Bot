from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any
import chess


@dataclass
class OpeningChoice:
    name: str


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

    def choose(self, color: chess.Color, opponent_rating: int | None) -> OpeningChoice | None:
        color_name = "white" if color == chess.WHITE else "black"
        eligible = [item for item in self.openings if item.get("enabled", True) and item.get("color") == color_name and (item.get("max_opponent_rating") is None or opponent_rating is None or opponent_rating <= int(item["max_opponent_rating"]))]
        if not eligible:
            return None
        picked = self.rng.choices(eligible, weights=[item.get("weight", 1) for item in eligible], k=1)[0]
        return OpeningChoice(picked["name"])

    def next_move(self, board: chess.Board, choice: OpeningChoice, color: chess.Color) -> chess.Move | None:
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
