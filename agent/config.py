from dotenv import load_dotenv
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# pydantic-settings' own env_file loading (below) only populates this Settings
# object — it never writes into os.environ. But the model provider SDKs
# (pydantic_ai.providers.google/anthropic/openai) read their API key env vars
# directly via os.getenv(...), bypassing Settings entirely. Without this,
# ANTHROPIC_API_KEY/OPENAI_API_KEY/GOOGLE_API_KEY set only in .env are
# invisible to those SDKs even though Settings itself validates successfully.
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Validated at startup: if the selected model's provider requires an API
    key and it is missing, Settings() raises immediately with a clear error
    instead of failing cryptically at the first API call.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Agent-specific vars are prefixed (AGENT_MODEL, AGENT_LOG_LEVEL, …) so
        # a generic name like MODEL in the user's shell can't silently change
        # the provider. Fields with an explicit validation_alias are exempt.
        env_prefix="AGENT_",
        # notify.yml sets AGENT_MODEL: ${{ vars.AGENT_MODEL }} unconditionally;
        # when that repo variable doesn't exist, GitHub Actions substitutes an
        # empty string rather than omitting the key, so the env var is present
        # but empty. Without this, pydantic-settings treats that as an explicit
        # value ("") instead of falling back to the field default, and
        # infer_model("") blows up with "Unknown model: ". Treat empty as unset.
        env_ignore_empty=True,
    )

    # Provider API keys — required only for the provider of the selected model.
    # These keep their standard, unprefixed names: the provider SDKs read
    # these exact variables directly, so prefixing them would validate one
    # variable while the model client reads another.
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    # pydantic_ai.providers.google.GoogleProvider reads GOOGLE_API_KEY directly
    # (falling back to the legacy GEMINI_API_KEY name, which we don't rely on).
    google_api_key: str | None = Field(default=None, validation_alias="GOOGLE_API_KEY")

    # Model selection — model-agnostic. Defaults to a small/fast Gemini model:
    # per-issue triage is a cheap, high-volume structured-output classification
    # task, not a general-purpose assistant, so a lightweight default fits.
    model: str = "google:gemini-3.1-flash-lite"

    # Judge model for LLM-as-judge evals. Use a different model from the agent
    # to avoid self-assessment bias, but at least as capable — a weak judge
    # grading a strong agent introduces its own bias. Kept on Anthropic
    # regardless of which provider AGENT_MODEL selects, so grading never
    # depends on the same provider/model family being evaluated.
    judge_model: str = "anthropic:claude-sonnet-5"

    # Logfire — optional, falls back to console if not set. Unprefixed:
    # LOGFIRE_TOKEN is the standard name the Logfire SDK and CLI use.
    logfire_token: str | None = Field(default=None, validation_alias="LOGFIRE_TOKEN")

    # Logging
    log_level: str = "INFO"

    # --- Pipeline-specific settings (GitHub Good-First-Issue Digest agent) ---
    # GITHUB_TOKEN keeps its standard, unprefixed name because it's the exact
    # variable GitHub Actions injects automatically for every workflow run.
    github_token: str | None = Field(default=None, validation_alias="GITHUB_TOKEN")
    postmark_server_token: str | None = Field(
        default=None, validation_alias="POSTMARK_SERVER_TOKEN"
    )
    email_from: str | None = Field(default=None, validation_alias="AGENT_EMAIL_FROM")
    email_to: str | None = Field(default=None, validation_alias="AGENT_EMAIL_TO")
    # Default cron cadence (notify.yml) is daily — this is set a bit above
    # 24h rather than exactly 24h so a run that's delayed or skipped doesn't
    # silently drop issues created in the gap. Not derived from the cron
    # schedule automatically; keep the two in sync by hand if you change one.
    search_window_hours: int = 25
    max_issue_body_chars: int = 4000
    max_issues_per_run: int = 30
    # The repo watch list as a YAML document (see .env.example for the
    # schema). Binds to AGENT_PIPELINE_CONFIG via the env_prefix above like
    # the other
    # pipeline settings. Declaring it here isn't optional bookkeeping: with
    # extra="forbid" (pydantic-settings' default), *any* unset AGENT_-prefixed
    # field would make Settings() reject the env var outright rather than
    # ignore it, crashing the app at import time the moment this is set.
    # Actual YAML/schema validation happens lazily in agent/pipeline/config.py.
    pipeline_config: str | None = None

    @model_validator(mode="after")
    def check_provider_key(self) -> "Settings":
        """Fail fast if the selected model's provider key is missing.

        Only the agent model is validated here — the judge model is used
        only by evals, which require a real key at runtime anyway.
        """
        provider = self.model.split(":", 1)[0]
        if provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError(
                "AGENT_MODEL is an Anthropic model but ANTHROPIC_API_KEY is not set. "
                "Add it to .env or the environment."
            )
        if provider == "openai" and not self.openai_api_key:
            raise ValueError(
                "AGENT_MODEL is an OpenAI model but OPENAI_API_KEY is not set. "
                "Add it to .env or the environment."
            )
        if provider == "google" and not self.google_api_key:
            raise ValueError(
                "AGENT_MODEL is a Google model but GOOGLE_API_KEY is not set. "
                "Add it to .env or the environment."
            )
        # "ollama" (and other local providers) run locally — no API key needed.
        return self


settings = Settings()
