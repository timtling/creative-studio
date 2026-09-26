"""Tests for agents/*.md: the role definitions the Producer routes work to.

These are markdown, not code, so the tests guard the things that silently break
a job: an agent whose name does not match its file, a roster that names an agent
that does not exist, or a role that no longer loads the studio standards.
Run: python3 -m pytest tests -q
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AGENTS = sorted((ROOT / "agents").glob("*.md"))
ROSTER = (ROOT / "skills" / "producer" / "SKILL.md").read_text()


def front(p: Path) -> dict:
    """The frontmatter's top-level scalar keys. Enough for these checks."""
    t = p.read_text()
    assert t.startswith("---\n"), f"{p.name} has no frontmatter"
    block = t.split("\n---\n", 1)[0][4:]
    return {m[1]: m[2].strip() for m in re.finditer(r"^([a-z_]+):[ \t]*(.*)$", block, re.M)}


def test_agents_exist():
    assert {p.stem for p in AGENTS} == {
        "art-director", "builder", "copywriter", "creative-lead", "delivery",
        "identity-designer", "strategist"}


@pytest.mark.parametrize("p", AGENTS, ids=lambda p: p.stem)
def test_frontmatter(p):
    f = front(p)
    assert f["name"] == p.stem, f"{p.name}: name '{f.get('name')}' does not match the filename"
    assert f["model"] == "inherit"
    assert f["color"]
    assert f["description"] == "|", f"{p.name}: description should be a literal block for the examples"


@pytest.mark.parametrize("p", AGENTS, ids=lambda p: p.stem)
def test_description_has_examples(p):
    t = p.read_text()
    head = t.split("\n---\n", 1)[0]
    assert head.count("<example>") >= 2, f"{p.name}: agent descriptions carry at least two examples"
    assert head.count("<example>") == head.count("</example>")
    assert head.count("<commentary>") == head.count("<example>")


@pytest.mark.parametrize("p", AGENTS, ids=lambda p: p.stem)
def test_loads_the_standards(p):
    body = p.read_text().split("\n---\n", 1)[1]
    assert "studio-standards" in body, f"{p.name}: every role loads studio-standards"
    assert "Producer" in body, f"{p.name}: every role reports to the Producer"


@pytest.mark.parametrize("p", AGENTS, ids=lambda p: p.stem)
def test_named_in_the_roster(p):
    assert f"`{p.stem}`" in ROSTER, f"{p.stem} is not named in the Producer's roster"


def test_roster_names_only_agents_that_exist():
    rows = [l for l in ROSTER.splitlines() if l.startswith("| ") and "|" in l[2:]]
    named = {m for l in rows for m in re.findall(r"\(`([a-z-]+)`\)", l)}
    assert named, "the roster names no agents"
    assert named <= {p.stem for p in AGENTS}, f"roster names missing agents: {named - {p.stem for p in AGENTS}}"


# --------------------------------------------------------------------------- 0.3.7
#
# These are markdown rules, so the test is that the rule is present and lands on the
# role that can act on it. Each names the Cypress failure it came from.

STANDARDS = (ROOT / "skills" / "studio-standards" / "SKILL.md").read_text()
GATE = (ROOT / "skills" / "studio-gate" / "SKILL.md").read_text()
PACK = (ROOT / "skills" / "producer" / "assets" / "templates" / "gate-pack.md").read_text()


def test_cross_read_is_an_operating_rule_and_reaches_the_gate():
    """Three roles, one sourcing failure, none caught by its author."""
    assert "**Cross-read at every gate.**" in STANDARDS
    assert "never its own" in STANDARDS
    assert "does not require anyone to be more careful" in STANDARDS
    assert "studio.py cross-read" in STANDARDS and "studio.py cross-read" in GATE
    assert "studio.py cross-read" in ROSTER


def test_the_source_that_governs_the_question_is_a_rule():
    """02-scope.md was the right source in two of the three failures and the wrong one
    in the third, so the fix cannot be a document hierarchy."""
    assert "Name the question, then name the source that governs it" in STANDARDS
    assert "Completeness and content need **different sources**" in STANDARDS
    assert "generate it from them and fail the build" in STANDARDS


def test_the_stopping_rule_is_a_standard_and_reaches_the_producer_and_delivery():
    """Cypress ran four verification passes with no rule saying when to stop."""
    assert "Checking stops when a pass finds nothing, not when the budget runs out" in STANDARDS
    assert "studio.py verify-close" in STANDARDS
    assert "studio.py verify-pass" in ROSTER
    assert "studio.py verify-pass" in (ROOT / "agents" / "delivery.md").read_text()
    assert "verify-close" in (ROOT / "skills" / "studio-close" / "SKILL.md").read_text()


def test_a_negation_is_a_claim_lands_on_the_copywriter_and_the_strategist():
    """Three instances in one evening, and the claim ceilings table let all three
    through because every row guarded a positive form."""
    assert "**A negation is still a claim.**" in STANDARDS
    assert "turn the negation into its positive" in STANDARDS.lower()
    assert "Apply the negation test hardest where the register is warmest" in STANDARDS
    assert "who handles the copy next" in STANDARDS
    cw = (ROOT / "agents" / "copywriter.md").read_text()
    assert "A negation is still a claim" in cw and "where the register is warmest" in cw
    strat = (ROOT / "agents" / "strategist.md").read_text()
    assert "Never and a Permitted form" in strat
    assert 'what the answer does not give' in strat, "the phrasing that invited the failure is named"


def test_the_strategist_names_what_a_constraint_does_not_forbid():
    """Cypress went further than the register required with nothing to stop it."""
    strat = (ROOT / "agents" / "strategist.md").read_text()
    assert "does not forbid" in strat
    assert "saturation, scale, depth, density or colour" in strat


def test_timidity_has_a_script_and_the_creative_lead_must_run_it():
    assert (ROOT / "skills" / "studio-standards" / "scripts" / "treatment-check.py").exists()
    assert "treatment-check.py" in STANDARDS
    assert "five of the seven" in STANDARDS
    cl = (ROOT / "agents" / "creative-lead.md").read_text()
    assert "treatment-check.py" in cl and "five of seven is a finding you must argue" in cl


def test_the_transplant_line_is_in_the_pack_and_the_gate():
    """T1's vermilion got 'n/a', so the T4 eval had to re-raise red from scratch."""
    assert "## Transplant" in PACK
    assert "Nothing to transplant" in PACK
    assert "transplant" in GATE.lower()
    assert "a departure needs a ruling even in a territory he does not choose" in GATE
    cl = (ROOT / "agents" / "creative-lead.md").read_text()
    assert "still needs a ruling" in cl


def test_the_final_pack_has_a_scope_section_it_cannot_write_from_memory():
    assert "## Scope" in PACK
    assert "not rewrite it from what the roles reported" in PACK
    assert "scope-audit" in GATE and "scope-audit" in ROSTER


def test_delivery_audits_subject_by_subject():
    d = (ROOT / "agents" / "delivery.md").read_text()
    assert "subject by subject" in d
    assert "one line per **promise**" in d
    assert "missing voice is a row that passes and a promise that failed" in d
    assert "property of the thing, not by its label" in d


def test_the_vault_lint_is_a_gate_step_because_the_hook_may_not_fire():
    assert "Run the vault lint yourself before every gate" in ROSTER
    vault = (ROOT / "skills" / "brand-vault" / "SKILL.md").read_text()
    assert "Do not rely on the hook" in vault
    assert "device shell" in vault and "device shell" in ROSTER
    assert "editor chrome is skipped" in vault
