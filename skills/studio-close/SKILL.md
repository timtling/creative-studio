---
name: studio-close
description: >
  This skill should be used when a creative studio job is finished or being stopped: "/studio-close",
  "close the job", "write up the job", "what did we learn on [codename]", "turn this job into evals",
  or after the final gate once Delivery has packaged the work. It turns a finished job into three
  things the studio keeps: the intervention log (every time a human had to step in), the fix list
  (what to change in the studio itself), and eval cases drawn from the job's own record. It does not
  apply to NTT DATA consulting engagements.
metadata:
  version: "0.3.7"
---

# Studio close

A finished job is evidence about the studio, and it is the only evidence that does not come from asking the studio about itself. Close every job this way, including the ones that went well: a job with no interventions is the finding, not the absence of one.

Load the `producer` skill first. `<studio>` below is its `scripts/` folder. Read `90-decisions.md` end to end before anything else; it is the job's memory and the source for all three outputs. Then read the gate packs in `gates/` and Tim's replies recorded against them.

Write everything into `95-close/` in the job folder.

## 1. The intervention log

`95-close/interventions.md`. One row per time a human changed the outcome, in order.

| Column | What goes in it |
|---|---|
| When | Date and stage |
| What happened | One sentence, factual |
| Who caught it | Tim, a role, or the tooling |
| What it cost | Rework, a delayed gate, a changed deliverable, or nothing |
| Would the studio have caught it alone? | Yes, no, or not for N stages |

Count three things separately, because they mean different things:

- **Tim's decisions**, which are the system working. A gate reply is not an intervention.
- **Tim's corrections**, where he changed work the studio had produced and was content with. These are the real measure.
- **Role-to-role catches**, where one agent caught another. These are what the ownership rules are for, and they are the studio's own immune system.

## 2. The fix list

`95-close/fixes.md`. What to change in the studio, not in the job. One entry each: what went wrong, the root cause, the change, and where it lands (a skill, an agent file, a script, or the standards). Rank by how likely the failure is to repeat and how expensive it is when it does.

Three tests before an entry earns its place:

1. **Would the change have prevented this, specifically?** Not "improved things generally".
2. **Is it enforceable?** A rule nobody can check is a wish. Prefer a script check, then a gate readiness condition, then a written rule, in that order.
3. **What does it cost when it fires wrongly?** A check that blocks good work gets disabled within a month.

Ship the fixes as their own versions, with the job named in the changelog entry. A fix that cannot be traced back to the job that caused it will be argued about later.

## 3. Eval cases

`95-close/evals/`. The job's record contains the studio's own failures, already diagnosed. Turn them into cases that would fail before the fix and pass after it.

Draw from three seams in `90-decisions.md`:

- **Corrections**: anything the record shows was wrong and then right. The wrong version is the input; the corrected one is the expected output.
- **Refusals**: every time a role declined to do something (write a claim, log a pass, use a word). These are the most valuable cases, because the failure mode they protect against is silent.
- **Gate replies**: Tim's own words are the ground truth for what the studio should have produced. "approve with: ..." names the gap directly.

Each case is one file: the situation, the input the agent would see, what a failing response looks like, what a passing one looks like, and which fix it tests. Write what fails, not just what passes; a case that only describes success cannot tell you when you have regressed.

## Closing

Report to Tim with the three counts (decisions, corrections, role-to-role catches), the top three fixes with their cost, and how many eval cases the job produced.

Then close the record in order: `studio.py verify-close <key> --call "<why checking is done>"` if any verification is still open, and then `studio.py set-active <folder> no`, which will refuse while a verification has passes and no closing call. **A job with no end condition on its checking is not a thorough job, it is an unfinished one**, and the call belongs to the Producer, in the log, under a name.

**Do not write a case, a fix or a log line for something that did not happen.** This skill exists to make the studio honest about itself, and a flattering close is worse than none.
