# Model routing

Route by what the asset has to do, not by which model is newest. Give the route and its reason for every shot in `shot-list.md`.

| Need | Route | Why | Notes |
|---|---|---|---|
| Mark explorations, icons, pictograms | Recraft, vector model | Native SVG output, editable paths | Explorations only. The Identity designer draws the final mark. Run svgo on anything kept. |
| Illustration system across many assets | Recraft, custom style per territory | One style keeps a set consistent | Build the style from assets the studio has rights to use. |
| Spot illustration, patterns, textures | Recraft, raster or vector | Style control, cheap within the plan | Vector when it must scale or recolour to tokens. |
| Photographic hero, lifestyle, product in context | Replicate, the strongest cleared photoreal model | Photoreal quality varies a lot by model | Clear the model first. Pin the version for the job. |
| Posters or scenes that need legible text in the image | Prefer type set in HTML/SVG over the image | Baked type cannot be edited or translated | If text really must be in the image, use a model known for text rendering and check every letter. |
| Background removal, upscaling, vectorising, erasing | Recraft tools first | Included in plan credits, one ledger | Use a Replicate specialist only if Recraft's result fails review. |
| Editing part of an image (inpainting) | Recraft edit, or a cleared Replicate edit model | Keep the selected composition | Record the source asset ID in `--note`. |
| Device, packaging or signage mockups | HTML/CSS renders with the real screens first | Real, editable, accurate | Use generated mockups for mood boards only. |
| Motion | The Animations artifact type first | Editable, on-brand, no licence question | Replicate video models only when real footage is needed, each with its own licence check. |

## Choosing and pinning a Replicate model

1. Search with the Replicate connector (`search_models`, or the text-to-image collections). Families worth checking for photoreal and text work include FLUX (Black Forest Labs), Imagen (Google), Ideogram, Seedream (ByteDance) and Recraft's own models. Line-ups change month to month, so check what is current at the start of each job rather than reusing last month's choice.
2. Read the model page: licence, commercial terms, typical run cost and output format. Licences differ between variants of the same family.
3. Run one test at draft size and look at it before clearing anything.
4. Clear it with `imagekit.py approve-model owner/name --version <id> ...`. Without a version, runs use the latest, which can change mid-job and break consistency.
5. Name the model as `owner/name` in every call. The hook matches the cleared list on that name.

## Cost discipline

- Explore at draft size and small batches, then finalise only what was selected.
- One provider per shot unless the first fails review. Mixing providers within a set breaks consistency faster than it adds quality.
- The call cap is the hard limit. The US$ cap is an estimate built from the per-run rates you record, so keep them honest.
