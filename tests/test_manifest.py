"""Checks the Claude app's plugin validator applies at upload, so a package that
would be rejected fails here first."""
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = sorted((ROOT / "skills").glob("*/SKILL.md"))


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, f"{path} has no frontmatter"
    return yaml.safe_load(m.group(1))


def test_manifest_present_and_valid():
    data = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert data["name"] and data["version"]


def test_skills_found():
    assert SKILLS


def test_skill_descriptions_have_no_angle_brackets():
    # The app rejects any skill whose description contains XML-like tags, e.g. "<codename>".
    bad = [str(p.relative_to(ROOT)) for p in SKILLS
           if re.search(r"[<>]", str(frontmatter(p).get("description", "")))]
    assert not bad, f"angle brackets in description: {bad}"


def test_every_skill_has_name_and_description():
    for p in SKILLS:
        fm = frontmatter(p)
        assert fm.get("name") and fm.get("description"), p
