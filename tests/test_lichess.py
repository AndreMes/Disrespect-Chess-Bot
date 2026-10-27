import requests

from disrespect_bot.config import LichessConfig
from disrespect_bot.lichess import challenge_is_allowed, game_id_from_event, is_bot_account, retry_delay


CONFIG = LichessConfig(enabled=True, accept_challenges=True, allowed_challengers=("andre",), allowed_variants=("standard",), allowed_speeds=("rapid",), max_concurrent_games=1)


def challenge(name="Andre", variant="standard", speed="rapid"):
    return {"challenger": {"name": name}, "variant": {"key": variant}, "speed": speed}


def test_accepts_only_authorized_standard_challenge():
    assert challenge_is_allowed(challenge(), CONFIG, active_games=0)
    assert not challenge_is_allowed(challenge(name="other"), CONFIG, active_games=0)
    assert not challenge_is_allowed(challenge(variant="chess960"), CONFIG, active_games=0)
    assert not challenge_is_allowed(challenge(speed="correspondence"), CONFIG, active_games=0)
    assert not challenge_is_allowed(challenge(), CONFIG, active_games=1)


def test_429_waits_at_least_one_minute():
    response = requests.Response()
    response.status_code = 429
    error = requests.HTTPError(response=response)
    assert retry_delay(error, 1) == 60


def test_uses_game_id_from_start_event():
    assert game_id_from_event({"id": "not-the-game-id", "gameId": "actual123"}) == "actual123"


def test_requires_bot_title_on_account():
    assert is_bot_account({"title": "BOT"})
    assert not is_bot_account({"title": None})
