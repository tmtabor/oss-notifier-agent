"""Triage agent: classifies a single GitHub issue as a good first issue or not.

One agent, one task — this run is called once per candidate issue by
agent/pipeline/run.py. It does no fetching, filtering, or emailing itself;
that's deterministic Python (see agent/pipeline/). The agent's only job is
the judgment call that actually needs an LLM: is this issue approachable for
a first-time contributor?
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

from agent.config import settings
from agent.logging import configure_logging, get_logger
from agent.prompts.templates import load_prompt

logger = get_logger(__name__)

# Guardrail against runaway agentic loops. A run that exceeds either limit
# raises UsageLimitExceeded instead of silently burning tokens. This agent
# makes a single structured-output classification call per issue (no tool
# loop), so the limits are tuned well below the template's tool-calling
# defaults — one retry on a validation failure is all that's expected.
USAGE_LIMITS = UsageLimits(request_limit=3, total_tokens_limit=20_000)


# --- Output type ---
class AgentOutput(BaseModel):
    """Triage verdict for a single GitHub issue."""

    is_good_first_issue: bool
    reasoning: str = Field(description="One-sentence justification based on the issue body.")
    summary: str = Field(
        description="Two-sentence summary of the required fix and where to start looking."
    )


# --- Dependencies ---
# No external dependencies — the agent only reasons over the issue text
# passed in the prompt.
@dataclass
class AgentDeps:
    """Runtime dependencies injected into the agent."""

    pass


# --- Agent definition ---
agent: Agent[AgentDeps, AgentOutput] = Agent(
    settings.model,
    name="agent",  # labels this agent's run span in Logfire traces
    output_type=AgentOutput,
    deps_type=AgentDeps,
    instructions=load_prompt("system"),  # loads agent/prompts/system.txt
)


async def run_agent(user_input: str, deps: AgentDeps | None = None) -> AgentOutput:
    """Classify one issue, given a rendered issue prompt.

    Args:
        user_input: The issue prompt, built by
            agent.prompts.templates.render_issue_prompt().
        deps: Runtime dependencies. Created with defaults if not provided.

    Returns:
        Validated AgentOutput instance.
    """
    if deps is None:
        deps = AgentDeps()

    logger.info("Running triage agent", extra={"user_input": user_input})

    result = await agent.run(user_input, deps=deps, usage_limits=USAGE_LIMITS)

    logger.info("Agent run complete", extra={"output": result.output})
    return result.output


if __name__ == "__main__":
    import asyncio

    configure_logging()
    output = asyncio.run(
        run_agent(
            "Repository: octocat/example-repo\n"
            "Title: Fix typo in README\n"
            "Labels: good first issue\n"
            "URL: https://github.com/octocat/example-repo/issues/1\n\n"
            "Body:\nThe word 'recieve' on line 12 of README.md should be 'receive'."
        )
    )
    print(output)
