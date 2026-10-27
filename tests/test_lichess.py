from disrespect_bot.config import LichessConfig
from disrespect_bot.lichess import challenge_is_allowed


CONFIG = LichessConfig(enabled=True, accept_challenges=True, allowed_challengers=("andre",), allowed_variants=("standard",), allowed_speeds=("rapid",), max_concurrent_games=1)


def challenge(name="Andre", variant="standard", speed="rapid"):
    return {"challenger": {"name": name}, "variant": {"key": variant}, "speed": speed}


def test_accepts_only_authorized_standard_challenge():
    assert challenge_is_allowed(challenge(), CONFIG, active_games=0)
    assert not challenge_is_allowed(challenge(name="other"), CONFIG, active_games=0)
    assert not challenge_is_allowed(challenge(variant="chess960"), CONFIG, active_games=0)
    assert not challenge_is_allowed(challenge(speed="correspondence"), CONFIG, active_games=0)
    assert not challenge_is_allowed(challenge(), CONFIG, active_games=1)
