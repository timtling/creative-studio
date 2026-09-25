# Changelog

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
