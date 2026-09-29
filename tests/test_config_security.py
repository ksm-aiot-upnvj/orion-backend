"""Regression tests for fail-closed production configuration."""

import pytest
from pydantic import ValidationError

from config.config import DEV_DEFAULT_JWT_SECRET, Settings, validate_production_security

REQUIRED = {
    "SUPERADMIN_NIM": "2099999999",
    "SUPERADMIN_NAME": "x",
    "SUPERADMIN_EMAIL": "x@example.com",
    "SUPERADMIN_PW": "x",
}


def _settings(monkeypatch, **env) -> Settings:
    for key in ("ENVIRONMENT", "JWT_SECRET", "DEBUG", "JWT_ALGORITHM"):
        monkeypatch.delenv(key, raising=False)
    for key, value in {**REQUIRED, **env}.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)


def test_debug_is_off_by_default(monkeypatch):
    assert _settings(monkeypatch).DEBUG is False


def test_production_refuses_default_or_short_jwt_secret(monkeypatch):
    with pytest.raises(RuntimeError):
        validate_production_security(_settings(monkeypatch, ENVIRONMENT="production", JWT_SECRET=DEV_DEFAULT_JWT_SECRET))
    with pytest.raises(RuntimeError):
        validate_production_security(_settings(monkeypatch, ENVIRONMENT="production", JWT_SECRET="short"))


def test_production_forces_debug_off(monkeypatch):
    cfg = _settings(monkeypatch, ENVIRONMENT="production", JWT_SECRET="a" * 64, DEBUG="true")
    validate_production_security(cfg)
    assert cfg.DEBUG is False


def test_development_keeps_defaults_usable(monkeypatch):
    validate_production_security(_settings(monkeypatch, ENVIRONMENT="development"))


@pytest.mark.parametrize("alg", ["none", "None", "RS256", ""])
def test_unsupported_jwt_algorithms_rejected(monkeypatch, alg):
    with pytest.raises(ValidationError):
        _settings(monkeypatch, JWT_ALGORITHM=alg)
