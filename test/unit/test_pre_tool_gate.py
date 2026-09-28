"""Tests for the Codex PreToolUse JEV policy gate."""

from __future__ import annotations

from types import SimpleNamespace

from jev_plugin.hook import PreToolEvent, PreToolGate


class FakeJevClient:
    """Deterministic TypeSafe boundary for policy tests."""

    def __init__(self, probability: float) -> None:
        self.probability = probability

    def evaluate(self, *, state: object, questions: object) -> object:
        return SimpleNamespace(
            answers={"allow": SimpleNamespace(noul=self.probability)}
        )


def test_gate_allows_a_confident_proposed_tool_call() -> None:
    gate = PreToolGate(FakeJevClient(0.91), minimum_probability=0.75)  # type: ignore[arg-type]

    result = gate.evaluate(
        PreToolEvent(tool_name="Bash", tool_input={"command": "pytest -q"})
    )

    assert result.is_allowed is True
    assert result.probability == 0.91
    assert result.to_hook_output()["hookSpecificOutput"]["hookEventName"] == "PreToolUse"


def test_gate_denies_a_low_probability_tool_call_and_requests_replanning() -> None:
    gate = PreToolGate(FakeJevClient(0.21), minimum_probability=0.75)  # type: ignore[arg-type]

    result = gate.evaluate(
        PreToolEvent(
            tool_name="mcp__payments__issue_refund",
            tool_input={"amount": 500},
        )
    )

    output = result.to_hook_output()["hookSpecificOutput"]

    assert result.is_allowed is False
    assert output["permissionDecision"] == "deny"
    assert "Replan" in output["permissionDecisionReason"]
