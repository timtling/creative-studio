---
name: studio-standards
description: >
  This skill should be used before making or reviewing any creative studio work: strategy, territories,
  marks, tokens, copy, pages, decks, screens, imagery or motion. It holds the studio's operating rules,
  the anti-generic list, craft and copy standards, the reference and originality rules, and file
  conventions. Every studio agent and every panel lens loads it. Also use it when Tim asks to "check this
  against the studio standards", "is this generic" or "does this meet the bar".
metadata:
  version: "0.3.0"
---

# Studio standards

The bar is a studio a client hires because its in-house work is competent but indistinguishable. Every rule below exists to protect distinctiveness, craft or the client's ownership.

## Operating rules

1. **Brief before pixels.** No design work until the brief gate is approved. A commission's brief can be approved on the requester's side.
2. **Diverge, then converge.** Territories are three different strategic bets, each with its own idea, not three colourways of one idea. If two territories could share a logo, they are one territory.
3. **Tokens, not values.** Every colour, font, size, space, radius and motion value comes from the brand vault. The vault lint flags literal values in deliverables.
4. **Render before review.** Work is judged as rendered output in context (on a phone, on a dark background, at 16px, on a billboard), never as source.
5. **One owner per file.** Others propose; the owner edits.
6. **Declared departures.** A territory may break a rule here, including the anti-generic list, only if the board names the rule and argues why breaking it serves the idea.
7. **Client isolation.** Nothing crosses between clients: no reused concepts, styles, names or references from another job.
8. **Human at every gate.** Nothing client-facing leaves without Tim's approval.

## Anti-generic list

`references/anti-generic.md` lists the visual and verbal defaults the studio does not ship unless a declared departure argues for them. Check work against it before any gate. The panel's Creative and Craft lenses use it from 0.4.0; until then the Creative Lead and the Producer check against it before every gate.

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

## References and originality

- References are described and linked in boards. They are never traced, and they are never fed to a generator as something to imitate.
- No living artist's name, brand, trademark, character or real person in any generation prompt (see the `image-generation` skill).
- Every selected mark, name and key visual gets an originality check before the system gate: the Identity designer reverse image searches marks in `30-identity/originality.md`, and the Copywriter runs web and trademark-register searches on names in `naming.md`. Record what was checked. Screening is not clearance; counsel clears names and marks.
- Final marks are human-directed throughout. An agent constructs and prepares the master; the pass that makes it final is made by a named human, and `30-identity/refinement-log.md` records who did what, and why, version by version. `studio.py check system` will not pass without an entry naming a person, and a name written there for a pass that did not happen is a fabrication, not a formality.

## Files

- Name deliverables `<job>-<deliverable>-v<n>.<ext>`. Never overwrite a version that has been to a gate; increment it.
- Every stage folder has a `README.md` listing what is in it, one line per file.
- Keep working files and client-ready files apart: client-ready work goes in `<stage>/client/`.
