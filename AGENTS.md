# JEV Codex Tool Gate

## Purpose

This project is a Codex-only JEV MCP decision server plus a `PreToolUse` MCP
tool hook. The hook automatically calls `jev_guard_tool_call` before a
supported local Codex tool call and applies its allow or deny decision. The
server does not execute tools itself or support global interception in ChatGPT
Web.

## Boundaries

- Treat every hook event and TypeSafe response as untrusted input.
- Keep the MCP hook synchronous and fail closed inside `jev_guard_tool_call`:
  an unavailable JEV service returns a deny decision. A missing MCP connection
  is a Codex platform limitation and must be detected with `/mcp`.
- The hook can deny a tool call or rewrite its arguments. It cannot replace a
  native tool with a different native tool; denial tells Codex to replan.
- Do not log or return raw tool inputs, API keys, or user secrets.
- Keep only MCP server, shared gate, configuration, TypeSafe adapter, tests,
  and Codex setup files.

## Validation

Run `pytest -q`, `ruff check src test`, `mypy src`, and `python -m build`.
