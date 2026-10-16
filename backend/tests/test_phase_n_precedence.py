import os
import pytest
from app.config import Settings, BACKEND_ENV_PATH


def test_process_environ_precedence_over_disk_env(monkeypatch, tmp_path):
    """
    Verifies that real process environment variables (os.environ) maintain
    strict precedence over any values in the on-disk .env file.
    """
    # Simulate a process-level environment variable (e.g., Kubernetes secret injection)
    strong_secret = "process_injected_strong_secret_key_1234567890_prod"
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", strong_secret)
    monkeypatch.setenv("GEMINI_MODEL", "process-override-model")

    s = Settings()
    # The setting MUST reflect os.environ, not any disk fallback
    assert s.SECRET_KEY == strong_secret
    assert s.GEMINI_MODEL == "process-override-model"
    assert s.ENVIRONMENT == "production"
    assert s.DEBUG is False
    assert s.SECURE_COOKIES is True


def test_disk_env_used_as_fallback_when_absent_from_process_environ(monkeypatch):
    """
    Verifies that when a variable is not set in os.environ,
    the .env file on disk is safely used as a fallback for local developer ergonomics.
    """
    # Ensure GEMINI_MODEL is absent from os.environ
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    s = Settings()
    # In backend/.env, GEMINI_MODEL is 'gemini-flash-lite-latest'
    if os.path.exists(BACKEND_ENV_PATH):
        with open(BACKEND_ENV_PATH, "r", encoding="utf-8") as f:
            content = f.read()
            if "GEMINI_MODEL=" in content:
                assert s.GEMINI_MODEL == "gemini-flash-lite-latest"


def test_production_fails_if_process_environ_is_weak(monkeypatch):
    """
    Verifies that even if a strong key were in .env on disk,
    if process os.environ defines an insecure default key in production, startup fails.
    """
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "contractly_dev_secret_key_change_in_production_9f8a3b2c1d0e")

    with pytest.raises(ValueError) as exc:
        Settings()
    assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(exc.value)
