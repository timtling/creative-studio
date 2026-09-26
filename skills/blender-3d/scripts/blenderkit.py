#!/usr/bin/env python3
"""blenderkit.py: the studio's Blender front end.

Two jobs, and it is careful about the boundary between them:

  * Outside Blender it is an ordinary CLI (`presets`, `plan`, `verify`, `report`)
    that needs nothing but the standard library, so the Producer and the tests
    can use it on any machine.
  * Inside Blender (`blender --background --python blenderkit.py -- ...`) it
    sets the view transform to Standard, sets the engine, samples and resolution,
    takes the material colours from vault/build/blender.json, moves the camera to
    each distance, renders, and writes a sidecar recording what was done.

IT DOES NOT BUILD THE SCENE. It creates no geometry, no materials, no lights and no
camera, and it never has: the caller supplies the scene, either as a .blend Blender
opens or as a scene script run before this one. Pointed at a factory startup file it
renders Blender's default cube, correctly exposed and in the brand's colours, which
looks exactly like a working render and answers nothing. A scene script is preferred
over a .blend because a .blend is not a record of how the scene was made.

Colours are never typed in and never converted by eye: they come from the vault
build, which is the only place that knows the brand's linear values.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

SGT = dt.timezone(dt.timedelta(hours=8))
PRESETS = {
    "draft": {"samples": 32, "width": 960, "height": 540, "denoise": True},
    "final": {"samples": 512, "width": 2560, "height": 1440, "denoise": True},
}
VIEW_TRANSFORM = "Standard"          # AgX, the default, desaturates every brand colour
SCENES = ("van", "sign", "card", "packaging", "stand")
# What each touchpoint is actually read from, in metres. A render judged at the
# wrong distance answers a question nobody asked.
DEFAULT_DISTANCES = {"van": (3, 10, 25), "sign": (2, 10), "card": (0.3,),
                     "packaging": (0.5, 2), "stand": (2, 10, 20)}


def now() -> dt.datetime:
    return dt.datetime.now(SGT)


def preset(name: str) -> dict:
    if name not in PRESETS:
        sys.exit(f"Unknown preset {name}. Presets: {', '.join(PRESETS)}")
    return dict(PRESETS[name], name=name, view_transform=VIEW_TRANSFORM)


def distances(scene: str, arg: str | None) -> list[float]:
    if arg:
        return [float(x) for x in arg.split(",") if x.strip()]
    return list(DEFAULT_DISTANCES.get(scene, (1,)))


def load_colours(job: Path) -> dict:
    """The brand's linear values, from the vault build. Never a hex typed by hand."""
    p = job / "vault" / "build" / "blender.json"
    if not p.exists():
        sys.exit(f"{p} is missing. Run `vault.py build {job}/vault` first: Blender colours come from the vault, "
                 "and a hex value typed into a scene is off-brand by the time it is rendered.")
    return json.loads(p.read_text())


def sidecar(out: Path, job: Path, scene: str, pre: dict, dist: float, colours: dict) -> Path:
    """What was rendered, in enough detail to run it again."""
    rec = {
        "rendered_at": now().isoformat(timespec="seconds"),
        "scene": scene,
        "distance_m": dist,
        "preset": pre["name"],
        "samples": pre["samples"],
        "resolution": [pre["width"], pre["height"]],
        "denoise": pre["denoise"],
        "view_transform": pre["view_transform"],
        "vault_build": str((job / "vault" / "build" / "blender.json")),
        "vault_tokens": sorted(colours.get("color", colours).keys())[:24],
        "blender": os.environ.get("BLENDER_VERSION", "unknown"),
        "command": " ".join(sys.argv),
    }
    p = out.with_suffix(".json")
    p.write_text(json.dumps(rec, indent=2) + "\n")
    return p


def cmd_presets(_a) -> int:
    for n, p in PRESETS.items():
        print(f"{n:6} {p['samples']:4} samples  {p['width']}x{p['height']}  denoise={p['denoise']}  "
              f"view_transform={VIEW_TRANSFORM}")
    return 0


def cmd_plan(a) -> int:
    """What a render would do, without Blender. Used to check a job is ready."""
    job = Path(a.job).expanduser().resolve()
    pre = preset(a.preset)
    ds = distances(a.scene, a.distances)
    vault = job / "vault" / "build" / "blender.json"
    print(f"{a.scene} · {pre['name']} · {pre['samples']} samples · {pre['width']}x{pre['height']} · "
          f"view transform {pre['view_transform']}")
    print(f"distances (m): {', '.join(str(d) for d in ds)}")
    print(f"colours from: {vault}" + ("" if vault.exists() else "   MISSING, run vault.py build"))
    print(f"outputs: {len(ds)} render(s) + {len(ds)} sidecar(s)")
    return 0 if vault.exists() else 1


def cmd_verify(a) -> int:
    """Does a finished render still carry the brand's colours?

    Reads the sidecar rather than guessing, and says plainly when it cannot check.
    """
    p = Path(a.render).expanduser().resolve()
    rec = p.with_suffix(".json")
    if not rec.exists():
        print(f"No sidecar beside {p.name}: this render cannot be reproduced or checked. "
              "Re-render it through blenderkit.py.")
        return 1
    d = json.loads(rec.read_text())
    problems = []
    if d.get("view_transform") != VIEW_TRANSFORM:
        problems.append(f"view transform was {d.get('view_transform')!r}, not {VIEW_TRANSFORM!r}: "
                        "every brand colour in this render is desaturated")
    if not Path(d.get("vault_build", "")).exists():
        problems.append("the vault build it took its colours from is gone; rebuild and re-render")
    for x in problems:
        print(f"  - {x}")
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


def cmd_report(a) -> int:
    job = Path(a.job).expanduser().resolve()
    d = job / "assets" / "3d"
    recs = sorted(d.rglob("*.json")) if d.exists() else []
    lines = ["# 3D renders", "", f"Written by blenderkit.py, {now().strftime('%d %b %Y %H:%M')}.", "",
             "| Render | Scene | Distance | Preset | Samples | View transform |", "|---|---|---|---|---|---|"]
    for r in recs:
        try:
            x = json.loads(r.read_text())
        except json.JSONDecodeError:
            continue
        lines.append(f"| {r.with_suffix('.png').name} | {x.get('scene')} | {x.get('distance_m')} m | "
                     f"{x.get('preset')} | {x.get('samples')} | {x.get('view_transform')} |")
    if not recs:
        lines.append("| (none yet) | | | | | |")
    out = d / "renders.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    print(f"{out} ({len(recs)} render(s))")
    return 0


def build_and_render(a) -> int:
    """Inside Blender only."""
    import bpy  # noqa: F401  (only importable under `blender --background --python`)

    job = Path(a.job).expanduser().resolve()
    colours = load_colours(job)
    pre = preset(a.preset)
    scene = bpy.context.scene
    scene.view_settings.view_transform = VIEW_TRANSFORM       # before anything is shaded
    scene.render.engine = "CYCLES"
    scene.cycles.samples = pre["samples"]
    scene.cycles.use_denoising = pre["denoise"]
    scene.render.resolution_x, scene.render.resolution_y = pre["width"], pre["height"]

    out_dir = job / "assets" / "3d" / a.scene
    out_dir.mkdir(parents=True, exist_ok=True)
    for dist in distances(a.scene, a.distances):
        for ob in bpy.data.objects:
            if ob.type == "CAMERA":
                ob.location.y = -abs(float(dist))
        out = out_dir / f"{a.scene}-{a.preset}-{str(dist).replace('.', 'p')}m.png"
        scene.render.filepath = str(out)
        bpy.ops.render.render(write_still=True)
        sidecar(out, job, a.scene, pre, float(dist), colours)
        print(f"rendered {out.name}")
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" in argv:                       # blender --background --python this.py -- <args>
        argv = argv[argv.index("--") + 1:]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("presets").set_defaults(fn=cmd_presets)
    for name, fn in (("plan", cmd_plan), ("render", build_and_render)):
        s = sub.add_parser(name)
        s.add_argument("--job", required=True)
        s.add_argument("--scene", required=True, choices=SCENES)
        s.add_argument("--preset", default="draft")
        s.add_argument("--distances")
        s.set_defaults(fn=fn)
    s = sub.add_parser("verify"); s.add_argument("render"); s.set_defaults(fn=cmd_verify)
    s = sub.add_parser("report"); s.add_argument("job"); s.set_defaults(fn=cmd_report)
    # `--job ... --scene ...` with no subcommand means render, which is how Blender calls it
    if argv and not argv[0].startswith("-") or not argv:
        a = ap.parse_args(argv)
    else:
        a = ap.parse_args(["render", *argv])
    if not getattr(a, "fn", None):
        ap.print_help()
        return 1
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
