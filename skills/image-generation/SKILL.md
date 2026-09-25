---
name: image-generation
description: >
  This skill should be used for any generated imagery on a creative studio job: "generate hero images",
  "make an illustration set", "create a Recraft style for the client", "vectorise this sketch", "upscale this",
  "run a Replicate model", "which image model should we use", "where did this image come from", "provenance
  report", "contact sheet". It covers the job set-up, Recraft and Replicate routing, prompt recipes, the ledger
  and budget, and the licensing rules. The Art Director loads it before any imagery work.
metadata:
  version: "0.1.0"
---

# Image generation

Generated imagery goes through two connectors and one script:

- **Recraft** (connector named `Recraft`, `https://mcp.recraft.ai/mcp`): vectors, icons, illustration systems, brand-consistent sets via custom styles, plus editing, background removal, vectorising and upscaling. Billed from the Recraft subscription credits.
- **Replicate** (connector named `Replicate`, `https://mcp.replicate.com/sse`): photographic hero imagery and any specialist model. Billed per run to the Replicate account.
- **`scripts/imagekit.py`**: the job file, ledger, budget, capture, contact sheet and provenance report. Run it with `python3 <this skill's base directory>/scripts/imagekit.py <command>`, and use `--help` to list the commands.

The plugin's hooks run `imagekit.py` around every Recraft and Replicate call. Calls that spend credits are denied until the job is ready. Every output is saved to the job's ledger, and the hook tells you in the tool result what was saved and what is still pending.

## Job set-up (once per job)

```
imagekit.py init <job-folder> --client <client> --job <job-name> --cap-calls 60 [--cap-usd 40]
imagekit.py confirm-recraft-paid --plan <plan name>      # only after Tim confirms it
imagekit.py approve-model <owner/name> --licence "<licence>" --url <model page> --commercial yes [--version <id>] [--usd <est per run>]
imagekit.py budget --recraft-usd <est> --replicate-usd <est>   # optional, enables the US$ cap
```

Only one job may be active below the working folder, or spend is denied, so that an asset can never land in another client's ledger. Use `imagekit.py set-active <folder> no` on a job that is done, or set `STUDIO_JOB` to the job folder.

## Workflow

1. **Direction.** Write `art-direction.md` and `shot-list.md` from the brief, the territory and the vault tokens. Pick a route per shot with `references/model-routing.md`.
2. **Styles.** For an illustration or icon system, create one Recraft custom style per territory from three to five reference images the studio has rights to use (client-supplied, licensed, or already approved outputs). Name it `<client>-<territory>-v<n>` and record it with `add-style`. A style is tied to the model and base style it was created with.
3. **Explore.** Generate two to four options per shot at draft size, using the recipe in `references/prompting.md`. Record the seed when the model returns one.
4. **Capture.** Read the hook message after each call. For Replicate, a prediction can return before its output exists: call the get-prediction tool until it has succeeded, and the hook captures the output from that response. Run `imagekit.py fetch` whenever anything is pending, and `imagekit.py status` to see how many minutes are left.
5. **Select.** Mark each option with `imagekit.py mark selected|rejected <ids> --territory T2 --note "<reason>"`. Selection is refused for an asset with no saved file or no commercial licence basis.
6. **Refine and finalise.** Use variations or image-to-image from the selected option, then upscale, vectorise or remove the background as needed. Stop after three rounds per shot.
7. **Review.** Run `imagekit.py sheet` and give `assets/contact-sheet.html` to the panel and the gate pack.
8. **Handoff.** Run `imagekit.py report`. `assets/provenance.md` goes into the handoff package and the client's licence appendix.

## When a call is denied

The denial reason says what is missing. It will be one of: the Recraft paid plan is unconfirmed, the Replicate model is not cleared (or is cleared as non-commercial), the budget is spent, the job is inactive, or more than one job is active. Report it to the Producer. Never rename a connector, switch provider or leave the job folder to get around it.

## When files cannot be downloaded

Generation runs from Claude's servers, but saving a file runs in the session's workspace, which only reaches allowlisted hosts. If captures stay `pending-fetch`, the network allowlist is missing `img.recraft.ai` or `replicate.delivery`. Tell the Producer, who asks Tim to add them (the README has the steps). Replicate outputs cannot be recovered after an hour. For those, if the host cannot be allowlisted in time, send Tim the URLs from `imagekit.py status` to save by hand, then record each file with `imagekit.py add`.

## References

- `references/model-routing.md`: which provider and model for which need, and how to pin a model.
- `references/prompting.md`: the prompt recipe, per-provider notes and what never goes in a prompt.
- `references/licensing.md`: ownership, commercial use, copyright and trademark limits, confidentiality and disclosure.
