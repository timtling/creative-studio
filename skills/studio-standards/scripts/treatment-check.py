#!/usr/bin/env python3
"""treatment-check.py: the failing test for timidity.

The reach rule says one of three territories draws on art practice and that three
territories inside one narrow band of restraint is a Major finding. The rule had no
test, and the author's own claim that a reach is load-bearing is the least reliable
evidence available: on Cypress all three boards diverged completely on subject and
agreed on seven of seven treatment dimensions, which passes "if two territories could
share a logo they are one territory" and fails the reach rule, and nobody noticed
until after handover.

So this measures treatment rather than idea, off the boards' own values:

    ground   the lightest surface colour, bucketed
    ink      the darkest text colour, bucketed
    chroma   how many distinctly saturated hues the board actually uses
    radius   any non-zero corner radius
    gradient any gradient
    shadow   any box-shadow or drop-shadow
    texture  any image, noise, grain or repeating pattern fill

Three boards agreeing on five of seven is a finding to argue on the board, not a
fail. It cannot tell you whether a board is any good; it tells you whether three
boards that claim to be different bets are three colourways of one treatment.

Usage:  python3 treatment-check.py <board1> <board2> <board3> [--json]
Standard library only, Python 3.9+.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
RGB = re.compile(r"rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)", re.I)
RADIUS = re.compile(r"border-radius\s*:\s*([^;}\"']+)", re.I)
GRADIENT = re.compile(r"(linear|radial|conic)-gradient\s*\(", re.I)
SHADOW = re.compile(r"box-shadow\s*:\s*(?!\s*none)|drop-shadow\s*\(", re.I)
TEXTURE = re.compile(r"(background(?:-image)?|mask-image)\s*:\s*[^;}]*"
                     r"(url\(|repeating-(?:linear|radial)-gradient|noise|grain|texture)", re.I)
# Editor and browser chrome, not the board's own palette.
CHROME = re.compile(r"\b(?:sodipodi|inkscape):[\w-]+\s*=|color-scheme|-webkit-tap", re.I)
DIMENSIONS = ("ground", "ink", "chroma", "radius", "gradient", "shadow", "texture")
AGREEMENT_FINDING = 5


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def hsl(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = (x / 255 for x in rgb)
    hi, lo = max(r, g, b), min(r, g, b)
    light = (hi + lo) / 2
    if hi == lo:
        return 0.0, 0.0, light
    d = hi - lo
    sat = d / (2 - hi - lo) if light > 0.5 else d / (hi + lo)
    if hi == r:
        hue = ((g - b) / d) % 6
    elif hi == g:
        hue = (b - r) / d + 2
    else:
        hue = (r - g) / d + 4
    return hue * 60, sat, light


def colours(text: str) -> list[tuple[int, int, int]]:
    out = []
    for line in text.splitlines():
        if CHROME.search(line):
            continue
        out += [_hex_rgb(m.group(0)) for m in HEX.finditer(line)]
        out += [(min(255, int(a)), min(255, int(b)), min(255, int(c))) for a, b, c in RGB.findall(line)]
    return out


def bucket_light(light: float) -> str:
    return "near-white" if light >= 0.86 else "light" if light >= 0.62 else \
        "mid" if light >= 0.38 else "dark" if light >= 0.12 else "near-black"


def treatment(path: Path) -> dict:
    """The seven dimensions, read off one board."""
    text = path.read_text(errors="replace")
    cols = colours(text)
    lights = sorted((hsl(c)[2], c) for c in cols)
    chroma = {round(hsl(c)[0] / 30) for c in cols if hsl(c)[1] >= 0.25 and 0.08 < hsl(c)[2] < 0.94}
    radii = [v.strip() for v in RADIUS.findall(text)]
    return {
        "board": path.name,
        "ground": bucket_light(lights[-1][0]) if lights else "none",
        "ink": bucket_light(lights[0][0]) if lights else "none",
        "chroma": "none" if not chroma else "one hue" if len(chroma) == 1 else
                  "two hues" if len(chroma) == 2 else "three or more",
        "radius": "yes" if any(r not in ("0", "0px", "0%", "none") for r in radii) else "no",
        "gradient": "yes" if GRADIENT.search(text) else "no",
        "shadow": "yes" if SHADOW.search(text) else "no",
        "texture": "yes" if TEXTURE.search(text) else "no",
    }


def compare(rows: list[dict]) -> dict:
    agreed = [d for d in DIMENSIONS if len({r[d] for r in rows}) == 1]
    return {
        "boards": rows,
        "agreed": agreed,
        "agreed_count": len(agreed),
        "of": len(DIMENSIONS),
        "finding": len(agreed) >= AGREEMENT_FINDING,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("boards", nargs="+", help="the territory boards, normally three")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    paths = [Path(b) for b in a.boards]
    for q in paths:
        if not q.exists():
            sys.exit(f"{q} does not exist")
    if len(paths) < 2:
        sys.exit("Give at least two boards: this compares them against each other.")
    rows = [treatment(q) for q in paths]
    if len({r["board"] for r in rows}) < len(rows):        # T1/board.html, T2/board.html, ...
        for r, q in zip(rows, paths):
            r["board"] = str(Path(q.parent.name) / q.name)
    res = compare(rows)
    if a.json:
        print(json.dumps(res, indent=2))
        return 1 if res["finding"] else 0
    w = max(len(r["board"]) for r in res["boards"])
    print(f"{'board'.ljust(w)}  " + "  ".join(f"{d:<14}" for d in DIMENSIONS))
    for r in res["boards"]:
        print(f"{r['board'].ljust(w)}  " + "  ".join(f"{str(r[d]):<14}" for d in DIMENSIONS))
    print()
    if res["finding"]:
        print(f"TIMIDITY FINDING: {res['agreed_count']} of {res['of']} treatment dimensions are identical "
              f"across all {len(res['boards'])} boards ({', '.join(res['agreed'])}).")
        print("Three different strategic bets may share a treatment, but the Creative Lead has to say so "
              "on the board and argue it. Unargued restraint is a default wearing a strategy's clothes.")
    else:
        print(f"No finding: {res['agreed_count']} of {res['of']} dimensions agree "
              f"({', '.join(res['agreed']) or 'none'}).")
    return 1 if res["finding"] else 0


if __name__ == "__main__":
    sys.exit(main())
