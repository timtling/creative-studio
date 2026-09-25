# Changelog

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
