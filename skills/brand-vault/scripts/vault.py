#!/usr/bin/env python3
"""vault.py: the brand vault for a creative studio job.

The vault is the single source of truth for a brand's values. Every deliverable
references it rather than typing values. Tokens follow the W3C Design Tokens
(DTCG) format: groups of {"$value": ..., "$type": ...} with {group.name} aliases.

Commands: init, validate, build, contrast, lint, hook-lint.
Run `python3 vault.py <command> --help`. Standard library only, Python 3.9+.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE.parent / "assets" / "tokens.template.json"
JOB_FILE = "studio-job.json"

REQUIRED_GROUPS = ["color", "text", "surface", "font", "type", "space"]
REQUIRED_PAIR = ("text.default", "surface.default")
HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
ALIAS_RE = re.compile(r"^\{([A-Za-z0-9_.-]+)\}$")
DIM_RE = re.compile(r"^-?\d+(?:\.\d+)?(?:px|rem|em|%)$")
DUR_RE = re.compile(r"^\d+(?:\.\d+)?(?:ms|s)$")
LITERAL_COLOUR_RE = re.compile(
    r"(?<![\w&-])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-zA-Z_-])"
    r"|\b(?:rgba?|hsla?)\(\s*[^)]*\)",
)
LINT_EXT = {".html", ".htm", ".css", ".scss", ".svg", ".jsx", ".tsx", ".vue", ".js", ".ts"}
NEUTRAL_OK = {"#fff", "#ffffff", "#000", "#000000"}  # allowed only when the vault defines them


# --------------------------------------------------------------------------- token model

class TokenError(Exception):
    pass


def load(vault: Path) -> dict:
    p = vault / "tokens.json" if vault.is_dir() else vault
    return json.loads(p.read_text())


def flatten(tree: dict, prefix: str = "", inherited: str | None = None) -> dict[str, dict]:
    """{'color.ink': {'value': ..., 'type': ..., 'description': ...}} for every token."""
    out: dict[str, dict] = {}
    gtype = tree.get("$type", inherited)
    for k, v in tree.items():
        if k.startswith("$") or not isinstance(v, dict):
            continue
        path = f"{prefix}.{k}" if prefix else k
        if "$value" in v:
            out[path] = {"value": v["$value"], "type": v.get("$type", gtype), "description": v.get("$description")}
        else:
            out.update(flatten(v, path, v.get("$type", gtype)))
    return out


def resolve(tokens: dict[str, dict]) -> dict[str, dict]:
    """Resolve {alias} values. Raises TokenError on missing targets or cycles."""
    resolved: dict[str, dict] = {}

    def res(path: str, seen: tuple) -> object:
        if path in seen:
            raise TokenError(f"alias cycle: {' -> '.join(seen + (path,))}")
        if path not in tokens:
            raise TokenError(f"{seen[-1] if seen else '?'} refers to missing token {{{path}}}")
        v = tokens[path]["value"]
        if isinstance(v, str):
            m = ALIAS_RE.match(v.strip())
            if m:
                return res(m.group(1), seen + (path,))
        return v

    for path, t in tokens.items():
        val = res(path, ())
        typ = t["type"]
        if typ is None and isinstance(t["value"], str) and ALIAS_RE.match(t["value"].strip()):
            typ = tokens.get(ALIAS_RE.match(t["value"].strip()).group(1), {}).get("type")
        resolved[path] = dict(t, resolved=val, type=typ)
    return resolved


def norm_hex(h: str) -> str:
    h = h.lower()
    if len(h) == 4:
        h = "#" + "".join(c * 2 for c in h[1:])
    return h[:7]


def rgb(h: str) -> tuple[float, float, float]:
    h = norm_hex(h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(h: str) -> float:
    r, g, b = (srgb_to_linear(c) for c in rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def colours(res: dict[str, dict]) -> dict[str, str]:
    return {p: norm_hex(t["resolved"]) for p, t in res.items()
            if t["type"] == "color" and isinstance(t["resolved"], str) and HEX_RE.match(t["resolved"])}


# --------------------------------------------------------------------------- validation

def validate(tree: dict) -> tuple[list[str], list[str]]:
    """(errors, warnings)."""
    errors, warnings = [], []
    for g in REQUIRED_GROUPS:
        if g not in tree:
            errors.append(f"missing required group '{g}'")
    toks = flatten(tree)
    if not toks:
        return errors + ["no tokens defined"], warnings
    for p, t in toks.items():
        if t["value"] in (None, ""):
            errors.append(f"{p}: no value set")
    if errors:
        return errors, warnings
    try:
        res = resolve(toks)
    except TokenError as e:
        return [str(e)], warnings
    for p, t in res.items():
        v, typ = t["resolved"], t["type"]
        if typ is None:
            errors.append(f"{p}: no $type (set it on the token or its group)")
        elif typ == "color" and not (isinstance(v, str) and HEX_RE.match(v)):
            errors.append(f"{p}: colour must be hex (#rrggbb), got {v!r}")
        elif typ == "dimension" and not (isinstance(v, str) and DIM_RE.match(v)):
            errors.append(f"{p}: dimension must be a number with px, rem, em or %, got {v!r}")
        elif typ == "duration" and not (isinstance(v, str) and DUR_RE.match(v)):
            errors.append(f"{p}: duration must be ms or s, got {v!r}")
        elif typ == "fontFamily" and not (isinstance(v, (str, list)) and v):
            errors.append(f"{p}: fontFamily must be a name or a list of names")
        elif typ == "fontWeight" and not (isinstance(v, (int, str))):
            errors.append(f"{p}: fontWeight must be a number or keyword")
        elif typ == "cubicBezier" and not (isinstance(v, list) and len(v) == 4):
            errors.append(f"{p}: cubicBezier must be four numbers")
    for grp in ("text", "surface"):
        for p in res:
            if p.startswith(grp + ".") and res[p]["type"] == "color":
                raw = toks[p]["value"]
                if not (isinstance(raw, str) and ALIAS_RE.match(raw.strip())):
                    warnings.append(f"{p}: semantic tokens should alias a primitive in 'color', not hold a raw value")
    if errors:
        return errors, warnings
    col = colours(res)
    a, b = REQUIRED_PAIR
    if a in col and b in col:
        r = contrast_ratio(col[a], col[b])
        if r < 4.5:
            errors.append(f"{a} on {b} is {r:.2f}:1, below WCAG AA 4.5:1 for body text")
    else:
        errors.append(f"required tokens {a} and {b} must both be colours")
    return errors, warnings


def contrast_matrix(res: dict[str, dict]) -> list[dict]:
    col = colours(res)
    rows = []
    for t in sorted(p for p in col if p.startswith(("text.", "accent."))):
        for s in sorted(p for p in col if p.startswith("surface.")):
            # Only the pairs a designer would actually use: inverse text on inverse surfaces,
            # other text on other surfaces, accents on every surface.
            if t.startswith("text.") and (("inverse" in t) != ("inverse" in s)):
                continue
            r = contrast_ratio(col[t], col[s])
            rows.append({"fg": t, "bg": s, "ratio": round(r, 2), "AA": r >= 4.5, "AA_large": r >= 3.0, "AAA": r >= 7.0})
    return rows


# --------------------------------------------------------------------------- build

def css_name(path: str) -> str:
    return "--" + re.sub(r"[^a-z0-9-]", "-", path.replace(".", "-").lower())


def css_value(t: dict, toks: dict) -> str:
    raw = t["value"]
    if isinstance(raw, str) and ALIAS_RE.match(raw.strip()):
        return f"var({css_name(ALIAS_RE.match(raw.strip()).group(1))})"
    v = t["resolved"]
    if t["type"] == "fontFamily":
        names = v if isinstance(v, list) else [v]
        return ", ".join(n if n in ("serif", "sans-serif", "monospace", "system-ui") else f'"{n}"' for n in names)
    if t["type"] == "cubicBezier":
        return f"cubic-bezier({', '.join(str(x) for x in v)})"
    return str(v)


def build(vault: Path) -> list[Path]:
    tree = load(vault)
    errors, _ = validate(tree)
    if errors:
        raise TokenError("vault does not validate:\n  " + "\n  ".join(errors))
    toks = flatten(tree)
    res = resolve(toks)
    out = vault / "build"
    out.mkdir(exist_ok=True)
    stamp = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M SGT")
    name = tree.get("$description") or vault.parent.name

    css = [f"/* Generated from tokens.json by vault.py, {stamp}. Do not edit: change tokens.json and rebuild. */", ":root {"]
    css += [f"  {css_name(p)}: {css_value(t, toks)};" for p, t in res.items()]
    css.append("}")
    (out / "tokens.css").write_text("\n".join(css) + "\n")

    flat = {p: t["resolved"] for p, t in res.items()}
    (out / "tokens.flat.json").write_text(json.dumps(flat, indent=2, ensure_ascii=False) + "\n")

    blender = {p: [round(srgb_to_linear(c), 6) for c in rgb(h)] + [1.0] for p, h in colours(res).items()}
    (out / "blender.json").write_text(json.dumps({
        "_note": "Linear RGBA for Blender Principled BSDF inputs. Set the scene view transform to Standard so these render as the brand hex values.",
        **blender}, indent=2) + "\n")

    (out / "swatches.html").write_text(swatches_html(name, res, stamp))
    return [out / f for f in ("tokens.css", "tokens.flat.json", "blender.json", "swatches.html")]


def swatches_html(name: str, res: dict[str, dict], stamp: str) -> str:
    e = html.escape
    col = colours(res)
    fam = {p: t["resolved"] for p, t in res.items() if t["type"] == "fontFamily"}
    body_font = fam.get("font.body") or next(iter(fam.values()), "system-ui")
    body_font = ", ".join(body_font) if isinstance(body_font, list) else body_font
    display_font = fam.get("font.display") or body_font
    display_font = ", ".join(display_font) if isinstance(display_font, list) else display_font
    bg, fg = col.get("surface.default", "#ffffff"), col.get("text.default", "#111111")
    muted = col.get("text.muted", fg)
    line = col.get("border.default", muted)

    def chip(p, h):
        on = "#000000" if luminance(h) > 0.4 else "#ffffff"
        return (f'<figure><div class="sw" style="background:{h};color:{on}">{e(norm_hex(h))}</div>'
                f'<figcaption><b>{e(p)}</b></figcaption></figure>')

    groups = {}
    for p, h in col.items():
        groups.setdefault(p.split(".")[0], []).append(chip(p, h))
    colour_html = "".join(f"<h3>{e(g)}</h3><div class=grid>{''.join(v)}</div>" for g, v in groups.items())
    rows = contrast_matrix(res)
    ctable = "".join(
        f"<tr><td>{e(r['fg'])}</td><td>{e(r['bg'])}</td><td><span class=pair style='background:{col[r['bg']]};color:{col[r['fg']]}'>Aa</span></td>"
        f"<td>{r['ratio']}:1</td><td>{'AAA' if r['AAA'] else 'AA' if r['AA'] else 'Large only' if r['AA_large'] else 'Fail'}</td></tr>"
        for r in rows)
    sizes = [(p, t["resolved"]) for p, t in res.items() if p.startswith("type.") and t["type"] == "dimension"]
    type_html = "".join(f'<div class=spec><span class=lab>{e(p)} · {e(str(v))}</span>'
                        f'<span style="font-size:{e(str(v))};font-family:{e(display_font if "display" in p or "h" in p.split(".")[-1][:1] else body_font)}">'
                        f'The quick brown fox jumps over the lazy dog</span></div>' for p, v in sizes)
    spaces = [(p, t["resolved"]) for p, t in res.items() if p.startswith("space.") and t["type"] == "dimension"]
    space_html = "".join(f'<div class=sp><span class=bar style="width:{e(str(v))}"></span><span class=lab>{e(p)} · {e(str(v))}</span></div>' for p, v in spaces)
    return f"""<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{e(name)} tokens</title>
<style>
body{{margin:0;padding:32px 16px 64px;background:{bg};color:{fg};font:16px/1.5 {e(body_font)}}}
main{{max-width:1040px;margin:0 auto}}h1{{font:600 28px/1.2 {e(display_font)};margin:0 0 4px}}
h2{{font:600 18px/1.3 {e(display_font)};margin:40px 0 12px;padding-top:16px;border-top:1px solid {line}}}
h3{{font-size:13px;font-weight:600;margin:20px 0 8px;color:{muted}}}p{{margin:0;color:{muted}}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px}}
figure{{margin:0}}.sw{{height:84px;border-radius:8px;display:flex;align-items:flex-end;padding:8px;font:12px ui-monospace,monospace;border:1px solid {line}}}
figcaption{{font-size:12px;margin-top:6px}}table{{border-collapse:collapse;width:100%;font-size:14px}}
td,th{{text-align:left;padding:6px 8px;border-bottom:1px solid {line}}}.pair{{display:inline-block;padding:2px 10px;border-radius:4px;border:1px solid {line}}}
.spec{{display:flex;flex-direction:column;gap:2px;margin:0 0 16px;overflow:hidden}}.spec span:last-child{{line-height:1.15}}.lab{{font:12px ui-monospace,monospace;color:{muted}}}
.sp{{display:flex;align-items:center;gap:12px;margin:6px 0}}.bar{{display:inline-block;height:12px;background:{col.get('accent.default', fg)}}}
.wrap{{overflow-x:auto}}
</style>
<main><h1>{e(name)}</h1><p>Brand tokens, built {e(stamp)} from vault/tokens.json.</p>
<h2>Colour</h2>{colour_html}
<h2>Contrast</h2><div class=wrap><table><tr><th>Foreground</th><th>Background</th><th></th><th>Ratio</th><th>WCAG</th></tr>{ctable}</table></div>
<h2>Type scale</h2>{type_html}
<h2>Space</h2>{space_html}
</main></html>
"""


# --------------------------------------------------------------------------- lint

def lint_text(text: str, suffix: str, allowed: set[str]) -> list[tuple[int, str, str]]:
    """[(line, literal, reason)] for literal colours that bypass the vault."""
    issues = []
    for i, line in enumerate(text.splitlines(), 1):
        for m in LITERAL_COLOUR_RE.finditer(line):
            lit = m.group(0)
            if suffix == ".svg":
                if lit.startswith("#") and norm_hex(lit) in allowed:
                    continue
                issues.append((i, lit, "not a vault colour"))
            else:
                reason = "use a var(--token)" if not (lit.startswith("#") and norm_hex(lit) in allowed) else \
                    "vault colour typed as a value; use its var(--token)"
                issues.append((i, lit, reason))
    return issues


def lint_files(files: list[Path], vault: Path) -> dict[str, list]:
    tree = load(vault)
    res = resolve(flatten(tree))
    allowed = set(colours(res).values())
    out = {}
    for f in files:
        if f.suffix.lower() not in LINT_EXT or not f.exists():
            continue
        if "vault" in f.parts or f.name == "tokens.css":
            continue
        issues = lint_text(f.read_text(errors="replace"), f.suffix.lower(), allowed)
        if issues:
            out[str(f)] = issues
    return out


def find_job(start: Path) -> Path | None:
    start = start if start.is_dir() else start.parent
    for p in [start, *start.parents]:
        if (p / JOB_FILE).exists():
            return p
    return None


# --------------------------------------------------------------------------- commands

def cmd_init(a) -> int:
    v = Path(a.vault)
    v.mkdir(parents=True, exist_ok=True)
    (v / "assets").mkdir(exist_ok=True)
    t = v / "tokens.json"
    if t.exists() and not a.force:
        sys.exit(f"{t} exists. Use --force to replace it.")
    tree = json.loads(TEMPLATE.read_text())
    if a.name:
        tree["$description"] = a.name
    t.write_text(json.dumps(tree, indent=2, ensure_ascii=False) + "\n")
    print(f"Created {t}. Fill every null value, then run `vault.py validate {v}`.")
    return 0


def cmd_validate(a) -> int:
    errors, warnings = validate(load(Path(a.vault)))
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    if not errors:
        print("Vault valid.")
    return 1 if errors else 0


def cmd_build(a) -> int:
    try:
        for p in build(Path(a.vault)):
            print(f"Wrote {p}")
    except TokenError as e:
        print(str(e))
        return 1
    return 0


def cmd_contrast(a) -> int:
    rows = contrast_matrix(resolve(flatten(load(Path(a.vault)))))
    if a.json:
        print(json.dumps(rows, indent=2))
        return 0
    for r in rows:
        verdict = "AAA" if r["AAA"] else "AA" if r["AA"] else "large text only" if r["AA_large"] else "FAIL"
        print(f"{r['fg']:<24} on {r['bg']:<22} {r['ratio']:>5}:1  {verdict}")
    return 0


def cmd_lint(a) -> int:
    res = lint_files([Path(f) for f in a.files], Path(a.vault))
    for f, issues in res.items():
        for line, lit, why in issues:
            print(f"{f}:{line}: {lit} ({why})")
    if not res:
        print("No literal colours outside the vault.")
    return 1 if res else 0


def cmd_hook_lint(_a) -> int:
    try:
        h = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 0
    ti = h.get("tool_input") or {}
    fp = ti.get("file_path") or ti.get("path")
    if not fp:
        return 0
    f = Path(fp)
    if not f.is_absolute():
        f = Path(h.get("cwd") or ".") / f
    if f.suffix.lower() not in LINT_EXT:
        return 0
    job = find_job(f)
    if job is None:
        return 0
    try:
        brand = json.loads((job / JOB_FILE).read_text()).get("brand_source", "vault")
    except (OSError, json.JSONDecodeError):
        brand = "vault"
    vault = job / "vault"
    if brand != "vault" or not (vault / "tokens.json").exists():
        return 0
    try:
        if validate(load(vault))[0]:
            return 0
        issues = lint_files([f], vault).get(str(f), [])
    except (TokenError, OSError, json.JSONDecodeError):
        return 0
    if not issues:
        return 0
    shown = "; ".join(f"line {ln}: {lit} ({why})" for ln, lit, why in issues[:8])
    more = f" and {len(issues) - 8} more" if len(issues) > 8 else ""
    msg = (f"Vault lint, {f.name}: {len(issues)} literal colour(s) bypass the vault: {shown}{more}. "
           "Reference tokens (var(--...) from vault/build/tokens.css); in SVG use exact vault colours only.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="vault.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="create vault/tokens.json from the template")
    p.add_argument("vault")
    p.add_argument("--name", help="brand name for the swatches page")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_init)
    for name, fn, h in (("validate", cmd_validate, "check structure, values, aliases and the required contrast pair"),
                        ("build", cmd_build, "write build/tokens.css, tokens.flat.json, blender.json, swatches.html"),
                        ("contrast", cmd_contrast, "text and accent against every surface, with WCAG verdicts")):
        p = sub.add_parser(name, help=h)
        p.add_argument("vault")
        if name == "contrast":
            p.add_argument("--json", action="store_true")
        p.set_defaults(fn=fn)
    p = sub.add_parser("lint", help="find literal colours in deliverables that bypass the vault")
    p.add_argument("--vault", required=True)
    p.add_argument("files", nargs="+")
    p.set_defaults(fn=cmd_lint)
    sub.add_parser("hook-lint", help="PostToolUse hook for Write/Edit").set_defaults(fn=cmd_hook_lint)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
