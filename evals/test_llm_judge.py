"""LLM-as-judge evals for the good-first-issue triage agent.

These evals use a separate LLM (settings.judge_model) to evaluate output
quality. They require an API key and cost money to run.
Run with: uv run pytest -m eval  (runs alongside the pass/fail evals)
"""

import pytest

from agent.agents import run_agent
from evals.judge import judge_response


@pytest.mark.eval
async def test_reasoning_is_faithful_to_issue_body():
    """The judge checks that reasoning cites specifics from the issue, not generic filler."""
    task = (
        "Repository: octocat/example-repo\n"
        "Title: Off-by-one error in pagination\n"
        "Labels: bug, good first issue\n"
        "URL: https://github.com/octocat/example-repo/issues/3\n\n"
        "Body:\nWhen requesting page 2 with page_size=10, the API returns items 21-30 instead of "
        "11-20. The bug is in paginate() in utils/pagination.py, where the offset calculation uses "
        "`page * page_size` instead of `(page - 1) * page_size`."
    )
    output = await run_agent(task)

    verdict = await judge_response(
        task=task,
        response=output.reasoning,
        criteria="The reasoning should be exactly one sentence, should reference specific details "
        "from the issue body (e.g. the pagination bug, the file, or the offset calculation), and "
        "should support flagging this issue as a good first issue.",
        threshold=0.7,
    )
    assert verdict.passed, (
        f"Judge score {verdict.score:.2f} below threshold. Reasoning: {verdict.reasoning}"
    )


@pytest.mark.eval
async def test_summary_points_to_where_to_start():
    """The judge checks the summary names the fix and a concrete starting point in the repo."""
    task = (
        "Repository: octocat/example-repo\n"
        "Title: Off-by-one error in pagination\n"
        "Labels: bug, good first issue\n"
        "URL: https://github.com/octocat/example-repo/issues/3\n\n"
        "Body:\nWhen requesting page 2 with page_size=10, the API returns items 21-30 instead of "
        "11-20. The bug is in paginate() in utils/pagination.py, where the offset calculation uses "
        "`page * page_size` instead of `(page - 1) * page_size`."
    )
    output = await run_agent(task)

    verdict = await judge_response(
        task=task,
        response=output.summary,
        criteria="The summary should be exactly two sentences: one describing the required fix, "
        "and one pointing to where in the repository to start looking (e.g. paginate() in "
        "utils/pagination.py).",
        threshold=0.6,
    )
    assert verdict.passed, (
        f"Judge score {verdict.score:.2f} below threshold. Reasoning: {verdict.reasoning}"
    )
