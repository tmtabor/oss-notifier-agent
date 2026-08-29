"""Pytest fixtures for eval runs."""

import json
from pathlib import Path

import pytest

from agent.logging import configure_logging


@pytest.fixture(scope="session", autouse=True)
def setup_logging():
    """Configure logging once for the eval session."""
    configure_logging()


@pytest.fixture
def triage_cases() -> list[dict]:
    """Load the triage eval cases from JSON."""
    fixtures_path = Path(__file__).parent / "fixtures" / "triage_cases.json"
    return json.loads(fixtures_path.read_text())
