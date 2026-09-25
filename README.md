# creative-studio

An independent creative studio run by a team of agents. It takes brand, identity, launch, website and product UI work for direct clients (SMEs, start-ups, corporates), and one-off commissions from other teams, including the engagement studio. A Producer runs each job through stages and gates. Specialists make the work, a panel reviews it, and Tim signs off every gate.

## What is built

| Version | Adds |
|---|---|
| 0.1.0 | Art Director agent; image generation on Recraft and Replicate with a provenance ledger, budget and licence guard rails (parked until needed) |
| 0.2.0 | Producer workflow: five tracks, job set-up, planning, gates, client revision rounds, feedback triage, change requests, commissions. Studio standards and the anti-generic list. Brand vault: design tokens with validation, contrast checks, CSS, Blender and swatch-page builds, and a lint hook |
| 0.3.0 | The four creative roles: Strategist, Creative Lead, Copywriter and Identity designer. The Producer now has someone to route every stage of a brand sprint to |
| 0.3.6 | Expressive range: one territory of three must reach into art practice, and three restrained territories is a timidity finding. Art sources and five studio benchmarks. An optional expressive token layer with a texture-behind-body-text lint. An expression budget set in the brief |
| 0.3.5 | 3D needs one of three reasons before anyone renders: a physical touchpoint, a spatial territory idea argued on the board, or explanation that needs space. The `blender-3d` skill builds scenes from the vault's own colour values. The system gate says when it could not verify a refinement rather than passing quietly |
| 0.3.4 | Intake is validated against an eleven-item checklist and at least three answered questions before the brief is drafted; the brief gate refuses to raise without it |
| 0.3.3 | Builder and Delivery complete the roster, so a sprint runs intake to handover. The `studio-close` skill turns a finished job into an intervention log, a fix list and eval cases. The system gate refuses a person-attributed version that renders identically to the one before it |

Next: 0.4.0, the seven-lens panel and a studio control room so jobs outlive a session, then one full Brand Sprint run end to end on a fictional start-up.

## Using it

Install `dist/creative-studio.plugin` in Claude, then:

- **Start a job**: "New studio job: a seed-stage fintech wants a brand before their raise in October. Their email is below." The Producer picks the track, opens the job, drafts the brief, scope and plan, and sends you the brief gate pack.
- **Reply to a gate** with `approve`, `approve with: ...` or `rework: ...`.
- **Check progress**: "Where are we on heron?"
- **Commission from the engagement studio**: "Commission the studio for a cover key visual for barbet, NTT DATA brand level B2, due Friday."

Skills: `producer`, `studio-intake`, `studio-gate`, `studio-status`, `studio-close`, `commission`, `studio-standards`, `brand-vault`, `image-generation`, `blender-3d`. They are named and described so they do not trigger on engagement studio work.

## The roster

The Producer runs the job in the main session and routes each stage to the agent that owns it. Agents report to the Producer, never to the client, and each owns its files outright: others propose, the owner edits.

| Agent | Owns | Stage |
|---|---|---|
| `strategist` | `10-strategy/`: landscape, positioning, messaging hierarchy | strategy |
| `creative-lead` | `20-territories/`: three different bets, boards, recommendation | territories |
| `copywriter` | `voice.md`, `naming.md`, `*-copy.md`, wherever they sit | from territories onwards |
| `identity-designer` | `30-identity/` and `vault/`: marks, system, tokens | identity |
| `art-director` | `assets/`: art direction, shot list, ledger, contact sheet | wherever imagery is needed |
| `builder` | `50-applications/`, `50-make/`: pages, decks, launch assets | applications |
| `delivery` | `99-handover/`, `99-return/`: the client package | handover |

Still to come: the Product designer and the panel.

## Tracks

| Track | Gates (client revision rounds) |
|---|---|
| `sprint`: brand for a start-up or SME | brief (1), direction (1), system (2), final (1) |
| `launch-kit`: site, deck, social for an existing brand | brief (1), final (2) |
| `product-ui`: flows, screens, prototype | brief (1), direction (1), system (2), final (1) |
| `programme`: corporate brand programme | brief (1), direction (1), system (2), governance (1), final (2) |
| `commission`: one deliverable for another team | brief (1, can be approved by the requester), final (1) |

## Where jobs live

The Mac mini is the studio's home machine: jobs in `~/Studio/jobs/<client>-<job>`, this repo in `~/Github Projects/creative-studio`, and Blender with its GPU. Keep it awake and the Claude desktop app running, and link studio sessions to it. A job holds the job file, brief, scope, plan, stage folders, vault, gate packs and decisions log. Back up `~/Studio/jobs` (Time Machine or a Drive sync). Never keep client jobs inside this repo.

## Scripts

All standard-library Python, run by the skills:

- `skills/producer/scripts/studio.py`: `init`, `plan`, `check`, `gate raise|record`, `round`, `feedback`, `cr`, `status`, `set-active`
- `skills/brand-vault/scripts/vault.py`: `init`, `validate`, `build`, `contrast`, `lint`, `hook-lint`
- `skills/image-generation/scripts/imagekit.py`: job ledger, budget, capture, contact sheet, provenance
- `skills/blender-3d/scripts/blenderkit.py`: `presets`, `plan`, `render` (inside Blender), `verify`, `report`

## Hooks

| When | What |
|---|---|
| After writing HTML, CSS, SVG or script files in a job | Reports literal colours that bypass the vault |
| Before a Recraft or Replicate call that spends credits | Blocks it without a confirmed paid plan, a cleared model, budget, or a single active job |
| After a Recraft or Replicate call | Saves outputs to the ledger before Replicate deletes them |

All hooks do nothing outside a studio job.

## Optional: imagery set-up (parked)

Only needed when generated imagery comes back into scope.

1. Put Recraft on a paid plan first. Free-plan images are public and owned by Recraft, and upgrading later does not transfer them.
2. Add custom connectors in Claude (Settings → Connectors), named exactly `Recraft` (`https://mcp.recraft.ai/mcp`, sign in with OAuth) and `Replicate` (`https://mcp.replicate.com/sse`, paste an API token).
3. Add `img.recraft.ai`, `replicate.delivery` and `*.replicate.delivery` to the network allowlist in Claude's settings, so outputs can be saved into jobs.
4. For Claude Code: `claude mcp add --transport http recraft https://mcp.recraft.ai/mcp --scope user` and `claude mcp add --transport sse replicate https://mcp.replicate.com/sse --scope user`, then `/mcp` to authenticate. `tools/mcp.example.json` has the same as a project config.

## Development

```
python3 -m pytest tests -q     # 159 tests
tools/package.sh               # runs the tests, builds dist/creative-studio.plugin
```

## Layout

```
.claude-plugin/plugin.json
agents/
  art-director.md  builder.md  copywriter.md  creative-lead.md
  delivery.md  identity-designer.md  strategist.md
hooks/hooks.json
skills/
  producer/            SKILL.md, scripts/studio.py, assets/templates/{brief,scope,gate-pack,commission,validation}.md
  studio-intake/       SKILL.md
  studio-gate/         SKILL.md
  studio-close/        SKILL.md
  studio-status/       SKILL.md
  commission/          SKILL.md
  studio-standards/    SKILL.md, references/{anti-generic,art-sources}.md
  brand-vault/         SKILL.md, scripts/vault.py, assets/tokens.template.json
  image-generation/    SKILL.md, references/, scripts/imagekit.py
  blender-3d/          SKILL.md, scripts/blenderkit.py
tests/
tools/package.sh, tools/mcp.example.json
```
