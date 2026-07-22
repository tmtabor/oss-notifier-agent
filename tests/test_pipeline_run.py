"""Unit tests for agent.pipeline.run — everything stubbed, no network, no real model calls."""

from agent.agents import AgentOutput
from agent.config import settings
from agent.pipeline import run as run_module
from agent.pipeline.config import PipelineConfig, RepoConfig
from agent.pipeline.models import Issue


def make_issue(repo: str, n: int) -> Issue:
    return Issue(
        repo=repo,
        title=f"Issue {n}",
        body="body",
        labels=[],
        html_url=f"https://github.com/{repo}/issues/{n}",
        created_at="2026-07-20T00:00:00Z",
    )


class FakeGithubClient:
    def __init__(self, results_by_repo, raise_for=()):
        self.results_by_repo = results_by_repo
        self.raise_for = raise_for

    async def search_issues(self, repo_config, pipeline_config, since_iso, max_body_chars):
        if repo_config.repo in self.raise_for:
            raise RuntimeError("simulated search failure")
        return self.results_by_repo.get(repo_config.repo, [])

    async def aclose(self):
        pass


async def test_collect_issues_aggregates_across_repos(monkeypatch):
    monkeypatch.setattr(settings, "max_issues_per_run", 100)
    config = PipelineConfig(repositories=[RepoConfig(repo="a/b"), RepoConfig(repo="c/d")])
    github_client = FakeGithubClient(
        {"a/b": [make_issue("a/b", 1)], "c/d": [make_issue("c/d", 1), make_issue("c/d", 2)]}
    )

    issues = await run_module.collect_issues(config, github_client)

    assert len(issues) == 3


async def test_collect_issues_tolerates_one_repo_failing(monkeypatch):
    monkeypatch.setattr(settings, "max_issues_per_run", 100)
    config = PipelineConfig(repositories=[RepoConfig(repo="a/b"), RepoConfig(repo="c/d")])
    github_client = FakeGithubClient({"c/d": [make_issue("c/d", 1)]}, raise_for=("a/b",))

    issues = await run_module.collect_issues(config, github_client)

    assert len(issues) == 1
    assert issues[0].repo == "c/d"


async def test_collect_issues_caps_at_max_issues_per_run(monkeypatch):
    monkeypatch.setattr(settings, "max_issues_per_run", 2)
    config = PipelineConfig(repositories=[RepoConfig(repo="a/b")])
    github_client = FakeGithubClient({"a/b": [make_issue("a/b", i) for i in range(5)]})

    issues = await run_module.collect_issues(config, github_client)

    assert len(issues) == 2


async def test_triage_issues_keeps_only_flagged(monkeypatch):
    issues = [make_issue("a/b", 1), make_issue("a/b", 2)]

    async def fake_run_agent(prompt: str) -> AgentOutput:
        flag = "1" in prompt
        return AgentOutput(is_good_first_issue=flag, reasoning="r", summary="s")

    monkeypatch.setattr(run_module, "run_agent", fake_run_agent)

    flagged = await run_module.triage_issues(issues)

    assert len(flagged) == 1
    assert flagged[0][0].html_url.endswith("/1")


async def test_main_skips_email_when_nothing_flagged(monkeypatch):
    monkeypatch.setattr(run_module, "configure_logging", lambda: None)
    monkeypatch.setattr(
        run_module,
        "load_config",
        lambda: PipelineConfig(repositories=[RepoConfig(repo="a/b")]),
    )
    monkeypatch.setattr(
        run_module, "GitHubIssuesClient", lambda: FakeGithubClient({"a/b": [make_issue("a/b", 1)]})
    )

    async def fake_run_agent(prompt: str) -> AgentOutput:
        return AgentOutput(is_good_first_issue=False, reasoning="r", summary="s")

    monkeypatch.setattr(run_module, "run_agent", fake_run_agent)

    send_calls = []

    class FakePostmarkClient:
        async def send_digest(self, flagged):
            send_calls.append(flagged)

        async def aclose(self):
            pass

    monkeypatch.setattr(run_module, "PostmarkClient", FakePostmarkClient)

    await run_module.main()

    assert send_calls == []


async def test_main_sends_email_when_issues_flagged(monkeypatch):
    monkeypatch.setattr(run_module, "configure_logging", lambda: None)
    monkeypatch.setattr(
        run_module,
        "load_config",
        lambda: PipelineConfig(repositories=[RepoConfig(repo="a/b")]),
    )
    monkeypatch.setattr(
        run_module, "GitHubIssuesClient", lambda: FakeGithubClient({"a/b": [make_issue("a/b", 1)]})
    )

    async def fake_run_agent(prompt: str) -> AgentOutput:
        return AgentOutput(is_good_first_issue=True, reasoning="r", summary="s")

    monkeypatch.setattr(run_module, "run_agent", fake_run_agent)

    send_calls = []

    class FakePostmarkClient:
        async def send_digest(self, flagged):
            send_calls.append(flagged)

        async def aclose(self):
            pass

    monkeypatch.setattr(run_module, "PostmarkClient", FakePostmarkClient)

    await run_module.main()

    assert len(send_calls) == 1
    assert len(send_calls[0]) == 1


def test_print_digest_includes_issue_details(capsys):
    verdict = AgentOutput(
        is_good_first_issue=True, reasoning="Small, localized fix.", summary="Fix the thing."
    )
    run_module.print_digest([(make_issue("a/b", 1), verdict)])

    output = capsys.readouterr().out
    assert "a/b" in output
    assert "Issue 1" in output
    assert "https://github.com/a/b/issues/1" in output
    assert "Fix the thing." in output
    assert "Small, localized fix." in output


class _UnusedPostmarkClient:
    """Fails the test if instantiated — dry run must never construct a real client."""

    def __init__(self):
        raise AssertionError("PostmarkClient should not be constructed during a dry run")


async def test_main_dry_run_prints_instead_of_emailing(monkeypatch, capsys):
    monkeypatch.setattr(run_module, "configure_logging", lambda: None)
    monkeypatch.setattr(
        run_module,
        "load_config",
        lambda: PipelineConfig(repositories=[RepoConfig(repo="a/b")]),
    )
    monkeypatch.setattr(
        run_module, "GitHubIssuesClient", lambda: FakeGithubClient({"a/b": [make_issue("a/b", 1)]})
    )

    async def fake_run_agent(prompt: str) -> AgentOutput:
        return AgentOutput(is_good_first_issue=True, reasoning="r", summary="s")

    monkeypatch.setattr(run_module, "run_agent", fake_run_agent)
    monkeypatch.setattr(run_module, "PostmarkClient", _UnusedPostmarkClient)

    await run_module.main(dry_run=True)

    output = capsys.readouterr().out
    assert "good first issue" in output
    assert "a/b" in output


async def test_main_dry_run_with_nothing_flagged(monkeypatch, capsys):
    monkeypatch.setattr(run_module, "configure_logging", lambda: None)
    monkeypatch.setattr(
        run_module,
        "load_config",
        lambda: PipelineConfig(repositories=[RepoConfig(repo="a/b")]),
    )
    monkeypatch.setattr(
        run_module, "GitHubIssuesClient", lambda: FakeGithubClient({"a/b": [make_issue("a/b", 1)]})
    )

    async def fake_run_agent(prompt: str) -> AgentOutput:
        return AgentOutput(is_good_first_issue=False, reasoning="r", summary="s")

    monkeypatch.setattr(run_module, "run_agent", fake_run_agent)
    monkeypatch.setattr(run_module, "PostmarkClient", _UnusedPostmarkClient)

    await run_module.main(dry_run=True)

    output = capsys.readouterr().out
    assert "No good first issues found" in output
