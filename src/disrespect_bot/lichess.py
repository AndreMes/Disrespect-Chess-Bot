from __future__ import annotations

import json
import logging
import os
import time
from typing import Iterator

import chess
import requests

from .config import AppConfig, LichessConfig, load_config
from .decisions import DisrespectEngine
from .engine import StockfishAnalyzer
from .logging import GameLogger
from .openings import OpeningManager

LOG = logging.getLogger(__name__)


def retry_delay(error: requests.RequestException, fallback_seconds: int) -> int:
    """Lichess asks clients to wait a full minute after HTTP 429."""
    if isinstance(error, requests.HTTPError) and error.response is not None:
        if error.response.status_code == 429:
            retry_after = error.response.headers.get("Retry-After")
            try:
                return max(60, int(retry_after)) if retry_after else 60
            except ValueError:
                return 60
    return fallback_seconds


def game_id_from_event(game: dict) -> str:
    """The incoming-event contract names the streamable game identifier gameId."""
    game_id = game.get("gameId")
    if not game_id:
        raise ValueError("gameStart event does not contain gameId")
    return game_id


def is_bot_account(account: dict) -> bool:
    return account.get("title") == "BOT"


class LichessApi:
    """Small wrapper for the official Bot API; no browser automation is used."""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}", "Accept": "application/x-ndjson"})

    def stream(self, endpoint: str) -> Iterator[dict]:
        with self.session.get(f"{self.base_url}{endpoint}", stream=True, timeout=(10, 90)) as response:
            response.raise_for_status()
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    yield json.loads(line)

    def post(self, endpoint: str) -> None:
        response = self.session.post(f"{self.base_url}{endpoint}", timeout=15)
        response.raise_for_status()

    def account(self) -> dict:
        response = self.session.get(f"{self.base_url}/api/account", timeout=15)
        response.raise_for_status()
        return response.json()

    def accept_challenge(self, challenge_id: str) -> None:
        self.post(f"/api/challenge/{challenge_id}/accept")

    def decline_challenge(self, challenge_id: str, reason: str = "generic") -> None:
        self.post(f"/api/challenge/{challenge_id}/decline?reason={reason}")

    def play_move(self, game_id: str, move: chess.Move) -> None:
        self.post(f"/api/bot/game/{game_id}/move/{move.uci()}")


def challenge_is_allowed(challenge: dict, config: LichessConfig, active_games: int) -> bool:
    challenger = challenge.get("challenger", {}).get("name", "").lower()
    variant = challenge.get("variant", {}).get("key")
    speed = challenge.get("speed")
    return (
        config.accept_challenges
        and active_games < config.max_concurrent_games
        and challenger in config.allowed_challengers
        and variant in config.allowed_variants
        and speed in config.allowed_speeds
    )


class LichessBot:
    def __init__(self, config: AppConfig, token: str):
        if not config.lichess.enabled:
            raise ValueError("Set lichess.enabled to true before starting the Lichess client.")
        self.config = config
        self.api = LichessApi(config.lichess.base_url, token)
        self.active_games = 0

    def run(self) -> None:
        account = self.api.account()
        if not is_bot_account(account):
            raise ValueError(
                "The authenticated Lichess account is not a BOT account. "
                "Upgrade a fresh, unused account before running this client."
            )
        LOG.info("Connected as %s", account["username"])
        retry_seconds = 1
        while True:
            try:
                for event in self.api.stream("/api/stream/event"):
                    retry_seconds = 1
                    event_type = event.get("type")
                    if event_type == "challenge":
                        self._handle_challenge(event["challenge"])
                    elif event_type == "gameStart":
                        game_id = game_id_from_event(event["game"])
                        self.active_games += 1
                        try:
                            self._play_game(game_id, account["id"])
                        except requests.HTTPError as error:
                            response = error.response
                            LOG.error(
                                "Unable to stream game %s (HTTP %s): %s",
                                game_id,
                                response.status_code if response is not None else "?",
                                response.text[:300] if response is not None else error,
                            )
                        finally:
                            self.active_games -= 1
            except requests.RequestException as error:
                delay = retry_delay(error, retry_seconds)
                LOG.warning("Lichess stream disconnected (%s); retrying in %ss", error, delay)
                time.sleep(delay)
                retry_seconds = min(retry_seconds * 2, 60)

    def _handle_challenge(self, challenge: dict) -> None:
        challenge_id = challenge["id"]
        if challenge_is_allowed(challenge, self.config.lichess, self.active_games):
            LOG.info("Accepting challenge %s", challenge_id)
            self.api.accept_challenge(challenge_id)
        else:
            LOG.info("Declining challenge %s", challenge_id)
            self.api.decline_challenge(challenge_id)

    def _play_game(self, game_id: str, account_id: str) -> None:
        board = chess.Board()
        logger = GameLogger(self.config.log_directory)
        opening_manager = OpeningManager(self.config.openings)
        selector = DisrespectEngine(self.config.safety, self.config.underpromotion)
        bot_color: chess.Color | None = None
        opening = None
        opening_attempted = False
        opponent_rating: int | None = None
        with StockfishAnalyzer(self.config.engine.path) as engine:
            for update in self.api.stream(f"/api/bot/game/stream/{game_id}"):
                if update["type"] == "gameFull":
                    bot_color = chess.WHITE if update["white"]["id"].lower() == account_id.lower() else chess.BLACK
                    opponent = update["black"] if bot_color == chess.WHITE else update["white"]
                    opponent_rating = opponent.get("rating")
                    state = update["state"]
                elif update["type"] == "gameState":
                    state = update
                else:
                    continue
                board = chess.Board()
                for uci in state.get("moves", "").split():
                    board.push_uci(uci)
                if state.get("status") != "started" or bot_color is None or board.turn != bot_color:
                    if state.get("status") not in {None, "started"}:
                        break
                    continue
                if not opening_attempted:
                    opening = opening_manager.choose(bot_color, opponent_rating, board)
                    opening_attempted = True
                move = opening_manager.next_move(board, opening, bot_color) if opening else None
                if move:
                    source, detail = "opening", {"source": "opening"}
                else:
                    decision = selector.choose_move(board, engine, self.config.engine.analysis_depth, self.config.engine.multipv)
                    move, source = decision.move, decision.source
                    detail = {"source": source, "best_centipawns": decision.best.centipawns, "chosen_centipawns": decision.chosen.centipawns, "best_wdl": decision.best.wdl}
                    if decision.event:
                        detail["event"] = decision.event
                detail["uci"] = move.uci()
                logger.event(ply=board.ply(), fen=board.fen(), kind="move", detail=detail)
                self.api.play_move(game_id, move)
        # Save decision events even if Lichess stores the authoritative PGN.
        logger.directory.mkdir(parents=True, exist_ok=True)
        (logger.directory / f"lichess-{game_id}.json").write_text(json.dumps(logger.events, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run Disrespect Bot through the official Lichess Bot API.")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()
    token = os.getenv("LICHESS_BOT_TOKEN")
    if not token:
        raise ValueError("Set LICHESS_BOT_TOKEN in the environment; never add it to config.yaml.")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    LichessBot(load_config(args.config), token).run()


if __name__ == "__main__":
    main()
