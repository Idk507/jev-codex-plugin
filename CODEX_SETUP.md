# JEV for Codex: one-time personal setup

JEV is now configured at your **Codex user level**, not per project. Once you
finish this guide, it is available whenever you open any local project in
Codex.

```text
Any local project in Codex
→ Codex proposes a supported local tool call
→ your personal JEV hook calls the JEV MCP server
→ JEV allows or denies the call
```

You do **not** need to reopen this JEV repository in Codex after setup. Keep
the folder on disk because it contains the local JEV MCP server code.

## One-time setup

### 1. Install the JEV package

Open PowerShell and run:

```powershell
cd C:\Users\dhanu\Downloads\jev-chatgpt-plugin
py -3.11 -m pip install -e '.[dev]'
```

### 2. Set your private TypeSafe key

In the same folder, create `.env` only when it does not already exist:

```powershell
Test-Path .env
```

If it prints `False`, run:

```powershell
Copy-Item .env.example .env
```

Open `.env` and set:

```dotenv
TYPESAFE_API_KEY=your-real-typesafe-key
JEV_PRE_TOOL_MINIMUM_PROBABILITY=0.75
```

Do not commit or share `.env`.

### 3. Restart Codex once

Fully close and reopen Codex. JEV has been registered in your personal Codex
configuration here:

```text
C:\Users\dhanu\.codex\config.toml
C:\Users\dhanu\.codex\hooks.json
```

Those files apply across all local projects. Do not add JEV again in a project
MCP settings form.

### 4. Trust the personal hook once

Open any local project in Codex and type:

```text
/mcp
```

Confirm that **jev** is connected and exposes:

- `jev_guard_tool_call`
- `jev_noul`

Then type:

```text
/hooks
```

Review and trust the hook with these values:

```text
event: PreToolUse
server: jev
tool: jev_guard_tool_call
```

Trust is tied to the hook definition, not a single project. You only need to
review it again if the hook configuration changes.

## Use JEV in every project

Open any repository in Codex and work normally. For supported local tools,
you should see:

```text
JEV is evaluating the proposed tool call
```

You do not need to include “use JEV” in your prompt. Example prompts in a
different repository:

```text
Run the tests and fix the first failure.
```

```text
Review the changed files for likely bugs, then run the relevant checks.
```

JEV automatically evaluates supported local shell calls, edits, connected MCP
tool calls, and most other local Codex function calls before execution.

## Optional direct JEV decision

For a bounded decision, you can explicitly ask Codex to use `jev_noul`:

```text
Use jev_noul to evaluate this state:
state: { "change_is_reversible": false }
proposition: "The change should proceed without review."
Show the probability.
```

## Important limits

| Situation | What happens |
| --- | --- |
| JEV returns a low probability | Codex is denied the pending local call and replans. |
| TypeSafe/JEV fails while connected | The JEV MCP tool returns a deny decision. |
| The **jev** MCP server is disconnected | Codex continues; always confirm **jev** in `/mcp` after a Codex update or configuration change. |
| Hosted tools such as WebSearch | They are not in the local hook path, so JEV cannot gate them. |
| ChatGPT Web tool calls | The personal local Codex configuration does not control them. |

## If you move or delete the JEV folder

The global MCP configuration points to:

```text
C:\Users\dhanu\Downloads\jev-chatgpt-plugin
```

If you move that folder, update the `cwd` value under `[mcp_servers.jev]` in
`C:\Users\dhanu\.codex\config.toml`, then restart Codex. If you delete the
folder, JEV will no longer start.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| **jev** missing from `/mcp` | Run the installation command again, confirm the JEV folder still exists, then restart Codex. |
| `No module named jev_plugin` | Run `py -3.11 -m pip install -e '.[dev]'` inside the JEV folder, then restart Codex. |
| No JEV status message | Verify **jev** in `/mcp`, then use `/hooks` to confirm the personal hook remains trusted. |
| JEV denies every call | Confirm the TypeSafe key in `.env`; leave the threshold at `0.75` until normal responses are observed. |

Technical reference: [Codex MCP setup](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) and [Codex hook locations and MCP tool hooks](https://learn.chatgpt.com/docs/hooks).
