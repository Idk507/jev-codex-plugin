"""Codex MCP tools backed by TypeSafe JEV.

The ``jev_guard_tool_call`` tool is intentionally shaped for Codex's
``mcp_tool`` PreToolUse hook.  It returns the documented hook decision JSON,
so the MCP evaluation is automatic rather than a tool Codex may ignore.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol

from mcp.server import MCPServer
from pydantic import BaseModel, ConfigDict, Field

from jev_plugin.config import Settings
from jev_plugin.hook.gate import JevEvaluator, PreToolGate
from jev_plugin.hook.models import PreToolEvent
from jev_plugin.typesafe import JevClient


class JevClientContext(JevEvaluator, Protocol):
    """The evaluator lifecycle required by one MCP tool request."""

    def __enter__(self) -> JevEvaluator:
        """Return an evaluator for the request."""

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> None:
        """Release the request-scoped evaluator."""


class NoulRequest(BaseModel):
    """A bounded yes/no decision request for JEV."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    state: Any = Field(description="Structured state JEV should evaluate.")
    proposition: str = Field(
        min_length=1,
        max_length=2_000,
        description="The exact proposition to judge as yes or no.",
    )


def create_server(
    *,
    settings: Settings | None = None,
    client_factory: Callable[[Settings], JevClientContext] = JevClient,
) -> MCPServer:
    """Create the local JEV MCP server.

    The first part of ``instructions`` is deliberately self-contained because
    Codex uses it while deciding when to call the server.
    """
    runtime_settings = settings or Settings()
    server = MCPServer(
        name="jev",
        title="JEV Decision Gate",
        instructions=(
            "Use jev_noul only for bounded, calibrated yes/no decisions. "
            "jev_guard_tool_call is invoked automatically by the Codex "
            "PreToolUse hook; do not call it manually to bypass approval. "
            "JEV advises decisions and does not execute external actions."
        ),
    )

    @server.tool(name="jev_guard_tool_call")
    def guard_tool_call(event: PreToolEvent) -> dict[str, Any]:
        """Allow or deny one pending Codex local tool call using JEV.

        Return a Codex PreToolUse decision object.  This tool performs no
        side effect; it only evaluates the proposed tool name and arguments.
        """
        try:
            with client_factory(runtime_settings) as client:
                result = PreToolGate(
                    client=client,
                    minimum_probability=(
                        runtime_settings.jev_pre_tool_minimum_probability
                    ),
                ).evaluate(event)
            return result.to_hook_output()
        except Exception as exc:
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        "JEV MCP tool gate is unavailable; the pending tool "
                        f"call was denied safely ({type(exc).__name__})."
                    ),
                }
            }

    @server.tool(name="jev_noul")
    def noul(request: NoulRequest) -> dict[str, float]:
        """Return JEV's calibrated probability for a bounded proposition."""
        with client_factory(runtime_settings) as client:
            response = client.evaluate(
                state=request.state,
                questions={"decision": request.proposition},
            )

        answer = response.answers["decision"].noul
        probability = float(answer)
        if not 0.0 <= probability <= 1.0:
            raise ValueError("JEV returned a probability outside [0, 1].")
        return {"probability": probability}

    return server
