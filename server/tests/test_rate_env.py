# File: server/tests/test_rate_env.py
"""A34: /classify per-minute limit comes from RATE_CLASSIFY_PER_MIN, default 10."""
import importlib

import pytest
from pydantic import ValidationError

from app import config, ratelimit


def _reload(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("RATE_CLASSIFY_PER_MIN", raising=False)
    else:
        monkeypatch.setenv("RATE_CLASSIFY_PER_MIN", value)
    config.get_settings.cache_clear()
    return importlib.reload(ratelimit)


def test_default_is_ten(monkeypatch):
    rl = _reload(monkeypatch, None)
    assert rl.ip_limiter.limit == 10


def test_env_raises_limit_and_blocks_after_n(monkeypatch):
    rl = _reload(monkeypatch, "60")
    assert rl.ip_limiter.limit == 60
    assert all(rl.ip_limiter.check("1.2.3.4") == 0 for _ in range(60))
    assert rl.ip_limiter.check("1.2.3.4") > 0


def test_bad_values_are_rejected(monkeypatch):
    monkeypatch.setenv("RATE_CLASSIFY_PER_MIN", "0")
    config.get_settings.cache_clear()
    with pytest.raises(ValidationError):
        config.Settings()


def test_restore_default(monkeypatch):
    _reload(monkeypatch, None)
