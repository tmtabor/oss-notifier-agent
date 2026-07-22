"""GitHub Search API client: fetches new, unassigned, open issues.

Deterministic ingestion — no LLM involved. Pre-filters heavily via the search
query itself (state, assignee, creation time, labels/keywords) before any
issue body is downloaded, to minimize both API rate-limit usage and the
number of issues the triage agent has to look at.
"""

from __future__ import annotations

import httpx

from agent.config import settings
from agent.logging import get_logger
from agent.pipeline.config import PipelineConfig, RepoConfig
from agent.pipeline.models import Issue

logger = get_logger(__name__)

SEARCH_URL = "https://api.github.com/search/issues"
PER_PAGE = 50


class GitHubIssuesClient:
    """Thin wrapper around the GitHub Search API for issues."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=30.0)
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if settings.github_token:
            headers["Authorization"] = f"token {settings.github_token}"
        return headers

    async def search_issues(
        self,
        repo_config: RepoConfig,
        pipeline_config: PipelineConfig,
        since_iso: str,
        max_body_chars: int,
    ) -> list[Issue]:
        """Search one repository for new, open, unassigned issues.

        Args:
            repo_config: The repo and its label/search-term overrides.
            pipeline_config: The full PipelineConfig, for default label/term fallback.
            since_iso: ISO-8601 timestamp — only issues created after this are returned.
            max_body_chars: Issue bodies longer than this are truncated.

        Returns:
            Matching issues, truncated to max_body_chars.
        """
        query = self._build_query(repo_config, pipeline_config, since_iso)
        logger.info("Searching issues", extra={"repo": repo_config.repo, "query": query})

        response = await self._client.get(
            SEARCH_URL,
            params={"q": query, "per_page": PER_PAGE},
            headers=self._headers(),
        )
        if response.is_error:
            # httpx.HTTPStatusError's default message doesn't include the
            # response body, which is where GitHub explains *which* limit was
            # hit (primary quota vs. secondary/abuse rate limit) — log it so a
            # failure is actually diagnosable instead of just a bare stack trace.
            logger.error(
                "GitHub search request failed",
                extra={
                    "repo": repo_config.repo,
                    "status_code": response.status_code,
                    "response_body": response.text[:1000],
                },
            )
        response.raise_for_status()
        items = response.json().get("items", [])

        issues = []
        for item in items:
            body = item.get("body") or ""
            truncated = len(body) > max_body_chars
            if truncated:
                body = body[:max_body_chars]
            issues.append(
                Issue(
                    repo=repo_config.repo,
                    title=item["title"],
                    body=body,
                    labels=[label["name"] for label in item.get("labels", [])],
                    html_url=item["html_url"],
                    created_at=item["created_at"],
                    truncated=truncated,
                )
            )
        logger.info("Search complete", extra={"repo": repo_config.repo, "issue_count": len(issues)})
        return issues

    def _build_query(
        self, repo_config: RepoConfig, pipeline_config: PipelineConfig, since_iso: str
    ) -> str:
        parts = [
            f"repo:{repo_config.repo}",
            "is:issue",
            "is:open",
            "no:assignee",
            f"created:>{since_iso}",
        ]

        labels = pipeline_config.labels_for(repo_config)
        for label in labels:
            parts.append(f'label:"{label}"')

        search_terms = pipeline_config.search_terms_for(repo_config)
        if search_terms:
            terms = " OR ".join(f'"{term}"' for term in search_terms)
            parts.append(f"({terms})" if len(search_terms) > 1 else terms)

        return " ".join(parts)
