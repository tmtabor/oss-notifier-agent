"""Unit tests for agent.pipeline.config — no network, no API keys."""

import pytest
from pydantic import ValidationError

from agent.config import settings
from agent.pipeline.config import PipelineConfig, RepoConfig, load_config

VALID_YAML = """
defaults:
  labels: ["good first issue"]
  search_terms: ["typo"]
repositories:
  - repo: "octocat/example-repo"
  - repo: "octocat/another-repo"
    labels: ["easy"]
    search_terms: ["css"]
"""


def test_load_config_from_settings(monkeypatch):
    monkeypatch.setattr(settings, "pipeline_config", VALID_YAML)
    config = load_config()

    assert config.defaults.labels == ["good first issue"]
    assert [r.repo for r in config.repositories] == ["octocat/example-repo", "octocat/another-repo"]


def test_load_config_raises_when_unset(monkeypatch):
    monkeypatch.setattr(settings, "pipeline_config", None)

    with pytest.raises(ValueError, match="AGENT_PIPELINE_CONFIG"):
        load_config()


def test_repo_override_falls_back_to_defaults(monkeypatch):
    monkeypatch.setattr(settings, "pipeline_config", VALID_YAML)
    config = load_config()

    no_override, with_override = config.repositories
    assert config.labels_for(no_override) == ["good first issue"]
    assert config.search_terms_for(no_override) == ["typo"]
    assert config.labels_for(with_override) == ["easy"]
    assert config.search_terms_for(with_override) == ["css"]


def test_repo_config_requires_repo_field():
    with pytest.raises(ValidationError):
        RepoConfig.model_validate({})


def test_misindented_repositories_under_defaults_raises_not_silently_drops():
    """Regression test: repositories nested under defaults by a YAML indentation
    mistake must fail loudly, not silently produce an empty repo list."""
    with pytest.raises(ValidationError, match="extra_forbidden|Extra inputs"):
        PipelineConfig.model_validate({"defaults": {"repositories": [{"repo": "a/b"}]}})
