"""Calibrated allow-or-deny policy for proposed Codex local tool calls."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field
from typesafe_sdk import Noul

from jev_plugin.core import JevResponseError

from .models import PreToolEvent


class JevEvaluator(Protocol):
    """Smallest TypeSafe boundary needed by the policy gate."""

    def evaluate(self, *, state: Any, questions: dict[str, Any]) -> Any:
        """Evaluate named TypeSafe questions."""


class PreToolResult(BaseModel):
    """A Codex-compatible decision without raw user or tool input."""

    model_config = ConfigDict(frozen=True)

    is_allowed: bool
    probability: float = Field(ge=0.0, le=1.0)
    tool_name: str

    def to_hook_output(self) -> dict[str, Any]:
        """Return the official PreToolUse hook-output shape."""
        if self.is_allowed:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": (
                        f"JEV approved {self.tool_name} with probability "
                        f"{self.probability:.2f}."
                    ),
                }
            }
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"JEV denied {self.tool_name} (appropriateness probability "
                    f"{self.probability:.2f}). Replan with a more appropriate "
                    "tool or ask for clarification."
                ),
            }
        }


class PreToolGate:
    """Ask JEV whether a proposed Codex local tool call may proceed."""

    def __init__(self, client: JevEvaluator, *, minimum_probability: float) -> None:
        if not 0.0 <= minimum_probability <= 1.0:
            raise ValueError("minimum_probability must be between 0 and 1.")
        self._client = client
        self._minimum_probability = minimum_probability

    def evaluate(self, event: PreToolEvent) -> PreToolResult:
        """Return an allow or deny result before the host executes the tool."""
        response = self._client.evaluate(
            state=event.model_dump(mode="json"),
            questions={
                "allow": Noul(
                    instructions=(
                        "Is this proposed Codex local tool call appropriate and "
                        "safe to advance the user's request with the currently "
                        "available context? Answer yes only when the specific tool "
                        "and arguments are suitable; otherwise answer no."
                    )
                )
            },
        )
        probability = self._probability(response)
        return PreToolResult(
            is_allowed=probability >= self._minimum_probability,
            probability=probability,
            tool_name=event.tool_name,
        )

    @staticmethod
    def _probability(response: Any) -> float:
        try:
            value = response.answers["allow"].noul
            probability = float(value)
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise JevResponseError("JEV returned an invalid PreToolUse result.") from error
        if not 0.0 <= probability <= 1.0:
            raise JevResponseError("JEV returned an out-of-range PreToolUse probability.")
        return probability
