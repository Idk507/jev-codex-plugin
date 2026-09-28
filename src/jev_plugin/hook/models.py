"""Validated contracts for Codex PreToolUse hook events."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PreToolEvent(BaseModel):
    """The subset of a Codex PreToolUse event required for JEV gating."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    tool_name: str = Field(min_length=1, max_length=256)
    tool_input: Any
    cwd: str | None = Field(default=None, max_length=4_096)
    permission_mode: str | None = Field(default=None, max_length=64)

