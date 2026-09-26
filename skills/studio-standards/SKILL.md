---
name: studio-standards
description: >
  This skill should be used before making or reviewing any creative studio work: strategy, territories,
  marks, tokens, copy, pages, decks, screens, imagery or motion. It holds the studio's operating rules,
  the anti-generic list, craft and copy standards, the reference and originality rules, and file
  conventions. Every studio agent and every panel lens loads it. Also use it when Tim asks to "check this
  against the studio standards", "is this generic" or "does this meet the bar".
metadata:
  version: "0.3.7"
---

# Studio standards

The bar is a studio a client hires because its in-house work is competent but indistinguishable. Every rule below exists to protect distinctiveness, craft or the client's ownership.

## Operating rules

1. **Brief before pixels.** No design work until the brief gate is approved. A commission's brief can be approved on the requester's side.
2. **Diverge, then converge.** Territories are three different strategic bets, each with its own idea, not three colourways of one idea. If two territories could share a logo, they are one territory.
3. **Reach on at least one.** One of the three territories is a **reach**: it draws explicitly on art practice — depth, colour, texture, atypical shape and form — from `references/art-sources.md`, and it still answers the positioning. A reach that does not answer the positioning is not a reach, it is a different job. **Three territories inside one narrow band of restraint is a Major finding: timidity.** It lands on the Creative Lead, and from 0.4.0 the panel's Creative lens looks for it. Restraint is a strategy when it is argued and a default when it is not.
4. **Tokens, not values.** Every colour, font, size, space, radius and motion value comes from the brand vault. The vault lint flags literal values in deliverables.
5. **Render before review.** Work is judged as rendered output in context (on a phone, on a dark background, at 16px, on a billboard), never as source.
6. **One owner per file.** Others propose; the owner edits.
7. **Declared departures.** A territory may break a rule here, including the anti-generic list, only if the board names the rule and argues why breaking it serves the idea.
8. **Client isolation.** Nothing crosses between clients: no reused concepts, styles, names or references from another job.
9. **Human at every gate.** Nothing client-facing leaves without Tim's approval.
10. **Cross-read at every gate.** One role checks another's completeness claim against the commissioning document, never its own. Recorded with `studio.py cross-read <gate> --by <role> --of <role> --against <document>`, and `studio.py check <gate>` will not pass without it. This is not a request to be more careful: three roles made the same sourcing mistake on one job and not one caught it in their own work, so the fix is that somebody else reads the claim, which is cheaper precisely because it does not require anyone to be more careful.
11. **Name the question, then name the source that governs it.** *What must exist* is the commissioning document (`02-scope.md`, the commission brief). *What does exist* is the artefact itself. *What this claim means* is the owner, or the client's own words. Completeness and content need **different sources**, and anything asserting both needs both. A gate pack, a stage README and a guidelines document each say *this is complete* and *this says X* in one breath, which is exactly where three failures sat, each author having verified only one half. And where a document describes a set of files, values or strings, **generate it from them and fail the build** when a described thing is missing or an existing thing is undescribed: three documents turned into generators each found a real defect on their first run, and none of the three defects had been found by a person reading the same file.
12. **Checking stops when a pass finds nothing, not when the budget runs out.** Every stage's verification gets a budget of full passes per track (`studio.py verify-pass`), and going beyond it is a stated decision rather than a habit. Checking closes on the Producer's explicit call, recorded in `90-decisions.md` with why (`studio.py verify-close ... --call "..."`), and it may only close on a pass that found nothing that would ship wrong. A verification nobody closed is not thoroughness; it is a job with no end condition.

## Anti-generic list

`references/art-sources.md` is where to reach when the work is going polite: art practice as principles, and five studios whose work sets the bar — bold and systemic at once. Principles are cited and linked on the board. Nothing is copied, nothing is named in a generation prompt, and no territory is pitched as "like Studio X".

**Timidity has a failing test, and it is a script rather than a judgement.** `scripts/treatment-check.py <board> <board> <board>` reads the three territory boards' own rendered values and compares them on seven treatment dimensions: ground, ink, chroma, radius, gradient, shadow and texture. **Three boards agreeing on five of the seven is a finding the Creative Lead must argue on the board**, not a fail. The reason it is a script is that the author's own claim that a reach is load-bearing is the least reliable evidence available: on the job this came from, all three boards diverged completely on subject and agreed on seven of seven treatments, passing rule 2 while failing rule 3, and nobody noticed until after handover.

`references/anti-generic.md` lists the visual and verbal defaults the studio does not ship unless a declared departure argues for them. Check work against it before any gate. The panel's Creative and Craft lenses use it from 0.4.0; until then the Creative Lead and the Producer check against it before every gate.

## When 3D is allowed

3D is the studio's most expensive material and the easiest to reach for. Abstract 3D blobs on gradients are on the anti-generic list for a reason: most 3D in brand work exists because it was available, not because the idea needed space.

**A job may use 3D for one of three reasons, and no others:**

1. **A physical touchpoint.** The brand exists on an object in the world: a van, a sign, a uniform, packaging, a stand, a building. 3D is how the studio sees it before the client pays a signwriter.
2. **A spatial territory idea, argued on the board.** The territory's idea is itself about depth, material, object or space, and the Creative Lead has argued it in the board's Dimension section. A territory that is flat with a 3D decoration is not this.
3. **Explanation that needs space.** Something true about the product cannot be shown flat: an assembly, a mechanism, a site, a route.

**Anything else is a declared departure and needs the board to argue it.** "It would look good in 3D" is not an argument, and neither is "the deck needs a hero".

**How it runs through the job:**

| Stage | Who | What |
|---|---|---|
| strategy | Strategist | A touchpoint inventory in `10-strategy/`: every place this brand physically exists, or will. It decides whether reason 1 is live before anyone designs. |
| territories | Creative Lead | A **Dimension** section on every board: flat, or 3D and which of the three reasons, or a declared departure. Three territories may reach three different answers. |
| direction gate | Producer | The pack states the 3D plan: what will be made in 3D, why, and what it costs. Tim approves the plan, not just the territory. |
| identity | Identity designer | Blender mockup tests for every physical touchpoint the inventory names, at real viewing distances. A mark that works at 512px on a screen and fails at 25 metres on a van is the identity stage's problem, not the client's. |
| applications | Builder, Art Director | Build only the 3D the direction gate approved. New 3D at this stage is a change request. |

The `blender-3d` skill does the making. Renders are judged at the distance the object is actually seen from, never at 100% on a monitor.

## The expression budget

Expression is not spread evenly across a brand. The brief says where it lives and where it does not, and every role works to that line.

| | Expression lives here | Expression stays out |
|---|---|---|
| Typical surfaces | Covers, heroes, campaigns, packaging, environments, launch moments | Forms, tables, data, body copy, settings, error states |

**The default dial, which Tim adjusts per job:**

- **Start-ups: bold throughout.** They are fighting to be noticed and have no legacy to protect. A calm working surface on a start-up brand usually means nobody decided what it should be.
- **Corporates: bold in brand moments, calm in working surfaces.** The report, the form and the table are where the organisation's competence is judged, and the campaign is where its character is.

The brief records the dial and names the surfaces on both sides of the line, so the Builder and the Identity designer are not guessing, and so "make it pop" and "tone it down" arrive as a decision rather than as taste. **The line is never drawn through accessibility**: every contrast rule holds on both sides of it, and expression never buys itself a readability exemption.

## Craft standards

- **Hierarchy**: one dominant element per view. If everything is emphasised, nothing is.
- **Type**: a modular scale from the vault. At most two families plus a mono. Body text 16px or larger on screen, with a line length of 45 to 80 characters. Real quotes and apostrophes, proper dashes in ranges, no faux bold or italic.
- **Layout**: an explicit grid. Spacing only from the space scale. Optical alignment beats mathematical alignment where they disagree (round forms overshoot, icons sit optically centred).
- **Colour**: text pairs pass WCAG AA (the vault enforces body text on the default surface). Accent colours carry meaning, not decoration.
- **Marks**: test at 16px, 32px and 512px, in one colour, reversed, and on photography. A mark that needs its detail to work at small sizes needs a simplified version.
- **Motion**: purposeful, 120 to 360ms from the vault's motion tokens, and reduced-motion variants always.
- **Accessibility**: WCAG 2.1 AA as the floor for anything on screen: contrast, focus states, alt text, touch targets of 44px or more.

## Copy standards

- The client's voice (from the tone-of-voice work) governs client-facing copy. Studio defaults apply until that exists.
- Default spelling follows the client's market. Tim's own messages use British spelling.
- Specific over impressive: name the customer, the number, the outcome. Cut any sentence the client's competitor could also say.
- Run the `humanizer` skill over long copy before review.
- No claims the client cannot evidence. Superlatives ("the leading", "the first") need a source or they go.
- **A negation is still a claim.** "Not retained beyond the day" asserts deletion exactly as much as "kept for seven years" asserts keeping, and about a product nobody has described both are unevidenced. The test is mechanical: **turn the negation into its positive and ask whether the client could stand behind it.** The distinction that makes it checkable is scope: a negation about *what we claim* needs no evidence ("we make no claim about how long a log is kept"); a negation about *what the software does* is a claim. A claim ceilings table whose rows all guard positive forms lets every negation through, so each row carries a Never/Permitted pairing and the sold-as versus does distinction.
- **Apply the negation test hardest where the register is warmest.** The friendlier the writing, the less a negation looks like a claim: one assertion appeared twice on the same job, and the version in the buyer's own vocabulary survived two further passes purely because it sounded like something a real operations director would say. *Write it the way they would say it* is the principle most likely to hide a breach of *claim nothing you cannot evidence*.
- **Which shape a ceiling takes depends on who handles the copy next.** A stranger's editor deletes negations first: they read as caveats and are the first thing cut for length. Copy that will be pasted and trimmed by someone outside the studio, boilerplate above all, carries its ceiling as a positive rather than as a denial.

## References and originality

- References are described and linked in boards. They are never traced, and they are never fed to a generator as something to imitate.
- No living artist's name, brand, trademark, character or real person in any generation prompt (see the `image-generation` skill).
- Every selected mark, name and key visual gets an originality check before the system gate: the Identity designer reverse image searches marks in `30-identity/originality.md`, and the Copywriter runs web and trademark-register searches on names in `naming.md`. Record what was checked. Screening is not clearance; counsel clears names and marks.
- Final marks are human-directed throughout. An agent constructs and prepares the master; the pass that makes it final is made by a named human, and `30-identity/refinement-log.md` records who did what, and why, version by version. `studio.py check system` will not pass without an entry naming a person, and a name written there for a pass that did not happen is a fabrication, not a formality.

## Files

- Name deliverables `<job>-<deliverable>-v<n>.<ext>`. Never overwrite a version that has been to a gate; increment it.
- Every stage folder has a `README.md` listing what is in it, one line per file.
- Keep working files and client-ready files apart: client-ready work goes in `<stage>/client/`.
