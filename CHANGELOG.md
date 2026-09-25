# Changelog

## 0.3.5 (25 Sep 2026)

3D gets a reason before it gets a renderer, and the effect check stops passing quietly.

- **The 3D decision rule** in `studio-standards`. A job may use 3D for a physical touchpoint, a spatial territory idea argued on the board, or explanation that needs space. Anything else is a declared departure, because "it would look good in 3D" is not an argument and abstract 3D blobs on gradients are already on the anti-generic list. It runs through the job rather than sitting in a document: the Strategist writes a touchpoint inventory in `10-strategy/touchpoints.md`, every territory board carries a **Dimension** section naming its answer or declaring a departure, the direction gate pack states the plan and Tim approves it, the Identity designer runs Blender mockups for every physical touchpoint at real viewing distances, and the Builder and Art Director build only what was approved.
- **`blender-3d` skill and `blenderkit.py`.** Scenes take their material colours from `vault/build/blender.json` and the view transform is forced to Standard, because Blender's default desaturates every brand colour and nobody can say why the renders drifted. Draft and final presets, headless from the command line, `--distances` so an object is judged at the distance it is actually seen from. Every render writes a sidecar recording the scene, preset, samples, view transform, the vault build it drew from and the command, because a render nobody can reproduce is a screenshot. `verify` reads that sidecar back and refuses a render made under the wrong view transform.
- **"Effect not verified" is now visible.** Where the refinement effect check has no SVG renderer it used to return nothing, which reads as a pass. It now raises a warning that never blocks the gate and is written into the pack above the risks, saying plainly that a person is named and that the pass was **not** checked for having changed anything.
- 125 tests.

## 0.3.4 (25 Sep 2026)

Mandatory intake validation, before a word of the brief is drafted.

- An eleven-item checklist, each marked `supplied`, `inferred` or `missing`: client and decision-maker, what they are buying, the date and what it is tied to, audience, existing brand, budget band, competitors as the client named them, physical touchpoints, platform and who maintains it, confidentiality, success measure. An inference is confirmed with Tim, never promoted to a fact by being written into the brief.
- At least three questions to Tim in one round of three or four, through `AskUserQuestion`, ordered by impact on track, scope, price and date, recommended option first, confirming the inferred rows rather than re-asking the supplied ones. A second round only for gaps that still block the track, the price or the date. Plain numbered questions where `AskUserQuestion` is unavailable.
- Items only the client can answer go to a drafted client email and into the brief's open questions, rather than being put to Tim.
- `studio.py init` writes `00-intake/validation.md` from a template, so the file exists from the first minute and is filled as intake happens. `studio.py check brief` refuses to raise without it, with unfilled prompts in it, or with fewer than three answered questions, and placeholders, "unanswered" and "TBC" do not count as answers.
- Competitors stay client-named in the checklist, the template and the skill, matching 0.3.1.
- 105 tests.

## 0.3.3 (25 Sep 2026)

Everything in this release came out of the studio's first job.

- `builder`: owns `50-applications/` and `50-make/`. Tokens only, never literal values; renders at phone and desktop width and judges the screenshots rather than the markup; never changes the identity to make a build easier, and never puts a mark or name into a deliverable the job's record says is unresolved.
- `delivery`: owns `99-handover/` and `99-return/`. Export matrix, asset index, tokens package and licence notes, packaged against `02-scope.md` line by line rather than against the folder. Opens every file it ships, never fixes a defect quietly, and ships nothing the record shows is unresolved.
- `studio-close` skill: turns a finished job into an intervention log, a fix list and eval cases drawn from `90-decisions.md` and Tim's gate replies. It counts Tim's decisions, Tim's corrections and role-to-role catches separately, because they mean different things, and it forbids writing a case for something that did not happen.
- **The refinement effect check.** A person-attributed version that renders identically to the one before it is now refused at the system gate. Found on Cypress: a hand file saved from a real editor, logged in good faith, with the change absent. Attribution without effect is not evidence. Renders through whichever of rsvg-convert, inkscape or cairosvg is present and compares decoded pixels with a standard-library PNG decoder; on a machine with no renderer it checks attribution and stays silent rather than blocking work it cannot assess.
- The Producer labels every figure an agent reports as reported until it has checked it. On the first job a contrast ratio, a small-size type table and a customer statistic all travelled upward unverified, and one reached Tim as fact.
- 96 tests.

## 0.3.2 (25 Sep 2026)

- The system gate's named-human check no longer accepts a placeholder or a role. It matched any text after `refined by:`, so `<name or role>`, `[Name]`, `TODO` and `the identity designer` all satisfied the check that exists to protect the client's rights in the mark. Found by the Identity designer on the first job to reach the identity stage: its own draft log contained a format example, the gate passed on it, and it reported the hole rather than working around it. Names are now normalised (parentheticals and punctuation dropped) and tested against placeholder syntax, placeholder words and every studio role, and the failure message quotes what it found. Two-letter given names still pass.

## 0.3.1 (25 Sep 2026)

- Intake lists only the competitors the client named, in the client's words, marked unverified, and leaves the competitive landscape to the Strategist. Found on the first sprint: the Producer assembled a plausible set at intake, it was wrong in four ways, and it was inherited as fact until the Strategist verified it against live pages two stages later. The same rule now covers anything else the Producer might supply on the client's behalf: the market's shape, what the category says, who the real incumbent is. Those are strategy findings, not intake ones.

## 0.3.0 (25 Sep 2026)

The four creative roles. A brand sprint now has someone to do every stage of it.

- `strategist`: owns `10-strategy/`. Tests the brief's working proposition against a rival reading rather than adopting it, applies the competitor-swap test to its own positioning, and hands the Creative Lead the constraints the territories have to answer. Evidence is sourced, attributed or flagged; never manufactured.
- `creative-lead`: owns `20-territories/`. Three different bets, each with a board that names its idea, what it gives up, its declared departures from the anti-generic list, its references and how it would fail. Boards are rendered and read on a phone before review. Literal colour values are allowed in territory boards, and only there, because the vault does not exist until the identity stage.
- `copywriter`: owns `voice.md`, `naming.md` and every `*-copy.md`, wherever they sit, the one role that owns files rather than a folder. Voice before lines, the competitor-swap test on every line, copy judged in place at real length, and name screening recorded.
- `identity-designer`: owns `30-identity/` and `vault/`. Marks tested at 16px, 32px and 512px, in one colour, reversed and on photography before discussion. Builds and validates the vault, and hands `swatches.html` to the Producer rather than publishing it. No generated image is ever a final mark: the agent constructs and prepares the master, and the pass that makes it final is made by a named human. `30-identity/refinement-log.md` records it, and `studio.py check system` will not pass without an entry naming a person. `originality.md` covers marks only; names are screened by the Copywriter, on every job.
- Vault lint and hook skip `20-territories/` and `30-identity/exploration/`. Both are pre-vault by design, and a lint that cries wolf there is one everyone learns to ignore.
- Producer roster names the agent to launch for each role, and how to brief one. The panel and the control room move to 0.4.0.
- 63 tests.

## 0.2.1 (25 Sep 2026)

- Jobs live on the Mac mini at `~/Studio/jobs` by default. The Producer says so at intake when the Mac mini cannot be reached, and never leaves a job living only in a cloud session.

## 0.2.0 (25 Sep 2026)

The Producer, the standards and the brand vault. The studio stands on its own; the engagement studio is one of its requesters.

- Producer operating model: five tracks (sprint, launch-kit, product-ui, programme, commission), roster and file ownership, gates, client feedback triage, commissions, where jobs live, output catalogue.
- `studio.py`: job set-up per track, forward planning with buffer against the client date, gate readiness checks, gate decisions with Tim's words logged, client revision rounds against the allowance, feedback classes, change requests, status.
- Stage skills: `studio-intake`, `studio-gate`, `studio-status`, `commission`. Named so they do not trigger on engagement studio work.
- Templates: creative brief, scope of work (draft statement of work with ownership, licensing and AI-use terms), phone-readable gate pack, commission brief.
- `studio-standards`: operating rules, craft and copy standards, references and originality, file conventions, and the anti-generic list.
- Brand vault: W3C design token template, `vault.py` validate (structure, values, aliases, cycles, WCAG AA on body text), build (CSS custom properties, flat JSON, linear colours for Blender, a tokens page), contrast matrix and lint. A hook reports literal colours written into job files.
- Art Director loads the standards and the vault, and works under external brands on commissions.
- 37 tests.

## 0.1.0 (25 Sep 2026)

The imagery layer.

- Art Director agent: art direction and shot list before generation, per-client Recraft styles, rounds of explore, select, refine and finalise, and ownership of the ledger and contact sheet.
- image-generation skill: job set-up, workflow, model routing, prompt recipe, and licensing and confidentiality rules for Recraft and Replicate.
- `imagekit.py`: job file, provenance ledger, capture of URL and inline outputs, fetch before Replicate's one-hour expiry, call and US$ budget, contact sheet, provenance report.
- Hooks: deny spend without a confirmed Recraft paid plan, without a commercially cleared Replicate model, past budget, or with more than one active job. Log and capture after every call.
- 16 tests.
