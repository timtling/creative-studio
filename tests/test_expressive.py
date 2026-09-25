"""Tests for the expressive range layer: the reach rule, the sources file,
the expressive vault tokens and their lint, and the expression budget.

Run: python3 -m pytest tests -q
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "brand-vault" / "scripts"))
import vault as vt  # noqa: E402

STANDARDS = (ROOT / "skills" / "studio-standards" / "SKILL.md").read_text()
SOURCES = (ROOT / "skills" / "studio-standards" / "references" / "art-sources.md").read_text()
LEAD = (ROOT / "agents" / "creative-lead.md").read_text()


# --------------------------------------------------------------- the reach rule

def test_timidity_is_a_named_major_finding():
    for text in (STANDARDS, LEAD):
        assert "timidity" in text.lower()
        assert "Major finding" in text
    assert "still answers the positioning" in LEAD


def test_the_reach_rule_is_on_the_role_that_owns_territories():
    assert "art-sources.md" in LEAD
    assert "reach" in LEAD.lower()


def test_no_pitching_as_like_studio_x():
    assert '"like Studio X"' in LEAD and '"like Studio X"' in SOURCES


# ------------------------------------------------------------------- the sources

BENCHMARKS = {
    "DIA": "https://www.dia.studio/",
    "Studio Dumbar": "https://studiodumbar.com/",
    "Hey Studio": "https://heystudio.es/",
    "ManvsMachine": "https://mvsm.com/",
    "PORTO ROCHA": "https://www.portorocha.com/",
}


@pytest.mark.parametrize("studio,url", BENCHMARKS.items())
def test_every_benchmark_studio_is_present_with_its_site(studio, url):
    assert studio in SOURCES and url in SOURCES


@pytest.mark.parametrize("studio", BENCHMARKS)
def test_every_studio_has_three_to_five_numbered_principles(studio):
    section = SOURCES.split(f"### {studio}", 1)[1].split("\n### ", 1)[0]
    numbered = re.findall(r"^\d+\. \*\*", section, re.M)
    assert 3 <= len(numbered) <= 5, f"{studio} has {len(numbered)} principles"


@pytest.mark.parametrize("studio", BENCHMARKS)
def test_principles_link_the_project_they_came_from(studio):
    """A principle with no project behind it is an opinion."""
    section = SOURCES.split(f"### {studio}", 1)[1].split("\n### ", 1)[0]
    body = section.split("\n1. ", 1)[1]
    assert re.search(r"\]\(https?://", body), f"{studio}'s principles cite no linked project"


def test_it_says_where_it_could_not_look():
    """MVSM's case pages would not open; the file says so rather than inventing detail."""
    mvsm = SOURCES.split("### ManvsMachine", 1)[1].split("\n### ", 1)[0]
    assert "would not open" in mvsm


def test_art_practice_is_framed_as_principles_not_looks():
    assert "principle to take" in SOURCES and "never a look to copy" in SOURCES
    for movement in ("Constructivism", "Op art", "Albers", "Suprematism", "Bauhaus"):
        assert movement in SOURCES


# ----------------------------------------------------------- the expressive vault

TEMPLATE = json.loads((ROOT / "skills" / "brand-vault" / "assets" / "tokens.template.json").read_text())


@pytest.mark.parametrize("group", ["palette", "texture", "shape", "gradient", "depth"])
def test_the_expressive_layer_has_its_groups(group):
    assert group in TEMPLATE["expressive"]


def test_the_expressive_layer_sits_beside_the_functional_one_not_over_it():
    for functional in ("color", "text", "surface", "border", "type", "space", "motion"):
        assert functional in TEMPLATE
    assert "contrast" in TEMPLATE["expressive"]["$description"]


def test_texture_behind_body_text_is_flagged():
    css = (".entry-body{background:repeating-linear-gradient(45deg,#000,#000 2px,transparent 2px)}\n"
           "p{background-image:url(noise.svg)}\n"
           "td{background-image:url(grain.png)}\n")
    found = vt.lint_texture(css, ".css")
    assert len(found) == 3
    assert all("never sits under running text" in why for _, _, why in found)


def test_texture_on_a_hero_or_cover_is_the_point_and_is_not_flagged():
    css = (".hero{background-image:url(grain.png)}\n"
           ".cover{background:conic-gradient(red,blue)}\n"
           ".campaign-panel{background-image:url(overprint.png)}\n")
    assert vt.lint_texture(css, ".css") == []


def test_the_texture_rule_only_applies_where_css_can_exist():
    css = ".entry-body{background-image:url(noise.svg)}"
    assert vt.lint_texture(css, ".css")
    assert vt.lint_texture(css, ".svg") == []
    assert vt.lint_texture(css, ".py") == []


def test_the_expressive_layer_is_optional(tmp_path):
    """A job whose expression budget keeps every surface calm has nothing to put in it."""
    from test_vault import filled
    v = filled(tmp_path)
    errs, _ = vt.validate(vt.load(v))
    assert errs == [], "an unfilled expressive layer must not block a valid vault"
    assert vt.main(["build", str(v)]) == 0

    tree = json.loads((v / "tokens.json").read_text())
    tree["expressive"]["palette"]["1"]["$value"] = "#B23520"
    (v / "tokens.json").write_text(json.dumps(tree))
    errs, _ = vt.validate(vt.load(v))
    assert errs == [], "a filled expressive token must validate like any other"

    tree["expressive"]["palette"]["2"]["$value"] = "not-a-colour"
    (v / "tokens.json").write_text(json.dumps(tree))
    errs, _ = vt.validate(vt.load(v))
    assert any("expressive.palette.2" in e for e in errs), "a filled one is still type-checked"


def test_contrast_rules_are_untouched_by_the_expressive_layer():
    """The expressive layer must not have loosened the vault's own floor."""
    assert "text.default" in (ROOT / "skills" / "brand-vault" / "SKILL.md").read_text()
    src = (ROOT / "skills" / "brand-vault" / "scripts" / "vault.py").read_text()
    assert "4.5" in src, "the AA body-text threshold is still enforced"


# --------------------------------------------------------- the expression budget

def test_the_budget_names_both_sides_and_the_dial():
    assert "## The expression budget" in STANDARDS
    for surface in ("Covers", "campaigns", "packaging", "environments"):
        assert surface in STANDARDS
    for surface in ("Forms", "tables", "data", "body copy"):
        assert surface in STANDARDS
    assert "Start-ups: bold throughout" in STANDARDS
    assert "Corporates: bold in brand moments" in STANDARDS


def test_the_budget_never_overrides_accessibility():
    assert "never drawn through accessibility" in STANDARDS
    brief = (ROOT / "skills" / "producer" / "assets" / "templates" / "brief.md").read_text()
    assert "## Expression budget" in brief
    assert "never drawn through accessibility" in brief


def test_the_budget_reaches_intake_and_the_builder():
    validation = (ROOT / "skills" / "producer" / "assets" / "templates" / "validation.md").read_text()
    assert "Expression budget" in validation
    assert "Expression budget" in (ROOT / "skills" / "studio-intake" / "SKILL.md").read_text()
    assert "expression budget" in (ROOT / "agents" / "builder.md").read_text()
