# Changelog

## 0.1.0 (25 Sep 2026)

The imagery layer.

- Art Director agent: art direction and shot list before generation, per-client Recraft styles, rounds of explore, select, refine and finalise, and ownership of the ledger and contact sheet.
- image-generation skill: job set-up, workflow, model routing, prompt recipe, and licensing and confidentiality rules for Recraft and Replicate.
- `imagekit.py`: job file, provenance ledger, capture of URL and inline outputs, fetch before Replicate's one-hour expiry, call and US$ budget, contact sheet, provenance report.
- Hooks: deny spend without a confirmed Recraft paid plan, without a commercially cleared Replicate model, past budget, or with more than one active job. Log and capture after every call.
- 16 tests.
