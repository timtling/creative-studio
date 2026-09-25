"""Tests for skills/producer/scripts/studio.py. Run: python3 -m pytest tests -q"""
import datetime as dt
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "producer" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "image-generation" / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import studio as st  # noqa: E402
import imagekit as ik  # noqa: E402
from test_vault import filled  # noqa: E402


@pytest.fixture
def job(tmp_path, monkeypatch):
    monkeypatch.delenv("STUDIO_JOB", raising=False)
    j = tmp_path / "job"
    assert st.main(["init", str(j), "--client", "Tessel", "--job", "Brand Sprint", "--track", "sprint",
                    "--codename", "heron", "--due", "2026-10-23"]) == 0
    return j


def fill(p: Path):
    p.write_text(st.MARKER.sub("Filled.", p.read_text()))


def validate_intake(job, answers=3):
    """Intake validation as the studio-intake skill leaves it."""
    p = job / "00-intake" / "validation.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text("# Intake validation\n")
    fill(p)
    body = p.read_text() + "\n## Questions asked\n\n" + "".join(
        f"{i}. **Q:** Question {i}?\n   **A:** Tim's answer {i}.\n\n" for i in range(1, answers + 1))
    p.write_text(body)


def sign(job, who="Tim Ling"):
    """The named human's final refinement pass on the mark."""
    (job / "30-identity").mkdir(exist_ok=True)
    (job / "30-identity" / "refinement-log.md").write_text(
        f"- 2026-10-06 · v4 · refined by: {who} · raised the crossbar; it filled in at 16px\n")


def approve(job, gate):
    if gate == "brief":
        validate_intake(job)
    assert st.main(["gate", "raise", gate, "--job", str(job)]) == 0
    assert st.main(["gate", "record", gate, "--status", "approved", "--job", str(job)]) == 0


def test_init_layout(job):
    d = st.load(job)
    assert d["track"] == "sprint" and d["stage"] == "intake" and d["codename"] == "heron"
    assert [g for g in d["gates"]] == ["brief", "direction", "system", "final"]
    assert d["gates"]["system"]["rounds_allowed"] == 2
    for f in ("00-intake", "10-strategy", "20-territories", "30-identity", "50-applications", "99-handover",
              "gates", "vault", "assets/raw", "01-brief.md", "02-scope.md", "90-decisions.md"):
        assert (job / f).exists(), f
    assert "| system | identity | 2 |" in (job / "02-scope.md").read_text()


def test_workdays_and_backplan():
    assert st.add_workdays(dt.date(2026, 9, 25), 1) == dt.date(2026, 9, 28)  # Fri -> Mon
    assert st.add_workdays(dt.date(2026, 9, 28), -1) == dt.date(2026, 9, 25)
    rows, info = st.plan_dates("sprint", dt.date(2026, 9, 26), dt.date(2026, 10, 23))  # Saturday start
    assert rows[0]["start"] == "2026-09-28" and rows[-1]["end"] == "2026-10-12" and info["working_days"] == 11
    assert info["buffer_days"] == 9 and info["fits"] is True
    assert all(dt.date.fromisoformat(r["start"]).weekday() < 5 for r in rows)
    assert st.workdays_between(dt.date(2026, 9, 25), dt.date(2026, 9, 28)) == 1


def test_plan_flags_a_date_that_does_not_fit(job):
    assert st.main(["plan", "--start", "2026-10-20", "--job", str(job)]) == 2
    assert "does not fit" in (job / "03-plan.md").read_text()
    assert st.load(job)["plan"]["fits"] is False
    assert st.main(["plan", "--start", "2026-09-28", "--job", str(job)]) == 0


def test_brief_gate_needs_filled_documents(job):
    st.main(["plan", "--start", "2026-09-28", "--job", str(job)])
    probs = st.readiness(job, st.load(job), "brief")
    assert any("01-brief.md" in p for p in probs) and any("02-scope.md" in p for p in probs)
    assert st.main(["gate", "raise", "brief", "--job", str(job)]) == 1
    fill(job / "01-brief.md")
    fill(job / "02-scope.md")
    validate_intake(job)
    assert st.readiness(job, st.load(job), "brief") == []
    approve(job, "brief")
    assert st.load(job)["stage"] == "strategy"


def test_order_territories_and_vault(job, tmp_path):
    st.main(["plan", "--start", "2026-09-28", "--job", str(job)])
    probs = st.readiness(job, st.load(job), "direction")
    assert any("gate 'brief'" in p for p in probs)
    fill(job / "01-brief.md")
    fill(job / "02-scope.md")
    approve(job, "brief")
    (job / "10-strategy" / "positioning.md").write_text("x")
    for t in ("T1", "T2"):
        (job / "20-territories" / t).mkdir()
        (job / "20-territories" / t / "board.md").write_text("x")
    assert any("2 territories" in p for p in st.readiness(job, st.load(job), "direction"))
    (job / "20-territories" / "T3").mkdir()
    (job / "20-territories" / "T3" / "board.md").write_text("x")
    approve(job, "direction")
    (job / "30-identity" / "marks.md").write_text("x")
    assert any("vault/tokens.json is missing" in p for p in st.readiness(job, st.load(job), "system"))
    v = filled(tmp_path / "v")
    (job / "vault" / "tokens.json").write_text((v / "tokens.json").read_text())
    sign(job)
    assert st.readiness(job, st.load(job), "system") == []


def test_system_gate_needs_a_named_human_on_the_mark(job, tmp_path):
    """The agent prepares the master; a person makes the final pass and the log says who."""
    log = job / "30-identity" / "refinement-log.md"
    problems = lambda: [x for x in st.readiness(job, st.load(job), "system") if "refinement-log" in x]
    (job / "30-identity" / "marks.md").write_text("x")
    (job / "vault" / "tokens.json").write_text((filled(tmp_path / "v") / "tokens.json").read_text())

    assert any("refinement-log.md is missing" in p for p in problems())

    log.write_text("# Refinement\n\nWe refined the mark a lot.\n")
    assert any("no refinement entries" in p for p in problems()), "prose is not a log"

    log.write_text("- 2026-10-05 · v2 · refined by: the agent · thinned the crossbar\n"
                   "- 2026-10-05 · v3 · refined by: TBC · closed the counter\n")
    assert any("names no person" in p for p in problems()), "the agent cannot sign for the final pass"

    log.write_text(log.read_text() + "- 2026-10-06 · v4 · refined by: Tim Ling · raised the crossbar; it filled in at 16px\n")
    assert problems() == []


@pytest.mark.parametrize("who", [
    "<name or role>", "[Name]", "{{who}}", "TODO", "TBC", "xxx",
    "the identity designer", "Identity designer (role)", "our copywriter",
    "Claude", "the agent", "AI", "a designer", "someone",
])
def test_a_placeholder_or_a_role_is_not_a_named_human(who):
    """The check protects the client's rights in the mark: a template's own
    example, or the role that prepared the master, must never satisfy it."""
    assert not st._person_name(who)


@pytest.mark.parametrize("who", ["Tim Ling", "Tim", "Jo", "J. Ainsworth", "Aoife Ni Bhriain",
                                 "Mary-Jane O'Connor"])
def test_a_real_name_passes(who):
    assert st._person_name(who)


def test_placeholder_in_the_log_does_not_open_the_system_gate(job, tmp_path):
    """Regression: the first version accepted any text after 'refined by:', so a
    format example left in the log opened the gate."""
    (job / "30-identity" / "marks.md").write_text("x")
    (job / "vault" / "tokens.json").write_text((filled(tmp_path / "v") / "tokens.json").read_text())
    log = job / "30-identity" / "refinement-log.md"
    problems = lambda: [x for x in st.readiness(job, st.load(job), "system") if "refinement-log" in x]

    log.write_text("- 2026-10-05 · v1 · refined by: Identity designer · derived the mark\n"
                   "- 2026-10-06 · v2 · refined by: <name or role> · <what changed and why>\n")
    assert any("names no person" in p for p in problems())
    assert any("<name or role>" in p for p in problems()), "the message should name what it found"

    log.write_text(log.read_text().replace("<name or role> · <what changed and why>",
                                           "Tim Ling · kerned the wordmark; the S was tight"))
    assert problems() == []


SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 40">{}</svg>'
BAR = '<rect x="{x}" y="10" width="20" height="20" fill="#17191a"/>'


def _write_mark(job, version, x):
    d = job / "30-identity" / "mark"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"tessel-wordmark-v{version}.svg").write_text(SVG.format(BAR.format(x=x)))


def test_png_decoder_round_trips_a_real_png(tmp_path):
    """The comparison is worthless if the decoder is: check it against a known image."""
    png = tmp_path / "x.png"
    svg = tmp_path / "x.svg"
    svg.write_text(SVG.format(BAR.format(x=10)))
    if st.renderer() is None:
        pytest.skip("no SVG renderer on this machine")
    assert st.render_differs(svg, svg) is False       # a file never differs from itself


def test_a_pass_that_changed_nothing_is_refused(job, tmp_path):
    """Cypress: a hand file saved from a real editor, logged in good faith, and
    geometrically identical to the version before it."""
    if st.renderer() is None:
        pytest.skip("no SVG renderer on this machine")
    (job / "vault" / "tokens.json").write_text((filled(tmp_path / "v") / "tokens.json").read_text())
    log = job / "30-identity" / "refinement-log.md"
    problems = lambda: [x for x in st.readiness(job, st.load(job), "system") if "30-identity" in x]

    _write_mark(job, 1, 10)
    _write_mark(job, 2, 10)                            # saved, but nothing moved
    log.write_text("- 2026-10-06 · v2 · refined by: Tim Ling · kerned the wordmark\n")
    assert any("renders identically" in p for p in problems())
    assert any("v2" in p for p in problems())

    _write_mark(job, 2, 16)                            # re-saved, this time with the change
    assert problems() == []


def test_effect_check_only_judges_person_attributed_passes(job, tmp_path):
    """An agent's own pass is not the thing being checked, so an identical render is not a finding."""
    if st.renderer() is None:
        pytest.skip("no SVG renderer on this machine")
    (job / "vault" / "tokens.json").write_text((filled(tmp_path / "v") / "tokens.json").read_text())
    _write_mark(job, 1, 10)
    _write_mark(job, 2, 10)
    (job / "30-identity" / "refinement-log.md").write_text(
        "- 2026-10-05 · v2 · refined by: Identity designer · rebuilt the master\n"
        "- 2026-10-06 · v3 · refined by: Tim Ling · kerned it\n")
    # v3 has no file pair to compare, and v2 is the agent's: no effect finding either way
    assert not any("renders identically" in p for p in st.readiness(job, st.load(job), "system"))


def test_effect_check_is_silent_without_a_renderer(job, tmp_path, monkeypatch):
    """On a machine with no renderer the tool checks attribution and says nothing else,
    rather than blocking work it cannot actually assess."""
    monkeypatch.setattr(st, "renderer", lambda: None)
    (job / "vault" / "tokens.json").write_text((filled(tmp_path / "v") / "tokens.json").read_text())
    _write_mark(job, 1, 10)
    _write_mark(job, 2, 10)
    (job / "30-identity" / "refinement-log.md").write_text(
        "- 2026-10-06 · v2 · refined by: Tim Ling · kerned the wordmark\n")
    assert [x for x in st.readiness(job, st.load(job), "system") if "30-identity" in x] == []


def test_identity_check_is_tied_to_the_stage_not_the_gate_name(tmp_path, monkeypatch):
    """product-ui has a system gate too, but it closes screens: no mark, no log needed."""
    monkeypatch.delenv("STUDIO_JOB", raising=False)
    j = tmp_path / "ui"
    assert st.main(["init", str(j), "--client", "Tessel", "--job", "Product UI", "--track", "product-ui"]) == 0
    (j / "30-screens" / "screens.md").write_text("x")
    (j / "vault" / "tokens.json").write_text((filled(tmp_path / "v") / "tokens.json").read_text())
    assert not any("refinement-log" in p for p in st.readiness(j, st.load(j), "system"))


def test_intake_validation_blocks_the_brief_gate(job):
    """A brief written first and validated afterwards does not pass."""
    fill(job / "01-brief.md")
    fill(job / "02-scope.md")
    st.main(["plan", "--start", "2026-09-28", "--job", str(job)])
    v = job / "00-intake" / "validation.md"
    problems = lambda: [p for p in st.readiness(job, st.load(job), "brief") if "validation" in p]

    assert v.exists(), "init writes the validation file so it is filled as intake happens"
    assert any("unfilled prompt" in p for p in problems())

    v.unlink()
    assert any("is missing" in p for p in problems())

    validate_intake(job, answers=2)
    assert any("records 2 answered question(s)" in p for p in problems())

    validate_intake(job, answers=3)
    assert problems() == []
    assert st.main(["gate", "raise", "brief", "--job", str(job)]) == 0


@pytest.mark.parametrize("answer,counts", [
    ("The budget is £30k to £45k.", True),
    ("unanswered", False),
    ("TBC", False),
    ("{{Tim's answer}}", False),
    ("<his words>", False),
    ("-", False),
    ("Yes.", True),
])
def test_only_real_answers_count(tmp_path, answer, counts):
    p = tmp_path / "validation.md"
    p.write_text(f"1. **Q:** Something?\n   **A:** {answer}\n")
    assert bool(st.answered_questions(p)) is counts


def test_the_producer_cannot_invent_the_competitive_set():
    """The checklist and the brief template both say competitors are client-named only."""
    tpl = (ROOT / "skills" / "producer" / "assets" / "templates").resolve()
    assert "Only the competitors the client named" in (tpl / "brief.md").read_text()
    v = (tpl / "validation.md").read_text()
    assert "Competitors are only ever `supplied` or `missing`" in v
    assert "as the client named them" in (ROOT / "skills" / "studio-intake" / "SKILL.md").read_text()


def test_rework_and_decisions_log(job):
    fill(job / "01-brief.md")
    fill(job / "02-scope.md")
    validate_intake(job)
    st.main(["plan", "--start", "2026-09-28", "--job", str(job)])
    st.main(["gate", "raise", "brief", "--job", str(job)])
    with pytest.raises(SystemExit):
        st.main(["gate", "record", "brief", "--status", "rework", "--job", str(job)])  # needs a note
    st.main(["gate", "record", "brief", "--status", "rework", "--note", "Audience too broad", "--job", str(job)])
    d = st.load(job)
    assert d["gates"]["brief"]["status"] == "rework" and d["gates"]["brief"]["reworks"] == 1 and d["stage"] == "intake"
    assert 'Tim: "Audience too broad"' in (job / "90-decisions.md").read_text()


def test_rounds_and_change_requests(job):
    assert st.main(["round", "system", "--note", "logo weight", "--job", str(job)]) == 0
    assert st.main(["round", "system", "--job", str(job)]) == 0
    assert st.main(["round", "system", "--job", str(job)]) == 1  # allowance of 2 used
    assert st.main(["round", "system", "--change-request", "--job", str(job)]) == 0
    st.main(["feedback", "--gate", "system", "--class", "new-request", "--text", "Add a mascot", "--job", str(job)])
    st.main(["feedback", "--gate", "system", "--class", "taste", "--text", "Prefer blue", "--job", str(job)])
    d = st.load(job)
    assert [c["id"] for c in d["change_requests"]] == ["CR-001", "CR-002"]
    assert d["gates"]["system"]["rounds_used"] == 2
    lines = (job / "90-feedback.jsonl").read_text().splitlines()
    assert json.loads(lines[0])["cr"] == "CR-002" and json.loads(lines[1])["class"] == "taste"
    st.main(["cr", "close", "CR-002", "--status", "declined", "--note", "Out of scope", "--job", str(job)])
    assert st.load(job)["change_requests"][1]["status"] == "declined"


def test_status_lines(job):
    lines = st.status_lines(job, st.load(job))
    assert lines[0].startswith("heron (Brand Sprint): stage intake")
    assert any(l.startswith("Next: gate 'brief'") for l in lines)


def test_commission_track(tmp_path):
    j = tmp_path / "c"
    st.main(["init", str(j), "--client", "NTT DATA", "--job", "Barbet cover", "--track", "commission",
             "--requester", "engagement-studio", "--requester-ref", "barbet", "--brand", "external:ntt-data-brand"])
    d = st.load(j)
    assert d["requester"] == {"type": "engagement-studio", "ref": "barbet"} and d["brand_source"] == "external:ntt-data-brand"
    assert (j / "00-intake" / "commission.md").exists() and (j / "50-make").exists()
    probs = st.readiness(j, d, "brief")
    assert any("commission.md" in p for p in probs) and not any("existing brand" in p for p in probs)


def test_requires_track_needs_a_brand(tmp_path):
    j = tmp_path / "lk"
    st.main(["init", str(j), "--client", "Tessel", "--job", "Launch", "--track", "launch-kit"])
    assert any("needs an existing brand" in p for p in st.readiness(j, st.load(j), "brief"))


def test_imagekit_reads_a_studio_job(job, monkeypatch):
    monkeypatch.chdir(job)
    assert ik.find_job(job) == job
    reason = ik.pre_check(job, "mcp__Recraft__generate_image", {"prompt": "x"})
    assert "paid plan" in reason
    ik.main(["confirm-recraft-paid", "--plan", "Pro", "--job", str(job)])
    assert ik.pre_check(job, "mcp__Recraft__generate_image", {"prompt": "x"}) is None
    assert st.load(job)["track"] == "sprint"  # imagekit writes did not clobber studio state
