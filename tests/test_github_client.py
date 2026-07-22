"""Unit tests for agent.pipeline.github_client — mocked transport, no network."""

import httpx
import pytest

from agent.pipeline.config import PipelineConfig, RepoConfig
from agent.pipeline.github_client import GitHubIssuesClient

SEARCH_RESPONSE = {
    "items": [
        {
            "title": "Fix typo in README",
            "body": "The word 'recieve' should be 'receive'.",
            "labels": [{"name": "good first issue"}],
            "html_url": "https://github.com/octocat/example-repo/issues/1",
            "created_at": "2026-07-20T00:00:00Z",
        },
        {
            "title": "No body issue",
            "body": None,
            "labels": [],
            "html_url": "https://github.com/octocat/example-repo/issues/2",
            "created_at": "2026-07-20T01:00:00Z",
        },
    ]
}


@pytest.fixture
def repo_config():
    return RepoConfig(repo="octocat/example-repo")


@pytest.fixture
def pipeline_config():
    return PipelineConfig(repositories=[RepoConfig(repo="octocat/example-repo")])


async def test_search_issues_parses_response(repo_config, pipeline_config):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "repo:octocat/example-repo" in request.url.params["q"]
        return httpx.Response(200, json=SEARCH_RESPONSE)

    client = GitHubIssuesClient(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    try:
        issues = await client.search_issues(
            repo_config, pipeline_config, "2026-07-19T00:00:00Z", 4000
        )
    finally:
        await client._client.aclose()

    assert len(issues) == 2
    assert issues[0].title == "Fix typo in README"
    assert issues[0].labels == ["good first issue"]
    assert issues[1].body == ""  # None body normalized to empty string


async def test_search_issues_truncates_long_body(repo_config, pipeline_config):
    long_body = "x" * 100
    response = {
        "items": [
            {
                "title": "Long issue",
                "body": long_body,
                "labels": [],
                "html_url": "https://github.com/octocat/example-repo/issues/3",
                "created_at": "2026-07-20T00:00:00Z",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response)

    client = GitHubIssuesClient(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    try:
        issues = await client.search_issues(
            repo_config, pipeline_config, "2026-07-19T00:00:00Z", 10
        )
    finally:
        await client._client.aclose()

    assert len(issues[0].body) == 10
    assert issues[0].truncated is True


async def test_search_issues_raises_on_http_error(repo_config, pipeline_config):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "rate limited"})

    client = GitHubIssuesClient(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    try:
        with pytest.raises(httpx.HTTPStatusError):
            await client.search_issues(repo_config, pipeline_config, "2026-07-19T00:00:00Z", 4000)
    finally:
        await client._client.aclose()


async def test_build_query_includes_labels_and_terms(repo_config):
    pipeline_config = PipelineConfig(
        defaults={"labels": ["good first issue"], "search_terms": ["typo", "docs"]},
        repositories=[repo_config],
    )
    client = GitHubIssuesClient(
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    )
    try:
        query = client._build_query(repo_config, pipeline_config, "2026-07-19T00:00:00Z")
    finally:
        await client._client.aclose()

    assert "repo:octocat/example-repo" in query
    assert "is:open" in query
    assert "no:assignee" in query
    assert 'label:"good first issue"' in query
    assert '"typo" OR "docs"' in query
