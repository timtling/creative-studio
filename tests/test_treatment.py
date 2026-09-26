"""Tests for skills/studio-standards/scripts/treatment-check.py: the timidity test.

The reach rule had no failing test, and the author's own claim that a reach is
load-bearing is the least reliable evidence available. These cover the Cypress case
the script was built from - three boards diverging on subject and agreeing on every
treatment dimension - and the case it must not fire on.
Run: python3 -m pytest tests -q
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "studio-standards" / "scripts"))
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "treatment_check", ROOT / "skills" / "studio-standards" / "scripts" / "treatment-check.py")
tc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tc)

RESTRAINED = """<style>
body{{background:#F4F1EA;color:#17191A}}
.accent{{color:{accent}}}
</style>
<h1>{title}</h1><p>A different bet entirely.</p>
"""
REACH = """<style>
body{background:#1B0E2B;color:#F7E9D0}
.plane{background:linear-gradient(120deg,#E4572E,#2E8B7A);border-radius:18px;
       box-shadow:0 12px 40px rgba(0,0,0,.5)}
.grain{background-image:repeating-linear-gradient(45deg,#E4572E 0 2px,transparent 2px 4px)}
.b{color:#F2C14E}.c{color:#3D8BFD}
</style>
<h1>Overprint</h1>
"""


def boards(tmp_path, *texts):
    tmp_path.mkdir(parents=True, exist_ok=True)
    out = []
    for i, t in enumerate(texts, 1):
        d = tmp_path / f"T{i}"
        d.mkdir()
        (d / "board.html").write_text(t)
        out.append(d / "board.html")
    return out


def test_three_boards_in_one_band_of_restraint_are_a_finding(tmp_path):
    """CYPRESS: all three boards shared the ground, the ink, the absence of radius,
    gradient, shadow and texture. It passed the shared-logo rule and failed the reach
    rule, and nobody noticed until after handover."""
    paths = boards(tmp_path,
                   RESTRAINED.format(accent="#2E8B7A", title="The Record"),
                   RESTRAINED.format(accent="#2E8B7A", title="The Handover"),
                   RESTRAINED.format(accent="#2E8B7A", title="The Margin"))
    res = tc.compare([tc.treatment(p) for p in paths])
    assert res["finding"], res
    assert res["agreed_count"] == 7 and res["of"] == 7
    assert tc.main([str(p) for p in paths]) == 1, "a finding exits non-zero"


def test_five_of_seven_is_the_threshold(tmp_path):
    assert tc.AGREEMENT_FINDING == 5
    paths = boards(tmp_path,
                   RESTRAINED.format(accent="#2E8B7A", title="One"),
                   RESTRAINED.format(accent="#2E8B7A", title="Two"),
                   REACH)
    res = tc.compare([tc.treatment(p) for p in paths])
    assert res["agreed_count"] < tc.AGREEMENT_FINDING, res["agreed"]
    assert not res["finding"], "one board that actually reaches clears the rule"
    assert tc.main([str(p) for p in paths]) == 0


def test_it_reads_the_dimensions_off_the_board(tmp_path):
    reach = boards(tmp_path, REACH)[0]
    t = tc.treatment(reach)
    assert t["ground"] in ("light", "mid", "near-white") and t["ink"] in ("dark", "near-black")
    assert t["gradient"] == "yes" and t["shadow"] == "yes" and t["texture"] == "yes"
    assert t["radius"] == "yes" and t["chroma"] == "three or more"
    calm = boards(tmp_path / "b", RESTRAINED.format(accent="#2E8B7A", title="Calm"))[0]
    c = tc.treatment(calm)
    assert (c["gradient"], c["shadow"], c["texture"], c["radius"]) == ("no", "no", "no", "no")
    assert c["ground"] == "near-white" and c["ink"] == "near-black"


def test_editor_chrome_is_not_a_board_colour(tmp_path):
    """The same rule as the vault lint: an editor's canvas colour is not the palette."""
    p = boards(tmp_path, '<svg><sodipodi:namedview pagecolor="#ffffff" '
                         'inkscape:deskcolor="#d1d1d1" /><path fill="#0B1B3F"/></svg>')[0]
    assert tc.treatment(p)["ground"] != "near-white"


def test_it_needs_something_to_compare(tmp_path):
    p = boards(tmp_path, REACH)[0]
    import pytest
    with pytest.raises(SystemExit, match="at least two boards"):
        tc.main([str(p)])
    with pytest.raises(SystemExit, match="does not exist"):
        tc.main([str(p), str(tmp_path / "nope.html")])
