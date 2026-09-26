"""Tests for skills/brand-vault/scripts/vault.py. Run: python3 -m pytest tests -q"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "brand-vault" / "scripts" / "vault.py"
sys.path.insert(0, str(SCRIPT.parent))
import vault as vt  # noqa: E402

PALETTE = dict(ink="#0B1B3F", paper="#F4F1EA", mid="#5E6472", line="#D9D4C7", signal="#E4572E", support="#2E8B7A")


def filled(tmp_path: Path) -> Path:
    v = tmp_path / "job" / "vault"
    assert vt.main(["init", str(v), "--name", "Tessel"]) == 0
    t = json.loads((v / "tokens.json").read_text())
    for k, val in PALETTE.items():
        t["color"][k]["$value"] = val
    t["font"]["display"]["$value"] = ["Fraunces", "serif"]
    t["font"]["body"]["$value"] = ["Inter Tight", "sans-serif"]
    for k, val in dict(caption="13px", body="16px", lead="20px", h3="25px", h2="31px", h1="39px", display="61px").items():
        t["type"][k]["$value"] = val
    t["radius"]["sm"]["$value"] = "4px"
    t["radius"]["md"]["$value"] = "10px"
    (v / "tokens.json").write_text(json.dumps(t, indent=2))
    return v


def test_template_reports_unset_values(tmp_path):
    v = tmp_path / "vault"
    vt.main(["init", str(v)])
    errors, _ = vt.validate(vt.load(v))
    assert any("color.ink: no value set" in e for e in errors)


def test_filled_vault_validates_and_builds(tmp_path):
    v = filled(tmp_path)
    errors, warnings = vt.validate(vt.load(v))
    assert errors == [] and warnings == []
    assert vt.main(["build", str(v)]) == 0
    css = (v / "build" / "tokens.css").read_text()
    assert "--color-ink: #0B1B3F;" in css and "--text-default: var(--color-ink);" in css
    assert '--font-display: "Fraunces", serif;' in css and "--motion-easing-standard: cubic-bezier(0.2, 0, 0, 1);" in css
    flat = json.loads((v / "build" / "tokens.flat.json").read_text())
    assert flat["text.default"] == "#0B1B3F"
    blender = json.loads((v / "build" / "blender.json").read_text())
    assert blender["color.paper"][3] == 1.0 and 0.8 < blender["color.paper"][0] < 0.95  # linear, not sRGB 0.957
    assert "Contrast" in (v / "build" / "swatches.html").read_text()


def test_contrast_maths():
    assert round(vt.contrast_ratio("#000000", "#ffffff"), 2) == 21.0
    assert round(vt.contrast_ratio("#777777", "#ffffff"), 2) == 4.48


def test_required_pair_must_pass_aa(tmp_path):
    v = filled(tmp_path)
    t = vt.load(v)
    t["color"]["ink"]["$value"] = "#C9C4B8"
    errors, _ = vt.validate(t)
    assert any("below WCAG AA" in e for e in errors)


def test_alias_errors(tmp_path):
    v = filled(tmp_path)
    t = vt.load(v)
    t["text"]["default"]["$value"] = "{color.nope}"
    assert "missing token" in vt.validate(t)[0][0]
    t["text"]["default"]["$value"] = "{text.muted}"
    t["text"]["muted"]["$value"] = "{text.default}"
    assert "cycle" in vt.validate(t)[0][0]


def test_type_checks(tmp_path):
    v = filled(tmp_path)
    t = vt.load(v)
    t["type"]["body"]["$value"] = "16"
    t["color"]["signal"]["$value"] = "orange"
    errs = vt.validate(t)[0]
    assert any("type.body: dimension" in e for e in errs) and any("color.signal: colour must be hex" in e for e in errs)


def test_semantic_raw_value_warns(tmp_path):
    v = filled(tmp_path)
    t = vt.load(v)
    t["surface"]["default"]["$value"] = "#FFFFFF"
    errors, warnings = vt.validate(t)
    assert errors == [] and any("surface.default" in w for w in warnings)


def test_matrix_skips_meaningless_pairs(tmp_path):
    v = filled(tmp_path)
    rows = vt.contrast_matrix(vt.resolve(vt.flatten(vt.load(v))))
    pairs = {(r["fg"], r["bg"]) for r in rows}
    assert ("text.default", "surface.default") in pairs and ("text.inverse", "surface.inverse") in pairs
    assert ("text.default", "surface.inverse") not in pairs and ("accent.default", "surface.inverse") in pairs


def test_lint(tmp_path):
    v = filled(tmp_path)
    site = tmp_path / "job" / "50-applications"
    site.mkdir(parents=True)
    page = site / "index.html"
    page.write_text('<style>.a{color:#0B1B3F}.b{background:rgba(0,0,0,.4)}.c{color:var(--text-default)}</style>\n'
                    '<a href="#top">x</a> &#x2014; <div id="a1b2c3"></div>\n')
    mark = site / "mark.svg"
    mark.write_text('<svg><path fill="#e4572e"/><path fill="#FF00FF"/></svg>')
    res = vt.lint_files([page, mark], v)
    assert [i[1] for i in res[str(page)]] == ["#0B1B3F", "rgba(0,0,0,.4)"]
    assert [i[1] for i in res[str(mark)]] == ["#FF00FF"]


def test_lint_skips_the_pre_vault_stages(tmp_path):
    """Territory boards and mark exploration are made before the vault exists."""
    v = filled(tmp_path)
    job = v.parent
    literal = '<style>.a{color:#FF00FF}</style>'
    made = {}
    for rel in ("20-territories/T1/board.html", "30-identity/exploration/route-a.svg",
                "30-identity/mark/lockup.svg", "50-applications/index.html"):
        f = job / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text('<svg><path fill="#FF00FF"/></svg>' if f.suffix == ".svg" else literal)
        made[rel] = f
    res = vt.lint_files(list(made.values()), v)
    flagged = {rel for rel, f in made.items() if str(f) in res}
    assert flagged == {"30-identity/mark/lockup.svg", "50-applications/index.html"}
    assert vt.lint_skip(made["20-territories/T1/board.html"])
    assert not vt.lint_skip(job / "30-identity" / "system.md")


def test_hook_lint_is_quiet_in_the_pre_vault_stages(tmp_path):
    v = filled(tmp_path)
    job = v.parent
    (job / "studio-job.json").write_text(json.dumps({"brand_source": "vault"}))
    f = job / "20-territories" / "T2" / "board.html"
    f.parent.mkdir(parents=True)
    f.write_text(".hero{background:#123456}")
    payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(f)}, "cwd": str(job)})
    r = subprocess.run([sys.executable, str(SCRIPT), "hook-lint"], input=payload, capture_output=True, text=True)
    assert r.stdout == ""


def test_hook_lint(tmp_path):
    v = filled(tmp_path)
    job = v.parent
    (job / "studio-job.json").write_text(json.dumps({"brand_source": "vault"}))
    f = job / "50-applications" / "hero.css"
    f.parent.mkdir(parents=True)
    f.write_text(".hero{background:#123456}")
    payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(f)}, "cwd": str(job)})
    r = subprocess.run([sys.executable, str(SCRIPT), "hook-lint"], input=payload, capture_output=True, text=True)
    assert "#123456" in json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
    (job / "studio-job.json").write_text(json.dumps({"brand_source": "external:ntt-data-brand"}))
    r = subprocess.run([sys.executable, str(SCRIPT), "hook-lint"], input=payload, capture_output=True, text=True)
    assert r.stdout == ""


def test_the_lint_skips_a_packaged_territory_board_too(tmp_path):
    """CYPRESS: Delivery copies the boards to 99-handover/territories/. They are
    records of the direction stage, made before the brand had its own colours, and a
    blocking gate lint that fires on them has no fix except being switched off."""
    for path in ("20-territories/T1/board.html",
                 "99-handover/territories/T1/board.html",
                 "99-handover/territories/T1/board.md"):
        assert vt.lint_skip(Path("job") / path), path
    for path in ("50-applications/page.css",
                 "30-identity/client/design-system.html",
                 "99-handover/applications/tessel-landing-v1.html"):
        assert not vt.lint_skip(Path("job") / path), path
