# Contributing

Thanks for your interest in improving OSS Notifier Agent.

## Setup

```bash
uv sync --group dev
```

## Before opening a PR

```bash
uv run ruff check .          # lint
uv run ruff format .         # format
uv run pytest                # unit tests — TestModel, no API key, no cost
```

CI runs exactly these three on every push and pull request; keep them green.

Evals are separate and not run in CI:

```bash
uv run pytest -m eval        # real model calls — needs an API key and costs money
```

Run them locally if your change touches the triage prompt (`agent/prompts/system.txt`), the
output schema (`agent/agents/single.py`), or the judge criteria (`evals/test_llm_judge.py`).
Add synthetic cases to `evals/fixtures/triage_cases.json` to cover new triage behavior.

## Guidelines

- See [CLAUDE.md](CLAUDE.md) for the architecture — particularly the deliberate split between
  the deterministic `agent/pipeline/` and the single LLM call in `agent/agents/single.py`.
- Keep instance-specific data (repo watch lists, credentials) out of commits. It belongs in
  `AGENT_PIPELINE_CONFIG` / GitHub Secrets, never in git.
- Don't add label or search-term pre-filtering to the default flow — most target repos don't
  label issues, which is the whole reason triage is an LLM call.
- Match the surrounding code's style and comment density.

## Reporting security issues

See [SECURITY.md](SECURITY.md) — please don't use public issues for vulnerabilities.
