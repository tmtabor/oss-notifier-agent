"""Pipeline configuration: the repo watch list, labels, and search terms.

This is fork-specific configuration, not a secret credential, but it still
must never be committed — a public template repo shouldn't carry any one
fork's repo list in git history. It's read from the AGENT_PIPELINE_CONFIG
environment variable — in production that's populated from a GitHub Secret
of the same name; locally, set it in .env. See .env.example for the schema
to copy from.
"""

from __future__ import annotations

import yaml
from pydantic import BaseModel, ConfigDict, Field

from agent.config import settings
from agent.logging import get_logger

logger = get_logger(__name__)


class RepoConfig(BaseModel):
    """One watched repository, with optional overrides of the defaults."""

    # extra="forbid": a misindented or misspelled key (e.g. "repositories"
    # nested under "defaults" by accident) should fail loudly at load time,
    # not get silently dropped and leave the pipeline watching zero repos.
    model_config = ConfigDict(extra="forbid")

    repo: str  # "owner/name"
    labels: list[str] | None = None
    search_terms: list[str] | None = None


class PipelineDefaults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    labels: list[str] = Field(default_factory=list)
    search_terms: list[str] = Field(default_factory=list)


class PipelineConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    defaults: PipelineDefaults = Field(default_factory=PipelineDefaults)
    repositories: list[RepoConfig] = Field(default_factory=list)

    def labels_for(self, repo: RepoConfig) -> list[str]:
        return repo.labels if repo.labels is not None else self.defaults.labels

    def search_terms_for(self, repo: RepoConfig) -> list[str]:
        return repo.search_terms if repo.search_terms is not None else self.defaults.search_terms


def load_config() -> PipelineConfig:
    """Load pipeline config from settings.pipeline_config (AGENT_PIPELINE_CONFIG).

    Raises:
        ValueError: The setting is unset or empty.
    """
    raw = settings.pipeline_config
    if not raw:
        raise ValueError(
            "AGENT_PIPELINE_CONFIG is not set. See .env.example for the schema and set it "
            "(in .env for local development, or as a GitHub Secret in production)."
        )

    logger.info("Loading pipeline config")
    data = yaml.safe_load(raw) or {}
    return PipelineConfig.model_validate(data)
