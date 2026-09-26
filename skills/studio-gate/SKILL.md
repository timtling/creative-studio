---
name: studio-gate
description: >
  This skill should be used for creative studio sign-offs: "/studio-gate", "send me the studio gate pack",
  or any reply from Tim to a pending studio gate (brief, direction, system, governance, final) such as
  "approve", "approve with: ...", "rework: ...", or comments on a territory, mark or page. It composes the
  phone-readable gate pack, records Tim's decision, turns his changes into instructions for the owning
  roles, and starts the next stage. Engagement studio gates (A, B, C) use the engagement studio instead.
metadata:
  version: "0.3.7"
---

# Studio gate

Load the `producer` skill first. `<studio>` below is its `scripts/` folder.

## Raising a gate

1. **Record the cross-read first**: `python3 <studio>/studio.py cross-read <gate> --by <role> --of <role> --against <document>`. One role reads another's completeness claim against the document that commissions it, and never its own. The gate does not pass without it, except at the brief gate.
2. **At the final gate, the scope audit comes before the pack.** `studio.py scope-audit` regenerates `gates/scope-audit.md` from `02-scope.md`, one line per promise. Delivery answers every line; you cross-read it. Nothing about this can be written from what the roles reported: that is exactly how a bought deliverable that did not exist at all reached Tim with an `approve` on it.
3. `python3 <studio>/studio.py check <gate>`. Fix what it reports, or ask the owning role to fix it. Use `gate raise --force` only when Tim has asked to see the work as it stands, and say so in the pack.
4. `python3 <studio>/studio.py gate raise <gate>` writes the pack scaffold to `gates/<gate>.md`, with the final gate's `## Scope` table generated from the audit.
5. Fill the pack. It is read on a phone, so keep everything before the links to one screen:
   - **Decision needed**: one sentence.
   - **Recommendation**: the team's view and why, naming the option.
   - **What is in the pack**: links to artifacts (boards, the vault page, contact sheets, prototypes), one line each.
   - **Panel**: the verdict and anything escalated. Until the panel exists (0.4.0), say the review was the Producer's only.
   - **Scope** (final gate): generated from the audit. Do not rewrite it from memory and do not soften a `short` row into a risk line.
   - **Transplant** (direction gate): one line naming whether a mechanism from a territory you are *not* recommending should be carried into the one you are. A board that loses can still be right about one thing, and if nobody asks at the gate the answer is lost with the board.
   - **Trade-offs and risks**: what this choice gives up.
   - **Questions**: at most three.
6. Send Tim the pack, as a message with the links. Publish visual work as artifacts so it opens on his phone.

What each gate decides:

| Gate | Tim decides |
|---|---|
| brief | The brief, scope, plan and fee are right to send to the client |
| direction | Which territory (or flow direction) goes forward, what to change in it, whether a losing territory's mechanism is transplanted into the winner, any declared departure in **any** of the three (a departure needs a ruling even in a territory he does not choose), and the 3D plan |
| system | The identity system or screen system is right: marks, tokens, type, key applications |
| governance | Rules, templates and roll-out for a corporate programme |
| final | Everything in scope is ready for the client and for handover, read off the scope audit rather than off what the roles reported |

## Recording Tim's reply

- "approve": `studio.py gate record <gate> --status approved`
- "approve with: ...": `--status approved-with --note "<his words>"`, then turn each change into an instruction for the owning role and track it to done before the client sees the work.
- "rework: ...": `--status rework --note "<his words>"`. Route the rework to the owners, then raise the gate again.
- Comments on specific items ("T2: the mark is too heavy") are "approve with" or "rework" depending on whether he approved. If that is unclear, ask him in one line.

Record his words verbatim in the note. `90-decisions.md` is the job's memory: the next session reads it before anything else.

## After approval

Say what starts next, who owns it and when the next gate is due (from `03-plan.md`). Then start it: launch the owning agent from the roster (`strategist`, `creative-lead`, `copywriter`, `identity-designer`, `art-director`) with the job folder, the files it needs and the gate it is working towards. If the owning role is not built yet, say which one is missing rather than doing its work in your own voice. For client-facing gates, prepare the client version of the work: same content, the studio's presentation, no internal notes, no panel findings.
