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
        "art-director", "copywriter", "creative-lead", "identity-designer", "strategist"}


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
