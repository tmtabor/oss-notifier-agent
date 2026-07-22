"""Postmark email delivery for the good-first-issue digest.

Builds a plain HTML digest (no templating dependency — the template stays
minimal-dependency and this markup is simple enough not to need one) and
POSTs it via Postmark's transactional email API.
"""

from __future__ import annotations

import html

import httpx

from agent.agents.single import AgentOutput
from agent.config import settings
from agent.logging import get_logger
from agent.pipeline.models import Issue

logger = get_logger(__name__)

POSTMARK_URL = "https://api.postmarkapp.com/email"


class PostmarkConfigError(RuntimeError):
    """Raised when required Postmark settings are missing at send time."""


class PostmarkClient:
    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=30.0)
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def send_digest(self, flagged: list[tuple[Issue, AgentOutput]]) -> None:
        """Send the digest email. No-ops (via the caller) if flagged is empty.

        Raises:
            PostmarkConfigError: Required settings are missing.
            httpx.HTTPStatusError: Postmark rejected the request.
        """
        if not settings.postmark_server_token:
            raise PostmarkConfigError("POSTMARK_SERVER_TOKEN is not set.")
        if not settings.email_from:
            raise PostmarkConfigError("AGENT_EMAIL_FROM is not set.")
        if not settings.email_to:
            raise PostmarkConfigError("AGENT_EMAIL_TO is not set.")

        recipients = [addr.strip() for addr in settings.email_to.split(",") if addr.strip()]
        html_body = _render_digest_html(flagged)

        response = await self._client.post(
            POSTMARK_URL,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": settings.postmark_server_token,
            },
            json={
                "From": settings.email_from,
                "To": ", ".join(recipients),
                "Subject": f"OSS Notifier Agent: {len(flagged)} issues found",
                "HtmlBody": html_body,
                "MessageStream": "outbound",
            },
        )
        response.raise_for_status()
        logger.info(
            "Digest email sent",
            extra={"recipient_count": len(recipients), "issue_count": len(flagged)},
        )


def _render_digest_html(flagged: list[tuple[Issue, AgentOutput]]) -> str:
    rows = []
    for issue, verdict in flagged:
        rows.append(f"""
        <li style="margin-bottom: 1.5em;">
            <a href="{html.escape(issue.html_url)}"><strong>{html.escape(issue.title)}</strong></a>
            <br><span style="color: #666;">{html.escape(issue.repo)}</span>
            <p>{html.escape(verdict.summary)}</p>
            <p><em>{html.escape(verdict.reasoning)}</em></p>
        </li>
        """)
    return f"""
    <html>
    <body>
        <h2>Good first issues digest</h2>
        <ul>{"".join(rows)}</ul>
    </body>
    </html>
    """
