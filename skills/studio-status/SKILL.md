---
name: studio-status
description: >
  This skill should be used when Tim asks where a creative studio job stands: "/studio-status",
  "where are we on <codename>" for a studio job, "what's pending in the studio", "what's next on the
  brand sprint", or when a new session needs to pick up a studio job started elsewhere. It reports the
  stage, the pending gate, days to the client date, revision rounds, open change requests and the next
  action. Engagement studio status uses the engagement studio instead.
metadata:
  version: "0.2.0"
---

# Studio status

Load the `producer` skill first. `<studio>` below is its `scripts/` folder.

1. **Find the job.** Look in the working folder, then the studio jobs folder on Tim's linked computer. If there are several jobs and he named none, list the active ones (codename, track, stage) and ask which one.
2. **Read before reporting**: `studio-job.json`, `90-decisions.md`, the last few lines of `90-feedback.jsonl`, and any pending `gates/*.md`.
3. Run `python3 <studio>/studio.py status --job <folder>`.
4. **Report in four lines or fewer**: where it is, what is waiting on Tim, what is at risk (date, scope, open change requests, an exhausted revision allowance), and the next action with its owner. For "all jobs", give one line per active job.
5. If the job folder cannot be found, say so plainly and ask where it was kept. Never recreate a job from memory.
