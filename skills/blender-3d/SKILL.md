---
name: blender-3d
description: >
  This skill should be used for any 3D on a creative studio job: "mock the mark up on a van",
  "render the signage", "how does this look at 25 metres", "3D hero", "turntable", "packaging
  mockup", "why do the renders look washed out", "set up a Blender scene from the vault". It
  covers when 3D is allowed at all, building scenes from the brand's own colour values, the
  draft and final presets, running Blender headless, and recording what was rendered so a result
  can be reproduced. The Identity designer uses it for touchpoint tests; the Art Director and the
  Builder use it for approved 3D only.
metadata:
  version: "0.3.5"
---

# Blender 3D

The studio's home machine is the Mac mini, which has Blender and the GPU. 3D is made there, headless, from the command line, so a render is a command that can be run again rather than a thing somebody did once in a window.

## Before anything: is this 3D allowed?

`studio-standards`, "When 3D is allowed", permits exactly three reasons: **a physical touchpoint** in `10-strategy/touchpoints.md`, **a spatial territory idea** argued in the board's Dimension section, or **explanation that needs space**. The direction gate pack states the approved plan.

If what you are about to make is not in that plan, stop and tell the Producer. It is a change request. "The deck needs a hero" is the most common reason bad 3D exists and it is not one of the three.

## Colour: the thing that goes wrong

Brand hex values are sRGB. **Blender expects linear values and applies a view transform, which is AgX by default and will desaturate every brand colour it touches.** Renders drift off-brand and nobody can say why.

Two rules, both non-negotiable:

1. **Material colours come from `vault/build/blender.json`**, which `vault.py build` writes as linear RGBA from the vault's own tokens. Never type a hex value into Blender and never convert one by eye.
2. **Set the scene's view transform to Standard.** `scene.view_settings.view_transform = "Standard"`. Check it in the render, not in the code: a Standard render of a brand surface next to the vault's swatch should be the same colour.

`scripts/blenderkit.py` does both when it builds a scene, and `verify` re-reads a finished render and reports the difference against the token it was meant to be.

## The presets

| Preset | For | Samples | Resolution | Denoise |
|---|---|---|---|---|
| `draft` | Looking, deciding, iterating | 32 | 960 × 540 | on |
| `final` | Gate packs and client-facing work | 512 | 2560 × 1440 | on |

Draft first, always. A draft answers "does the mark survive at this distance", which is the question most touchpoint tests are actually asking, and it answers it in seconds rather than minutes. Go to `final` when the answer is yes and somebody needs to see it.

## Running it

Headless, from the command line, never interactively:

```
blender --background --python <this skill's base directory>/scripts/blenderkit.py -- \
  --job ~/Studio/jobs/<job> --scene van --preset draft --distances 3,10,25
```

`--distances` renders the same scene from each camera distance in metres, which is the whole point of a touchpoint test: an object is judged at the distance it is seen from, never at 100% on a monitor.

## Recording what you did

Every render writes a sibling `.json` beside it with the scene, preset, samples, resolution, view transform, the vault build it took its colours from, the distances, the Blender version and the command. A render nobody can reproduce is a screenshot.

`blenderkit.py report <job>` collects them into `assets/3d/renders.md` for the gate pack.

## Judging a render

- **At the right size.** A 25-metre van test is judged at the size a van is at 25 metres, not full screen. Render it, then scale it down to what the eye would actually get.
- **Against the vault**, not against taste: run `verify` and read the numbers.
- **On the object's real material.** A mark on a matt vinyl wrap is not a mark on a gloss panel, and the difference decides whether a thin keyline survives.
- **The failure is the finding.** A mark that disappears at 25 metres has told you something the screen could not, and that belongs in `system.md` as a rule rather than being quietly fixed in the render.

## Rules

- Never put a mark, a name or a claim into a render that the job's `90-decisions.md` records as unresolved.
- No generated textures, no scanned real products, no third-party models without a licence recorded in the job.
- Renders are labelled as mockups in every internal and client review until the client approves the real thing. A render of a van is not a photograph of a van.
- The Identity designer owns `30-identity/touchpoint-tests/`; the Art Director owns everything under `assets/3d/`. One owner per file, as everywhere.
