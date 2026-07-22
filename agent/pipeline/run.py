"""Pipeline entrypoint: scan configured repos, triage new issues, email a digest.

Deterministic orchestration — fetching, filtering, and emailing are plain
Python; only the per-issue "is this a good first issue?" judgment goes
through the triage agent (agent/agents/single.py). Run with:

    uv run python -m agent.pipeline.run
    uv run python -m agent.pipeline.run --dry-run   # print the digest instead of emailing it
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

import logfire

from agent.agents import AgentOutput, run_agent
from agent.config import settings
from agent.logging import configure_logging, get_logger
from agent.pipeline.config import PipelineConfig, load_config
from agent.pipeline.email import PostmarkClient
from agent.pipeline.github_client import GitHubIssuesClient
from agent.pipeline.models import Issue
from agent.prompts.templates import render_issue_prompt

logger = get_logger(__name__)


async def collect_issues(config: PipelineConfig, github_client: GitHubIssuesClient) -> list[Issue]:
    """Search every configured repo, tolerating individual repo failures."""
    since_iso = (datetime.now(UTC) - timedelta(hours=settings.search_window_hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    issues: list[Issue] = []
    for repo_config in config.repositories:
        try:
            repo_issues = await github_client.search_issues(
                repo_config, config, since_iso, settings.max_issue_body_chars
            )
            issues.extend(repo_issues)
        except Exception:
            logger.error(
                "Failed to search repo, skipping", extra={"repo": repo_config.repo}, exc_info=True
            )

    if len(issues) > settings.max_issues_per_run:
        logger.warning(
            "Issue count exceeds max_issues_per_run, truncating",
            extra={"found": len(issues), "cap": settings.max_issues_per_run},
        )
        issues = issues[: settings.max_issues_per_run]

    return issues


async def triage_issues(issues: list[Issue]) -> list[tuple[Issue, AgentOutput]]:
    """Classify each issue, keeping only ones flagged as good first issues."""
    flagged: list[tuple[Issue, AgentOutput]] = []
    for issue in issues:
        verdict = await run_agent(render_issue_prompt(issue))
        if verdict.is_good_first_issue:
            flagged.append((issue, verdict))
    return flagged


def print_digest(flagged: list[tuple[Issue, AgentOutput]]) -> None:
    """Print the digest to the console instead of emailing it (--dry-run)."""
    print(f"\n{len(flagged)} good first issue{'s' if len(flagged) != 1 else ''} found:\n")
    for issue, verdict in flagged:
        print(f"- [{issue.repo}] {issue.title}")
        print(f"  {issue.html_url}")
        print(f"  Summary:   {verdict.summary}")
        print(f"  Reasoning: {verdict.reasoning}\n")


async def main(dry_run: bool = False) -> None:
    configure_logging()

    with logfire.span("digest_run"):
        config = load_config()
        logger.info("Loaded pipeline config", extra={"repo_count": len(config.repositories)})

        github_client = GitHubIssuesClient()
        try:
            issues = await collect_issues(config, github_client)
        finally:
            await github_client.aclose()
        logger.info("Issues collected", extra={"issue_count": len(issues)})

        flagged = await triage_issues(issues)
        logger.info("Triage complete", extra={"flagged_count": len(flagged)})

        if not flagged:
            logger.info("No good first issues found, skipping email")
            if dry_run:
                print("\nNo good first issues found.")
            return

        if dry_run:
            logger.info("Dry run — printing digest instead of emailing")
            print_digest(flagged)
            return

        postmark_client = PostmarkClient()
        try:
            await postmark_client.send_digest(flagged)
        finally:
            await postmark_client.aclose()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the good-first-issue digest pipeline.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Search and triage issues as normal, but print the digest instead of emailing it.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(main(dry_run=args.dry_run))
