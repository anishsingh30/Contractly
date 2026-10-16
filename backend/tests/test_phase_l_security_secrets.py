import pytest
from app.config import Settings


def test_production_fails_on_default_secret_key(monkeypatch):
    """Verifies that production environment refuses to boot with the development default SECRET_KEY."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "contractly_dev_secret_key_change_in_production_9f8a3b2c1d0e")

    with pytest.raises(ValueError) as excinfo:
        Settings(_env_file=None)
    assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(excinfo.value)
    assert "production" in str(excinfo.value)


def test_staging_fails_on_default_secret_key(monkeypatch):
    """Verifies that staging environment refuses to boot with the development default SECRET_KEY."""
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("SECRET_KEY", "contractly_dev_secret_key_change_in_production_9f8a3b2c1d0e")

    with pytest.raises(ValueError) as excinfo:
        Settings(_env_file=None)
    assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(excinfo.value)
    assert "staging" in str(excinfo.value)


def test_production_fails_on_short_secret_key(monkeypatch):
    """Verifies that production environment fails when SECRET_KEY is shorter than 32 characters."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "too_short_key_123")

    with pytest.raises(ValueError) as excinfo:
        Settings(_env_file=None)
    assert "at least 32 characters" in str(excinfo.value)


def test_production_fails_on_empty_secret_key(monkeypatch):
    """Verifies that production environment fails when SECRET_KEY is empty."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "")

    with pytest.raises(ValueError) as excinfo:
        Settings(_env_file=None)
    assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(excinfo.value)


def test_production_succeeds_with_strong_secret(monkeypatch):
    """Verifies that production boots cleanly with a strong >= 32 char key, enforces secure cookies and disables debug."""
    # Synthetic 64-char key for test verification only
    synthetic_key = "a" * 64
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", synthetic_key)

    s = Settings(_env_file=None)
    assert s.ENVIRONMENT == "production"
    assert s.DEBUG is False
    assert s.SECURE_COOKIES is True
