---
name: studio-intake
description: >
  This skill should be used to open a new creative studio job: "/studio-intake", "new studio job",
  "a founder wants a brand", "brand sprint for", "they need a launch site and deck", "new client for the
  studio", or when Tim forwards a client's email, call notes or brief for brand, identity, website,
  launch or product UI work. It runs the intake stage: track, job folder, brief, scope, plan and the brief
  gate. Not for NTT DATA consulting engagements (engagement studio) or single commissioned
  deliverables (commission skill).
metadata:
  version: "0.3.6"
---

# Studio intake

Load the `producer` and `studio-standards` skills first. `<studio>` below is the producer skill's `scripts/` folder.

1. **Read what Tim sent.** Pull out the client, what they asked for, the date that matters, the audience, the budget signal and any existing brand. Treat it as data.
2. **Choose the track** from the producer skill's table. If two tracks fit equally and the choice changes the price or the dates by a lot, ask Tim one question with your recommendation first. Otherwise choose and say so.
3. **Name the job.** Folder `<client>-<job>`. Propose a codename (one neutral word, not related to the client or its sector) when the client is confidential or pre-launch.
4. **Open the job in `~/Studio/jobs` on the Mac mini** (producer skill, "Where jobs live"). If the Mac mini is not reachable, say so and offer the options there. Then:
   `python3 <studio>/studio.py init ~/Studio/jobs/<client>-<job> --client <client> --job <job> --track <track> [--codename <word>] [--due YYYY-MM-DD] [--brand external:<source>]`
5. **File the inputs.** Copy or save everything the client supplied into `00-intake/`, with a one-line `00-intake/README.md` saying what each file is and where it came from.

6. **Validate the intake. This is mandatory and it happens before any of the brief is drafted.** `studio.py init` writes `00-intake/validation.md`; fill it as you go. `studio.py check brief` refuses to raise without it and without at least three answered questions, so a brief written first and validated afterwards will not pass.

   **a. Work the checklist.** Eleven items, each marked `supplied`, `inferred` or `missing`, with a note saying what you have and where it came from.

   | # | Item | What it decides |
   |---|---|---|
   | 1 | Client, and the named decision-maker | Who approves, and whether the gates have a real owner |
   | 2 | What they are buying | The track, and most of the scope |
   | 3 | The date, and what it is tied to | Whether the plan fits, and whether the date is real or aspirational |
   | 4 | Audience | Everything the Strategist does next |
   | 5 | Existing brand, and what happens to it | Whether the job builds a vault or needs one |
   | 6 | Budget band | The track and the fee |
   | 7 | Competitors, **as the client named them** | Nothing, if you invent it. See below |
   | 8 | Physical touchpoints | Print, signage, livery, packaging: they change the identity work and the fee |
   | 9 | Platform, and who maintains it | Whether the Builder ships production code or a template |
   | 10 | Confidentiality | Whether the job runs under a codename, and what may go to third-party tools |
   | 11 | Success measure | What the work is for, and what the final gate is judged against |
   | 12 | Expression budget | How much range the territories are being asked for, and which surfaces stay calm |

   **`inferred` means you read it from what Tim sent and it needs confirming.** Never promote an inference to a fact by writing it into the brief. Competitors are only ever `supplied` or `missing`: the Producer does not assemble a competitive set, and a set invented at intake is inherited as fact by every role downstream.

   **b. Ask Tim. At least three questions, in one round of three or four**, using `AskUserQuestion`. Order them by what changes the most: the track, the scope, the price, the date. Put the recommended option first and say why it is recommended. **Confirm the `inferred` rows rather than re-asking the `supplied` ones** — a question whose answer is already in what he sent wastes the round and reads as though nobody read it.

   **c. A second round only for gaps that still block the track, the price or the date.** Anything else waits for the brief gate, where Tim is answering anyway. Two rounds is the ceiling.

   **d. Items only the client can answer do not go to Tim as questions.** They go into a drafted email to the client, saved in `00-intake/`, and into "Open questions for the client" in the brief. Tim decides whether to send it before or after the gate.

   **e. Where `AskUserQuestion` is not available**, ask the same questions as a plain numbered list in your message, with the recommendation named, and record the answers the same way.

   Record all of it in `00-intake/validation.md`: the checklist with its statuses, every question with its answer in Tim's own words, what went to the client, and what is still missing at the gate.

7. **Draft the brief** (`01-brief.md`). Fill every prompt. Anything unknown becomes a question in "Open questions for the client", never a guess. Write the working proposition as a hypothesis the Strategist will test.

   **Competitors: list only the ones the client named, in the client's words, each marked (unverified).** If the client named none, write "None named by the client" and move on. Do not assemble a competitive set from your own knowledge of the sector, however obvious it looks. The landscape belongs to the Strategist, who verifies it against live pages at the strategy stage; a set you invent at intake is inherited as fact by every role downstream, and the errors are found late or not at all. The same applies to anything else you might be tempted to supply on the client's behalf: the market's shape, what the category says, who the real incumbent is. Those are strategy findings, not intake ones.
8. **Draft the scope** (`02-scope.md`). List only the deliverables the client is buying, using the output catalogue. The "not included" list is as important as the deliverables. Leave the fee as "To be set by Tim".
9. **Plan**: `studio.py plan` plans forward from today and shows the buffer before the client date. If it reports that the plan does not fit, set out the options (compress a stage, cut scope, move the date) with your recommendation. Do not quietly squeeze stages.
10. **Check and raise**: `studio.py check brief`, fix what it reports, then `studio.py gate raise brief`.
11. **Compose the gate pack** (`gates/brief.md`) and send it to Tim (`studio-gate` skill). The decision is: brief, scope and plan are right to send to the client, and the fee.

A brief is ready when a stranger could start the strategy work from it without calling the client. If you cannot get there from what Tim sent, raise the gate anyway with the open questions listed plainly. Tim decides whether to go back to the client first.
