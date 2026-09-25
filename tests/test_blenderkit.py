"""Tests for skills/blender-3d/scripts/blenderkit.py and the 3D decision rule.

The CLI half runs anywhere; the Blender half only runs inside Blender, so these
cover what a machine without Blender can actually check: the presets, the plan,
the colour-provenance rules, and that the rule is wired through the roster.
Run: python3 -m pytest tests -q
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "blender-3d" / "scripts"))
import blenderkit as bk  # noqa: E402


def test_the_view_transform_is_standard():
    """Blender's default desaturates every brand colour, so this is not a preference."""
    assert bk.VIEW_TRANSFORM == "Standard"
    for name in bk.PRESETS:
        assert bk.preset(name)["view_transform"] == "Standard"


def test_draft_is_cheaper_than_final_in_every_dimension():
    d, f = bk.PRESETS["draft"], bk.PRESETS["final"]
    assert d["samples"] < f["samples"] and d["width"] < f["width"] and d["height"] < f["height"]


@pytest.mark.parametrize("scene,expected", [
    ("van", [3, 10, 25]), ("sign", [2, 10]), ("card", [0.3])])
def test_touchpoints_are_judged_at_the_distance_they_are_seen_from(scene, expected):
    assert bk.distances(scene, None) == expected
    assert bk.distances(scene, "1,2.5") == [1.0, 2.5]


def test_plan_refuses_without_the_vault_build(tmp_path, capsys):
    """Colours come from the vault, so a job without one cannot render on-brand."""
    job = tmp_path / "job"
    (job / "vault" / "build").mkdir(parents=True)
    a = type("A", (), {"job": str(job), "scene": "van", "preset": "draft", "distances": None})
    assert bk.cmd_plan(a) == 1
    assert "MISSING" in capsys.readouterr().out
    (job / "vault" / "build" / "blender.json").write_text("{}")
    assert bk.cmd_plan(a) == 0


def test_load_colours_will_not_guess(tmp_path):
    with pytest.raises(SystemExit) as e:
        bk.load_colours(tmp_path)
    assert "vault.py build" in str(e.value)


def test_verify_catches_the_render_that_cannot_be_reproduced(tmp_path, capsys):
    png = tmp_path / "van-draft-25m.png"
    png.write_bytes(b"")
    a = type("A", (), {"render": str(png)})
    assert bk.cmd_verify(a) == 1
    assert "cannot be reproduced" in capsys.readouterr().out


def test_verify_catches_the_wrong_view_transform(tmp_path, capsys):
    png = tmp_path / "van-draft-25m.png"
    png.write_bytes(b"")
    build = tmp_path / "blender.json"
    build.write_text("{}")
    png.with_suffix(".json").write_text(json.dumps(
        {"view_transform": "AgX", "vault_build": str(build)}))
    a = type("A", (), {"render": str(png)})
    assert bk.cmd_verify(a) == 1
    assert "desaturated" in capsys.readouterr().out

    png.with_suffix(".json").write_text(json.dumps(
        {"view_transform": "Standard", "vault_build": str(build)}))
    assert bk.cmd_verify(a) == 0


def test_report_lists_what_was_rendered(tmp_path, capsys):
    job = tmp_path / "job"
    d = job / "assets" / "3d" / "van"
    d.mkdir(parents=True)
    (d / "van-draft-25m.json").write_text(json.dumps(
        {"scene": "van", "distance_m": 25, "preset": "draft", "samples": 32, "view_transform": "Standard"}))
    assert bk.cmd_report(type("A", (), {"job": str(job)})) == 0
    out = (job / "assets" / "3d" / "renders.md").read_text()
    assert "van-draft-25m.png" in out and "25 m" in out and "Standard" in out


# --------------------------------------------------------------------- the rule

STANDARDS = (ROOT / "skills" / "studio-standards" / "SKILL.md").read_text()


def test_three_reasons_and_only_three():
    assert "## When 3D is allowed" in STANDARDS
    for reason in ("physical touchpoint", "spatial territory idea", "Explanation that needs space"):
        assert reason in STANDARDS
    assert "declared departure" in STANDARDS


@pytest.mark.parametrize("agent,must_say", [
    ("strategist", "touchpoints.md"),
    ("creative-lead", "Dimension"),
    ("identity-designer", "blender-3d"),
    ("builder", "the direction gate approved"),
    ("art-director", "direction gate approved"),
])
def test_the_rule_reaches_every_role_that_could_break_it(agent, must_say):
    assert must_say in (ROOT / "agents" / f"{agent}.md").read_text()


def test_the_direction_gate_states_the_plan():
    assert "## The 3D plan" in (ROOT / "skills" / "producer" / "assets" / "templates" / "gate-pack.md").read_text()
    assert "the 3D plan" in (ROOT / "skills" / "studio-gate" / "SKILL.md").read_text()
