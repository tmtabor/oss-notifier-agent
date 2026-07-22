"""Data models for the GitHub issue ingestion pipeline."""

from __future__ import annotations

from pydantic import BaseModel


class Issue(BaseModel):
    """A single GitHub issue returned by the Search API, trimmed to what the
    triage agent and the email digest need."""

    repo: str
    title: str
    body: str
    labels: list[str]
    html_url: str
    created_at: str
    truncated: bool = False
