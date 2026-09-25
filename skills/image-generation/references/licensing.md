# Licensing and provenance

These notes set the studio's operating rules. They are not legal advice. Anything a client will register, or will rely on owning exclusively, goes to counsel.

## Recraft

- On a **paid plan**, the user owns the images, has full commercial rights, and the images stay private. Ownership survives cancelling the subscription.
- On the **free plan**, images are public, owned by Recraft and licensed for personal use only. Upgrading later does not transfer them.
- So no client generation happens until Tim confirms the plan, which the hook enforces. The ledger records the plan name and when it was confirmed.
- Source: https://www.recraft.ai/docs/trust-and-security/ownership (checked 25 Sep 2026).

## Replicate

- Replicate does not grant one blanket licence. Each model has its own licence and commercial terms, set by its author, and these can differ between variants of the same family.
- Read the licence on the model page before clearing a model, and record the licence and URL with `approve-model`. If commercial use of outputs is not clearly allowed, record `--commercial no`.
- API prediction inputs, outputs and files are deleted after one hour by default, so capture is immediate.
- Source: https://replicate.com/docs/topics/predictions/data-retention (checked 25 Sep 2026).

## Limits to tell the client

- **Copyright.** In several jurisdictions, purely machine-generated images may not attract copyright protection, and human authorship is what counts. Where a client needs to own an asset exclusively (a hero illustration system, a mascot, a key visual), the studio's human refinement is part of the deliverable. Say so in the statement of work.
- **Trademark.** A generated mark is an exploration. Web screening is not clearance. Marks and names go to counsel for search before launch.
- **Similarity.** Generated images can resemble existing work. The Originality lens reviews every selected asset for resemblance to known marks, characters or artworks, and anything doubtful is rejected, not argued.

## Confidentiality

- Prompts and reference images go to third parties (Recraft, Replicate and the model authors' infrastructure). Treat a prompt as something that leaves the building.
- For stealth or confidential clients, use the codename and keep unannounced details out of prompts, unless the client has agreed in writing.
- Each client's custom styles and history sit in the studio's Recraft and Replicate accounts. Use client-prefixed style names. Where a corporate client's confidentiality terms require it, use a separate provider account for that client.

## Disclosure

- Internal and client review material labels generated imagery "AI-generated concept". The contact sheet says so by default.
- Whether published assets carry an AI disclosure is the client's decision. Record it in the handoff notes.

## The provenance record

`assets/ledger.jsonl` holds one record per asset: provider, tool, model and version, prompt, parameters, licence basis, source URL, file, sha256, timestamps and status. `assets/provenance.md` is the client-facing extract of selected and delivered assets, with the Recraft styles and Replicate models used. Stock, photographer, illustrator and client-supplied assets enter the same ledger through `imagekit.py add`, so one record covers the whole handoff.
