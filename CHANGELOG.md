# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-08-28

Initial public release.

### Added

- Scheduled GitHub Actions pipeline that searches a configured watch list of repositories for
  newly opened, unassigned issues and emails a digest of the ones an LLM triages as
  approachable for a first-time contributor.
- Deterministic ingestion (`agent/pipeline/`) — GitHub Search API client, YAML watch-list
  config via `AGENT_PIPELINE_CONFIG`, Postmark digest delivery — with the LLM used only for
  the per-issue "good first issue?" judgment (`agent/agents/single.py`).
- Model-agnostic configuration (`AGENT_MODEL`, any Pydantic AI model string, `ollama:` for
  local models), validated at import time.
- `--dry-run` mode that runs search and triage for real but prints the digest instead of
  emailing it.
- Unit tests against `TestModel` and mocked HTTP (no API key, no cost) and evals
  (pass/fail + LLM-as-judge) against real models.
- Logfire instrumentation with automatic console fallback.

[0.1.0]: https://github.com/tmtabor/oss-notifier-agent/releases/tag/v0.1.0
