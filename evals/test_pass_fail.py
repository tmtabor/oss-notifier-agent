"""Pass/fail evals for the good-first-issue triage agent.

These evals test for specific, verifiable outputs.
Run with: uv run pytest -m eval
"""

from dataclasses import dataclass

import pytest
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Evaluator, EvaluatorContext

from agent.agents import run_agent

TYPO_FIX_ISSUE = (
    "Repository: octocat/example-repo\n"
    "Title: Fix typo in README\n"
    "Labels: good first issue\n"
    "URL: https://github.com/octocat/example-repo/issues/1\n\n"
    "Body:\nThe word 'recieve' on line 12 of README.md should be 'receive'."
)

ARCHITECTURE_REDESIGN_ISSUE = (
    "Repository: octocat/example-repo\n"
    "Title: Redesign caching layer for better performance\n"
    "Labels: enhancement\n"
    "URL: https://github.com/octocat/example-repo/issues/2\n\n"
    "Body:\nOur current caching approach doesn't scale well under high concurrency. We should "
    "investigate alternative architectures such as a distributed cache with consistent hashing, "
    "potentially replacing the current LRU implementation across every subsystem that depends on it."
)


@pytest.mark.eval
async def test_agent_flags_clear_typo_fix():
    """A localized, clearly-described fix should be flagged as a good first issue."""
    output = await run_agent(TYPO_FIX_ISSUE)
    assert output.is_good_first_issue is True
    assert output.reasoning
    assert output.summary


@pytest.mark.eval
async def test_agent_rejects_architecture_redesign():
    """A cross-cutting architectural change should not be flagged."""
    output = await run_agent(ARCHITECTURE_REDESIGN_ISSUE)
    assert output.is_good_first_issue is False


# --- Dataset eval driven by evals/fixtures/example.json ---


@dataclass
class MatchesExpectedVerdict(Evaluator[str, bool]):
    """Pass if the agent's is_good_first_issue verdict matches the expected boolean."""

    def evaluate(self, ctx: EvaluatorContext[str, bool]) -> bool:
        if ctx.expected_output is None:
            return ctx.output is not None
        return ctx.output == ctx.expected_output


@pytest.mark.eval
async def test_fixture_dataset(example_fixtures: list[dict]):
    """Run every case in evals/fixtures/example.json through the agent.

    Add cases to that JSON file to grow this eval — no code changes needed
    unless a case requires a new kind of check, in which case add an
    Evaluator like MatchesExpectedVerdict above.
    """
    dataset = Dataset(
        cases=[
            Case(
                name=fixture["name"],
                inputs=fixture["inputs"]["user_input"],
                expected_output=fixture.get("expected_output"),
                metadata=fixture.get("metadata"),
            )
            for fixture in example_fixtures
        ],
        evaluators=[MatchesExpectedVerdict()],
    )

    async def task(user_input: str) -> bool:
        output = await run_agent(user_input)
        return output.is_good_first_issue

    report = await dataset.evaluate(task)
    report.print(include_input=True, include_output=True)

    averages = report.averages()
    assert averages is not None
    assert averages.assertions == 1.0, "One or more eval cases failed — see the report above."
