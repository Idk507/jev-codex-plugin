from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from jev_plugin.config import Settings
from jev_plugin.mcp import create_server


class FakeClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def evaluate(self, *, state: Any, questions: dict[str, Any]) -> Any:
        del state
        if "allow" in questions:
            return SimpleNamespace(
                answers={"allow": SimpleNamespace(noul=0.93)}
            )
        return SimpleNamespace(
            answers={"decision": SimpleNamespace(noul=0.61)}
        )


def settings() -> Settings:
    return Settings(typesafe_api_key="test-key")


@pytest.mark.asyncio
async def test_server_exposes_typed_jev_tools() -> None:
    server = create_server(settings=settings(), client_factory=FakeClient)

    names = {tool.name for tool in await server.list_tools()}

    assert names == {"jev_guard_tool_call", "jev_noul"}


@pytest.mark.asyncio
async def test_guard_tool_returns_codex_hook_allow_output() -> None:
    server = create_server(settings=settings(), client_factory=FakeClient)

    result = await server.call_tool(
        "jev_guard_tool_call",
        {
            "event": {
                "tool_name": "Bash",
                "tool_input": {"command": "pytest -q"},
                "cwd": "C:/project",
                "permission_mode": "default",
            }
        },
    )

    assert result.structured_content == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                "JEV approved Bash with probability 0.93."
            ),
        }
    }


@pytest.mark.asyncio
async def test_noul_returns_calibrated_probability() -> None:
    server = create_server(settings=settings(), client_factory=FakeClient)

    result = await server.call_tool(
        "jev_noul",
        {
            "request": {
                "state": {"candidate": "Bash"},
                "proposition": "The candidate is appropriate.",
            }
        },
    )

    assert result.structured_content == {"probability": 0.61}
