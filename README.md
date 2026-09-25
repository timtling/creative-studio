# creative-studio

A creative studio team of agents for SME and start-up brand, product and launch work, built as a Claude plugin in the same pattern as `engagement-studio`.

Version 0.1.0 ships the imagery layer: the **Art Director** agent, the **image-generation** skill on Recraft and Replicate, a provenance ledger, and hooks that enforce budget, licence and paid-plan rules. The Producer, the other studio agents and the panel come in later versions.

## Set-up (once, about ten minutes)

### 1. Recraft: paid plan first, then the connector

1. Put the Recraft account on a **paid plan before the first client generation**. Free-plan images are public, owned by Recraft and personal-use only, and upgrading later does not transfer them.
2. In Claude, open **Settings → Connectors → Add custom connector**:
   - Name: `Recraft` (exactly, because the hooks match on it)
   - URL: `https://mcp.recraft.ai/mcp`
   - Shortcut: [Add Recraft to Claude](https://claude.ai/customize/connectors?modal=add-custom-connector&connectorName=Recraft&connectorUrl=https%3A%2F%2Fmcp.recraft.ai%2Fmcp)
3. On first use, Claude sends you to Recraft to authorise with OAuth. There is no API key to manage. Calls draw on the plan's credits.

### 2. Replicate: token, then the connector

1. Create an API token at replicate.com → Account → API tokens, named `creative-studio`.
2. In Claude, open **Settings → Connectors → Add custom connector**:
   - Name: `Replicate` (exactly)
   - URL: `https://mcp.replicate.com/sse`
3. Click **Connect**, paste the token, then **Log in and Approve**.
4. Note that Replicate's hosted server uses the SSE transport, and Claude has said SSE support may be retired. If Replicate publishes a streamable HTTP URL, switch to it.

Both connectors live on your Claude account, so they work in the web app, the desktop app, mobile and cloud sessions without installing anything locally.

### 3. Network allowlist for saving files

Generation runs from Claude's servers, but saving the output into a job folder happens in the session's sandbox, which only reaches allowlisted hosts. Add these to the network allowlist in Claude's settings (Settings → Capabilities, code execution network access):

```
img.recraft.ai
replicate.delivery
*.replicate.delivery
```

For Claude Code on the web, add the same hosts under the environment's **Network access → Custom** and keep the default package-manager list.

Without these entries, generation still works but outputs stay `pending-fetch`. Replicate deletes outputs after an hour.

### 4. Claude Code (for developing the plugin)

`.mcp.json` in this repo registers both servers for Claude Code sessions opened here. Run `/mcp` once to authenticate. It is a development convenience and is not packaged into the plugin: the packaged plugin relies on the account-level connectors above.

### 5. Install

```
tools/package.sh            # builds dist/creative-studio.plugin
```

Install the `.plugin` file in Claude the same way as `engagement-studio`.

## Per job

```
python3 skills/image-generation/scripts/imagekit.py init jobs/<client>-<job> --client <client> --job <job> --cap-calls 60
python3 skills/image-generation/scripts/imagekit.py confirm-recraft-paid --plan Pro --job jobs/<client>-<job>
```

Then brief the Art Director. The skill covers the rest.

## Check the set-up

In a new session with the plugin installed and a test job initialised:

1. "Show my Recraft account and remaining credits." (a read call, never blocked)
2. "Generate one draft vector icon of a paper boat with Recraft." The hook should save it as `A-001`. If it shows `pending-fetch`, the allowlist is not in place yet.
3. "Search Replicate for a photoreal text-to-image model." (read only). Clear one with `approve-model` and run a single draft.
4. Run `imagekit.py status` and `imagekit.py sheet`.

## What the hooks enforce

| Before a call that spends credits | After any Recraft or Replicate call |
|---|---|
| Recraft paid plan confirmed for the job | Spend logged to `assets/calls.jsonl` |
| Replicate model cleared for commercial use, named as owner/name | Outputs downloaded to `assets/raw/` and recorded in `assets/ledger.jsonl` |
| Call cap and optional US$ cap not exceeded | Inline images saved directly |
| Exactly one active job, so assets cannot cross clients | The agent is told what was saved, what is pending and the minutes left |

Outside a studio job folder, both hooks do nothing.

## Layout

```
.claude-plugin/plugin.json
agents/art-director.md
hooks/hooks.json
skills/image-generation/
  SKILL.md
  references/{model-routing,prompting,licensing}.md
  scripts/imagekit.py
tests/test_imagekit.py      # python3 -m pytest tests -q
tools/package.sh
.mcp.json                   # Claude Code development only
```
