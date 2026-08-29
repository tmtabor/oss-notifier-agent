# CLAUDE.md

**OSS Notifier Agent** scans a configured list of GitHub repositories on a schedule, uses an
LLM to triage newly-opened, unassigned issues for whether they're approachable for a
first-time contributor, and emails a digest of the ones that qualify. It runs entirely on
GitHub Actions — there's no server. The code is the source of truth; this file only covers
what isn't obvious from reading it.

## Commands

```bash
uv sync --group dev            # install deps
uv run pytest                  # unit tests only (TestModel, no API key needed)
uv run pytest -m eval          # all evals — pass/fail AND LLM-judge (needs a real API key, costs money)
uv run ruff check .            # lint
uv run ruff format .           # format

uv run python -m agent.pipeline.run             # run the full pipeline once (searches, triages, emails)
uv run python -m agent.pipeline.run --dry-run   # same, but print the digest instead of emailing
```

There is no separate `llm_judge` marker. Everything in `evals/` carries only
`@pytest.mark.eval`, so `-m eval` runs it all in one shot — there's no cheaper eval-only
subset to reach for.

`asyncio_mode = "auto"` is set in `pyproject.toml`, so async tests need no
`@pytest.mark.asyncio` decorator — don't add them back.

## Architecture: pipeline vs. agent

```
GitHub Search API → truncate/filter → [triage agent, one call per issue] → digest builder → Postmark
```

- **`agent/pipeline/`** is deterministic Python — fetching (`github_client.py`), config
  loading (`config.py`), digest email (`email.py`), and the `run.py` entrypoint. No LLM. It's
  fully unit-testable against mocked HTTP.
- **`agent/agents/single.py`** is the only place an LLM is involved: one structured-output
  call per candidate issue, answering "is this a good first issue?" No tools, no agentic loop
  — and by design it stays that way. `agent/prompts/system.txt` holds the triage criteria.
- `agent/pipeline/run.py` orchestrates: `collect_issues()` → `triage_issues()` →
  `print_digest()` or `PostmarkClient.send_digest()`.

## Making changes

- **Triage criteria** live in `agent/prompts/system.txt`, loaded via `load_prompt("system")`
  in `agent/prompts/templates.py`. `render_issue_prompt()` in the same file formats an `Issue`
  into the user prompt.
- **Output schema** is `AgentOutput` in `agent/agents/single.py` (`is_good_first_issue`,
  `reasoning`, `summary`). The evals in `evals/` read `is_good_first_issue` as the canonical
  verdict field — rename consistently if you change it.
- **Eval cases**: add to `evals/fixtures/triage_cases.json` — the dataset eval in
  `evals/test_pass_fail.py` picks them up automatically. Adapt judge criteria in
  `evals/test_llm_judge.py`.
- Tests and evals import the canonical names — `run_agent`, `AgentOutput`, `AgentDeps`,
  `agent` — from `agent/agents/__init__.py`, never from `agent.agents.single` directly.

## Non-obvious details

- **`agent/config.py` validates at import time, not at call time.** `Settings` has a
  `model_validator` that raises immediately if the provider implied by `AGENT_MODEL`
  (`anthropic:`/`openai:`/`google:` prefix) has no matching API key set. `ollama:` models are
  exempt — no key required. Agent-specific env vars carry an `AGENT_` prefix; API keys and
  `LOGFIRE_TOKEN` deliberately don't, because the provider SDKs read those standard names
  directly. So `import agent.config` (or anything importing it transitively) can fail before
  any code runs — which is the point, but it's also why every module under `agent/` needs
  *some* key present at import time, even for paths that never call the model. `AGENT_MODEL`
  is also `env_ignore_empty` — GitHub Actions substitutes `""` for an undefined repo
  variable, and empty must fall back to the default, not blow up `infer_model("")`.

- **The default model is small on purpose.** `settings.model` defaults to
  `google:gemini-3.1-flash-lite` — per-issue triage is cheap, high-volume classification, not
  a general assistant. `settings.judge_model` (`anthropic:claude-sonnet-5`, used only by the
  LLM-judge evals) is kept on a different provider to avoid self-assessment bias, and should
  stay *at least as capable* as the agent, never weaker.

- **Unit tests never need real credentials — two layers guarantee it.**
  `tests/conftest.py` calls `os.environ.setdefault(...)` for all three provider keys *before*
  importing anything from `agent/` (satisfying the import-time validator), and an autouse
  fixture overrides every `Agent` under `agent.agents` with `TestModel`. Don't remove either
  — together they're why `uv run pytest` works with zero setup and zero spend.
  `evals/conftest.py` deliberately does **neither**: a missing key there should fail loudly,
  since evals make real API calls anyway.

- **Every run is bounded by `USAGE_LIMITS`** (`agent/agents/single.py`). Exceeding
  `request_limit` or `total_tokens_limit` raises `UsageLimitExceeded` rather than silently
  looping. This is a single structured-output call per issue, so the limits are tuned low.
  `AGENT_MAX_ISSUES_PER_RUN` (default 30) is the separate guardrail for the whole batch.

- **`AGENT_PIPELINE_CONFIG` is instance-specific config, never committed.** It's the YAML repo
  watch list, read from the env var (a GitHub Secret in production, `.env` locally). Schema
  is in `.env.example`. Most target repos don't label issues "good first issue" — that's why
  triage is an LLM call and not a label search — so leaving `labels`/`search_terms` unset is
  the norm; only add them to pre-filter the search. **Never add label/search-term
  restrictions unprompted.**

- **`AGENT_SEARCH_WINDOW_HOURS` (default 25) is not derived from the cron schedule** in
  `.github/workflows/notify.yml` — it's a separate manual value, set slightly above the ~24h
  cadence so a delayed run doesn't drop issues created in the gap. Change one, change the
  other.

- **GitHub's Search API secondary-rate-limits rapid consecutive requests** well under the
  documented quota. `run.py` puts a flat `GITHUB_SEARCH_DELAY_SECONDS = 2.0` sleep between
  per-repo searches — deliberately flat, not a dynamic backoff, since a run only searches a
  handful of repos once a day. `github_client.search_issues()` logs the response body on
  error because httpx's default message hides *which* limit GitHub says was hit.

- **Logfire falls back to console automatically** when `LOGFIRE_TOKEN` is unset — there's no
  separate "dev mode" flag. Each pipeline run is wrapped in a `digest_run` span;
  `logfire.instrument_pydantic_ai()` traces every agent/model call with no per-agent setup.
  Expecting cloud traces but seeing console output? Check `.env` for the token.

- **If you ever add a tool** (there are none today): `ModelRetry` is reserved for errors the
  LLM can plausibly fix by changing its input (bad query format, out-of-range params).
  Anything else is logged and re-raised as a normal exception — don't use `ModelRetry` as a
  generic catch-all; it burns the agent's retry budget on failures it can't correct.

## Built on

[agent-template](https://github.com/tmtabor/agent-template) — the generic Pydantic AI agent
template this was forked from.
