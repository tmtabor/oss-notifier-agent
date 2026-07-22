"""Unit tests for agent.config.Settings — no network, no real API calls."""

from agent.config import Settings


def test_empty_agent_model_env_var_falls_back_to_default(monkeypatch):
    """Regression test: notify.yml sets AGENT_MODEL: ${{ vars.AGENT_MODEL }}
    unconditionally. When that repo variable doesn't exist, GitHub Actions
    substitutes an empty string rather than omitting the key, so the env var
    is present but empty at runtime. Settings must treat that as unset and
    fall back to the code default, not pass "" to infer_model()."""
    monkeypatch.setenv("AGENT_MODEL", "")

    settings = Settings(_env_file=None)

    assert settings.model == "google:gemini-3.1-flash-lite"


def test_nonempty_agent_model_env_var_still_overrides(monkeypatch):
    monkeypatch.setenv("AGENT_MODEL", "anthropic:claude-opus-4-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "unit-test-dummy-key")

    settings = Settings(_env_file=None)

    assert settings.model == "anthropic:claude-opus-4-8"
