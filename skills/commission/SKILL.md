---
name: commission
description: >
  This skill should be used when another team or tool asks the creative studio for a single deliverable:
  "/commission", "commission the studio", "ask the creative studio for a key visual / icon set / 3D hero /
  landing section", or when the engagement studio's Design Director needs a visual it should not make
  itself. It opens a commission job with the requester's brief, makes and reviews the one deliverable, and
  returns it in the requested format with provenance.
metadata:
  version: "0.2.0"
---

# Commission

A commission is one deliverable for someone else's project. The requester owns the context; the studio owns the craft. Load `producer` and `studio-standards` first. `<studio>` below is the producer skill's `scripts/` folder.

## What a requester sends

Ask for whatever is missing, in one message:

- the deliverable, one item per commission
- where it will be used, and the size, format and background it must fit
- the brand source and how much latitude the studio has
- audience and the one message it must carry
- inputs (copy, data, references), the due date, and the acceptance criteria
- the return format and location, and any confidentiality rules

From the engagement studio, the brand is usually the NTT DATA identity: `--brand external:ntt-data-brand`, plus the brand level from the engagement brief. Follow the `ntt-data-brand` skill for anything fixed at that level.

## Steps

1. Open the job: `python3 <studio>/studio.py init <folder> --client <client> --job <deliverable> --track commission --requester <engagement-studio|name> --requester-ref <codename> --brand <vault|external:source> [--due YYYY-MM-DD]`
2. Copy the request into `00-intake/commission.md` and fill every prompt. Copy the requester's own words where they exist.
3. Brief gate: when the requester's brief is complete and Tim has already approved it on their side (for example at an engagement studio gate), record `studio.py gate record brief --status skipped --note "Approved by requester: <where>"`. Otherwise raise it to Tim as normal.
4. Make the deliverable with the owning role. Use the Art Director for imagery and 3D. The studio's standards apply in full, except that the external brand overrides the studio's taste where the two conflict.
5. Review against the acceptance criteria and `studio-standards` (the panel from 0.3.0), then raise the final gate to Tim.
6. Return exactly what was asked for, where it was asked for, plus a short note covering what it is, the decisions made, provenance (from the image ledger if any imagery was generated) and any limits. Close the job.

## Boundaries

- One deliverable per commission. A request that grows into a brand, a site or a campaign becomes a proper studio job, and Tim decides.
- The studio does not rewrite the requester's argument or copy. It flags problems in the return note.
- Confidential engagement material stays in the job folder, under the requester's codename.
