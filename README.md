# JEV Codex Tool Gate

Use TypeSafe JEV as a personal, automatic decision layer for local Codex tool
calls. JEV runs before supported local actions and returns a calibrated
allow-or-deny result.

```text
Codex proposes a local tool call
→ Codex PreToolUse hook calls JEV through MCP
→ JEV allows or denies the call
→ Codex executes the call or replans
```

This is designed as a **user-level Codex setup**: install it once and use it
in every local project. It is not a ChatGPT Web plugin and does not require
ngrok, a public URL, or cloud hosting.

## What it provides

| Component | Purpose |
| --- | --- |
| `jev_guard_tool_call` | Automatically called by the Codex hook before supported local tool calls. |
| `jev_noul` | An optional MCP tool that returns JEV’s calibrated probability for a bounded yes/no proposition. |
| User-level `PreToolUse` hook | Connects the automatic gate to every local Codex project. |

JEV evaluates decisions; it does not execute external actions itself.

## Requirements

- [Codex desktop or Codex CLI](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- Python 3.11 or newer
- A TypeSafe API key
- Windows instructions below use the `py` launcher. On macOS/Linux, replace
  `py -3.11` with your Python 3.11 command, usually `python3.11`.

## Install once for all Codex projects

### 1. Clone and install

Choose a permanent location. Do not delete or move this folder after setup
without updating the Codex configuration.

```powershell
git clone https://github.com/YOUR_GITHUB_USERNAME/jev-chatgpt-plugin.git
cd jev-chatgpt-plugin
py -3.11 -m pip install -e '.[dev]'
```

### 2. Create your private configuration

```powershell
Copy-Item .env.example .env
```

Open `.env` and add your TypeSafe key:

```dotenv
TYPESAFE_API_KEY=your-real-typesafe-key
JEV_PRE_TOOL_MINIMUM_PROBABILITY=0.75
```

Never commit `.env`, paste its key into chat, or share it. The default `0.75`
requires JEV to estimate at least 75% probability before it allows a tool call.

### 3. Register the MCP server globally

Open your user-level Codex configuration:

```powershell
notepad $env:USERPROFILE\.codex\config.toml
```

Append the following, replacing the `cwd` path with the **absolute path where
you cloned this repository**. Do not add a second block if
`[mcp_servers.jev]` already exists; update that existing block instead.

```toml
[mcp_servers.jev]
command = "py"
args = ["-3.11", "-m", "jev_plugin.mcp"]
cwd = 'C:\Users\YOUR_USERNAME\path\to\jev-chatgpt-plugin'
env_vars = [
  "TYPESAFE_API_KEY",
  "TYPESAFE_MODEL",
  "JEV_PRE_TOOL_MINIMUM_PROBABILITY",
]
startup_timeout_sec = 30
tool_timeout_sec = 30
```

The `cwd` is important: it lets the MCP server load the repository’s private
`.env` file regardless of which project you open in Codex.

### 4. Register the global hook

Create or open the user-level hooks file:

```powershell
notepad $env:USERPROFILE\.codex\hooks.json
```

If the file is empty or does not exist, paste this complete JSON:

```json
{
  "description": "Personal JEV MCP decision gate for supported local Codex tool calls.",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "mcp_tool",
            "server": "jev",
            "tool": "jev_guard_tool_call",
            "input": {
              "tool_name": "${tool_name}",
              "tool_input": "${tool_input}",
              "cwd": "${cwd}",
              "permission_mode": "${permission_mode}"
            },
            "timeout": 30,
            "statusMessage": "JEV is evaluating the proposed tool call"
          }
        ]
      }
    ]
  }
}
```

If `hooks.json` already contains other hooks, merge only the shown
`PreToolUse` entry into its existing `hooks` object. Do not overwrite unrelated
hooks.

### 5. Restart, verify, and trust

1. Fully restart Codex.
2. Open **any** local project in Codex.
3. Run `/mcp` and verify that **jev** is connected.
4. Run `/hooks` and review/trust the hook named `jev_guard_tool_call`.

The trust applies to your user-level hook, not just the current project.

## Test in any repository

Ask Codex:

```text
Run the test suite and report any failures.
```

Before Codex executes a supported local tool call, you should see:

```text
JEV is evaluating the proposed tool call
```

- **Allowed:** Codex runs the tool call.
- **Denied:** Codex does not run it and must replan or ask for clarification.

For an explicit calibrated decision, ask:

```text
Use jev_noul to evaluate this state:
state: { "change_is_reversible": false }
proposition: "The change should proceed without review."
Show the probability.
```

## Scope and limitations

| Tool path | Automatic JEV gate? |
| --- | --- |
| Local shell commands | Yes |
| `apply_patch` edits | Yes |
| Connected local MCP tools | Yes |
| Most other local Codex function tools | Yes |
| Hosted tools such as WebSearch | No |
| ChatGPT Web tool calls | No |

If JEV is connected but TypeSafe returns an error or malformed answer, the
server returns a deny decision. If the whole **jev** MCP server is disconnected,
Codex continues instead; verify **jev** in `/mcp` after updates or configuration
changes.

## Development checks

```powershell
py -3.11 -m pytest -q
py -3.11 -m ruff check src test
py -3.11 -m mypy src
py -3.11 -m build
```

## References

- [Codex MCP configuration](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)
- [Codex hooks and MCP tool hooks](https://learn.chatgpt.com/docs/hooks)
- [TypeSafe JEV](https://autojev.ai/)
