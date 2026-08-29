"""Canonical names for the triage agent.

tests/ and evals/ import `run_agent`, `AgentOutput`, `AgentDeps`, and `agent`
from this package rather than from `agent.agents.single` directly, so the
concrete module can be reorganized without touching them.
"""

from agent.agents.single import AgentDeps, AgentOutput, agent, run_agent

__all__ = ["AgentDeps", "AgentOutput", "agent", "run_agent"]
