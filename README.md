# GitHub Good First Issue Digest

Scans a configured list of GitHub repositories on a schedule, uses an LLM to triage newly opened,
unassigned issues for whether they're approachable for a first-time contributor, and emails a
digest of the ones that qualify. Runs entirely on GitHub Actions — no server to host.

Built on [agent-template](https://github.com/tmtabor/agent-template).

**This repo is public and meant to be forked.** No fork-specific configuration — your repo watch
list, labels, search terms, or credentials — should ever be committed. Everything you customize
lives in your fork's own GitHub Secrets; see [Fork this repo](#fork-this-repo) below.

## Stack
- Python 3.13, uv
- Pydantic AI v2 (agents) + pydantic-evals (evals)
- Logfire (observability)
- pytest + pytest-asyncio
- GitHub Actions (scheduling), GitHub Search API (ingestion), Postmark (email delivery)

## How it works

```
GitHub Search API → truncate/filter → [triage agent, one call per issue] → digest builder → Postmark
```

The LLM only does one thing: classify a single issue as a good first issue
(`agent/agents/single.py`). Fetching, filtering, and emailing are plain, deterministic Python
(`agent/pipeline/`) — cheaper, predictable, and fully unit-testable without hitting a real model.

## Fork this repo

1. **Fork** this repository on GitHub.
2. **Write your repo watch list** as YAML (schema and examples in `.env.example`), and set it as
   the value of a new **`AGENT_PIPELINE_CONFIG`** secret
   (Settings → Secrets and variables → Actions → New repository secret). This is your watch list —
   it's never committed to git.
3. **Add the rest of the secrets** listed below. Only the API key secret matching your chosen
   `AGENT_MODEL` provider is required (Google/Gemini by default).
4. **Trigger the workflow manually** once (Actions → Good First Issue Digest → Run workflow) to
   confirm an email arrives before trusting the cron schedule.

| Secret | Required | Notes |
|---|---|---|
| `AGENT_PIPELINE_CONFIG` | Always | Your repo watch list — see step 2 above |
| `GOOGLE_API_KEY` | If `AGENT_MODEL` is a `google:...` model (the default) | |
| `ANTHROPIC_API_KEY` | If `AGENT_MODEL` is an `anthropic:...` model | |
| `OPENAI_API_KEY` | If `AGENT_MODEL` is an `openai:...` model | |
| `POSTMARK_SERVER_TOKEN` | Always | From your Postmark server |
| `AGENT_EMAIL_FROM` | Always | Must be a Postmark-verified sender |
| `AGENT_EMAIL_TO` | Always | Comma-separated recipient list |
| `LOGFIRE_TOKEN` | Optional | Falls back to console-only tracing if unset |

`GITHUB_TOKEN` needs no setup — GitHub Actions provides it automatically for reading/searching
public repo issues. `AGENT_MODEL` itself isn't sensitive; set it as a repo **variable**
(Settings → Secrets and variables → Actions → Variables) if you want to override the default, or
leave it unset.

The schedule is a `cron:` trigger in `.github/workflows/notify.yml` (default: daily at 14:09 UTC,
i.e. ~6am Pacific Standard Time — GitHub Actions cron is UTC-only with no DST support, so this
drifts to ~7am Pacific during Pacific Daylight Time; the `:09` avoids the top-of-hour scheduling
delay GitHub's own docs warn about) — edit it directly in your fork if you want a different
cadence. **`AGENT_SEARCH_WINDOW_HOURS` (default 25h) is not derived from the cron
schedule** — it's a separate, manually-set value. If you change the cron interval, update
`AGENT_SEARCH_WINDOW_HOURS` to match (plus a small buffer): too small and issues created between
runs are silently never searched.

## Local development

```bash
# Install dependencies
uv sync --group dev

# After uv sync, install Claude Code skills for pydantic-ai and logfire
uvx library-skills install --all --claude

# Copy and configure environment
cp .env.example .env
# Edit .env: add your GOOGLE_API_KEY (or override AGENT_MODEL + the matching provider key), and
# uncomment/edit the AGENT_PIPELINE_CONFIG example with your own repos

# Run unit tests (no API calls, no API key needed)
uv run pytest

# Run evals — requires a real API key, see Evals below
uv run pytest -m eval

# Run the full pipeline once, locally
uv run python -m agent.pipeline.run

# Same, but print the digest to the console instead of emailing it — everything
# up through triage still runs for real (GitHub search + real model calls),
# only the Postmark send is skipped
uv run python -m agent.pipeline.run --dry-run

# Lint
uv run ruff check .

# Format
uv run ruff format .
```

## Project structure

```
agent/
├── config.py           # Settings — validates the provider API key at import time (raises if missing)
├── logging.py           # Logfire setup — configure_logging(), get_logger()
├── agents/
│   ├── __init__.py       #   canonical names (run_agent, AgentOutput, …)
│   └── single.py          #   the triage agent — classifies one issue per call
├── prompts/
│   ├── system.txt         # Triage criteria — edit this to change what counts as "good first issue"
│   └── templates.py        # load_prompt(), render_issue_prompt()
└── pipeline/             # Deterministic orchestration — NOT agent tools
    ├── config.py           # Pipeline config loading (AGENT_PIPELINE_CONFIG env var / secret)
    ├── models.py            # Issue model
    ├── github_client.py     # GitHub Search API client
    ├── email.py              # Postmark digest delivery
    └── run.py                 # Entrypoint: uv run python -m agent.pipeline.run

tests/    # Unit tests against TestModel and mocked HTTP — no API calls, no API key needed
evals/    # Pass/fail + dataset + LLM-as-judge evals — real API calls, run with -m eval
.github/workflows/
├── ci.yml       # CI: ruff check, format check, unit tests (no secrets needed)
└── notify.yml    # The scheduled digest run (needs the secrets above)
```

## Configuration

All settings are read from the environment (see `.env.example`). Agent-specific variables carry an
`AGENT_` prefix so a generic name like `MODEL` in your shell can't silently change the provider;
API keys and `LOGFIRE_TOKEN` keep their standard names because the provider SDKs read those exact
variables directly.

| Variable | Default | Notes |
|---|---|---|
| `GOOGLE_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | — | Required for whichever provider `AGENT_MODEL` uses. `Settings` validates this at import time and raises immediately if it's missing — not a lazy/runtime check. |
| `AGENT_MODEL` | `google:gemini-3.1-flash-lite` | Per-issue triage is a cheap, high-volume classification task, so the default is a small/fast model. Any pydantic-ai model string works, including `ollama:*` for local models (no API key needed). |
| `AGENT_JUDGE_MODEL` | `anthropic:claude-sonnet-5` | Used only by the LLM-as-judge evals. Kept on Anthropic regardless of `AGENT_MODEL` to avoid self-assessment bias. |
| `LOGFIRE_TOKEN` | unset | If set, traces go to Logfire cloud. If unset, traces print to the console — no separate dev-mode flag needed. |
| `AGENT_LOG_LEVEL` | `INFO` | Standard Python logging level. |
| `GITHUB_TOKEN` | unset | GitHub Search API auth. Provided automatically in Actions; optional (rate-limited) locally. |
| `AGENT_PIPELINE_CONFIG` | — | Required. YAML repo watch list — see [Fork this repo](#fork-this-repo). |
| `POSTMARK_SERVER_TOKEN` / `AGENT_EMAIL_FROM` / `AGENT_EMAIL_TO` | — | Required to actually send the digest email. |
| `AGENT_SEARCH_WINDOW_HOURS` | `25` | How far back each run searches for newly created issues. Set independently of the cron schedule — see [Fork this repo](#fork-this-repo). |
| `AGENT_MAX_ISSUE_BODY_CHARS` | `4000` | Issue bodies longer than this are truncated before reaching the LLM. |
| `AGENT_MAX_ISSUES_PER_RUN` | `30` | Cost guardrail across the whole run, on top of the triage agent's own `USAGE_LIMITS`. |

## Usage limits

`agent/agents/single.py` defines a `USAGE_LIMITS` constant passed to every triage call — a
guardrail against runaway agentic loops. `request_limit` caps model round-trips; `total_tokens_limit`
caps overall spend. Exceeding either raises `UsageLimitExceeded` instead of silently burning
tokens. This is a single structured-output call per issue (no tool loop), so the limits are tuned
low; `AGENT_MAX_ISSUES_PER_RUN` is the guardrail for the whole batch.

## Customizing the triage criteria

Edit `agent/prompts/system.txt` to change what counts as a "good first issue." It's loaded via
`load_prompt("system")` in `agent/prompts/templates.py`.

## Observability

All agent runs and model requests are automatically traced via `logfire.instrument_pydantic_ai()`
— no per-agent setup needed. Cloud vs. console output is controlled by `LOGFIRE_TOKEN`, see
Configuration above. Each pipeline run is also wrapped in a `digest_run` Logfire span.

## Evals

- Pass/fail evals: `evals/test_pass_fail.py` — includes a `pydantic_evals` Dataset eval driven by
  `evals/fixtures/example.json` (synthetic issue text, safe to commit). Add cases to that JSON file
  to grow the eval.
- LLM-as-judge evals: `evals/test_llm_judge.py` — graded by `AGENT_JUDGE_MODEL`, checking that
  `reasoning`/`summary` are faithful to the issue content.

Both files share the same `@pytest.mark.eval` marker. `uv run pytest -m eval` runs all of them and
requires a real API key; the LLM-judge evals also cost money (an extra model call per test).

## License

BSD 3-Clause — see [LICENSE](LICENSE).
