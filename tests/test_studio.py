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


def cross_read(job, gate, by="delivery", of="producer"):
    """The cross-read every gate but brief now requires before it can be raised."""
    if gate == "brief":
        return
    assert st.main(["cross-read", gate, "--by", by, "--of", of,
                    "--against", "02-scope.md", "--job", str(job)]) == 0


def approve(job, gate):
    if gate == "brief":
        validate_intake(job)
    cross_read(job, gate)
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
    assert any("no cross-read recorded" in x for x in st.readiness(job, st.load(job), "system"))
    cross_read(job, "system")
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
BAR = '<rect x="{x}" y="10" width="20" height="20" fill="#0B1B3F"/>'   # ink in test_vault.PALETTE


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


def test_no_renderer_warns_in_the_pack_rather_than_passing_quietly(job, tmp_path, monkeypatch):
    """A silent pass reads as a verified one, so the gap is said out loud."""
    monkeypatch.setattr(st, "renderer", lambda: None)
    (job / "vault" / "tokens.json").write_text((filled(tmp_path / "v") / "tokens.json").read_text())
    _write_mark(job, 1, 10)
    _write_mark(job, 2, 10)
    (job / "30-identity" / "refinement-log.md").write_text(
        "- 2026-10-06 · v2 · refined by: Tim Ling · kerned the wordmark\n")

    assert [x for x in st.readiness(job, st.load(job), "system") if "30-identity" in x] == [], \
        "a warning must never block the gate"
    warns = st.gate_warnings(job, st.load(job), "system")
    assert len(warns) == 1 and warns[0].startswith("effect not verified: no renderer")
    assert "not** that the pass changed anything" in warns[0]

    validate_intake(job)
    fill(job / "01-brief.md"); fill(job / "02-scope.md")
    for g in ("brief", "direction"):
        st.main(["gate", "raise", g, "--job", str(job), "--force"])
        st.main(["gate", "record", g, "--status", "approved", "--job", str(job)])
    cross_read(job, "system")
    assert st.main(["gate", "raise", "system", "--job", str(job)]) == 0
    pack = (job / "gates" / "system.md").read_text()
    assert "## Not verified" in pack and "effect not verified: no renderer" in pack
    assert pack.index("## Not verified") < pack.index("## Trade-offs and risks")


def test_a_verified_pass_adds_no_warning(job, tmp_path):
    if st.renderer() is None:
        pytest.skip("no SVG renderer on this machine")
    (job / "vault" / "tokens.json").write_text((filled(tmp_path / "v") / "tokens.json").read_text())
    _write_mark(job, 1, 10)
    _write_mark(job, 2, 16)
    (job / "30-identity" / "refinement-log.md").write_text(
        "- 2026-10-06 · v2 · refined by: Tim Ling · kerned the wordmark\n")
    assert st.gate_warnings(job, st.load(job), "system") == []


def test_warnings_are_only_raised_where_they_mean_something(job):
    """No refinement log, no claim about effect: the brief gate says nothing."""
    assert st.gate_warnings(job, st.load(job), "brief") == []


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


def test_log_takes_its_time_from_the_clock_not_from_the_typist(job, monkeypatch):
    """Cypress: hand-typed timestamps drifted ahead and crossed a midnight that
    had not happened. The Producer must never type a time again."""
    import datetime as dt
    fixed = dt.datetime(2026, 9, 25, 21, 35, tzinfo=st.SGT)
    monkeypatch.setattr(st, "now", lambda: fixed)
    assert st.main(["log", "Van", "livery", "test", "run.", "--job", str(job)]) == 0
    line = [l for l in (job / "90-decisions.md").read_text().splitlines() if "Van livery" in l][0]
    assert line.startswith("- 25 Sep 2026 21:35: ")
    assert "Van livery test run." in line


def test_log_refuses_an_empty_line(job):
    with pytest.raises(SystemExit):
        st.main(["log", "   ", "--job", str(job)])


def test_the_studio_clock_is_singapore():
    """The Mac mini runs Asia/Singapore; studio.py must agree with it."""
    assert st.SGT == dt.timezone(dt.timedelta(hours=8))


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


# --------------------------------------------------------------------------- 0.3.7: the scope audit
#
# Every test below names the Cypress failure it was built from. The point of the
# class is that a row-level audit passes four of the five gaps, so the tests assert
# the row-level view is clean and the promise-level one is not.

CYPRESS_SCOPE = """# Scope of work: Cypress

## Deliverables

| Deliverable | Delivered as | Includes |
|---|---|---|
| Brand strategy | Doc | Positioning, the proposition, messaging hierarchy |
| Verbal identity | Doc | Tone of voice, the category words we refuse, boilerplate |
| Creative territories | Doc with visual boards | Three strategic bets, one recommended |
| Identity system | Design System artifact, plus SVG, PNG and PDF | Primary mark, small-size variant, clear space, misuse |
| Brand vault | `vault/tokens.json` plus exports | Colour, type, space, radius and motion tokens |
| Brand guidelines | HTML microsite with PDF export | The system, in use: mark, type, colour, layout, imagery, voice, accessibility floor |
| Imagery direction | Doc and contact sheet | Art direction, shot list, a custom style |
| Landing page | Production HTML | A recorded morning, the decision it turned on |
| Pitch deck | Slides, exports .pptx | A 12 to 15 slide shell, the narrative, three slides fully designed |
| Handover | Folder plus a README | Source files, fonts and licences, tokens |

## Not included

- Nothing else.
"""


def cypress_scope(job):
    (job / "02-scope.md").write_text(CYPRESS_SCOPE)
    assert st.main(["plan", "--start", "2026-09-28", "--job", str(job)]) == 0


def write_audit(job, rows=None, filled="delivery", cross="producer", default=("shipped", "02-scope.md")):
    """The audit as Delivery would leave it. `rows` overrides individual promises by key."""
    rows = rows or {}
    out = ["# Scope audit: test", "", f"filled-by: {filled}", f"cross-read-by: {cross}",
           "scope-read: 26 Sep 2026 13:00", "",
           "| Key | Bought | Kind | State | Evidence |", "|---|---|---|---|---|"]
    for pr in st.parse_scope(job):
        state, ev = rows.get(pr["key"], default)
        out.append(f"| {pr['key']} | {pr['deliverable']} · {pr['promise']} | {pr['kind']} | {state} | {ev} |")
    st.audit_path(job).parent.mkdir(parents=True, exist_ok=True)
    st.audit_path(job).write_text("\n".join(out) + "\n")


def at_final(job, tmp_path):
    """A job standing where Cypress stood when its final gate was approved."""
    cypress_scope(job)
    (job / "vault" / "tokens.json").write_text((filled(tmp_path / "v") / "tokens.json").read_text())
    fill(job / "01-brief.md")
    (job / "10-strategy" / "positioning.md").write_text("x")
    for t in ("T1", "T2", "T3"):
        (job / "20-territories" / t).mkdir(exist_ok=True)
        (job / "20-territories" / t / "board.md").write_text("x")
    sign(job)
    (job / "30-identity" / "marks.md").write_text("x")
    (job / "50-applications").mkdir(exist_ok=True)
    (job / "50-applications" / "tessel-guidelines-v1.html").write_text("<h1>Guidelines</h1>")
    for g in ("brief", "direction", "system"):
        approve(job, g)
    cross_read(job, "final")


def test_the_scope_is_read_promise_by_promise_not_row_by_row(job):
    """Cypress: four of five scope gaps sat inside a row a row-level check passes."""
    cypress_scope(job)
    keys = {p["key"] for p in st.parse_scope(job)}
    # The four gaps that were invisible at row level, each its own promise:
    for k in ("2.subject.boilerplate", "4.format.png", "4.format.pdf",
              "4.format.design-system-artifact", "9.format.pptx", "6.subject.voice"):
        assert k in keys, k
    # Row 6 buys seven subjects, and every one of them is its own line.
    six = {p["promise"].lower() for p in st.parse_scope(job) if p["row"] == 6 and p["kind"] == "subject"}
    for subject in ("mark", "type", "colour", "layout", "imagery", "voice", "accessibility floor"):
        assert subject in six, subject
    promises = st.parse_scope(job)
    assert len(promises) > 3 * len({p["row"] for p in promises}), \
        "a promise-level audit must be several times longer than a row-level one"


def test_the_parser_fails_loudly_rather_than_finding_fewer_promises(job):
    """A parser that silently yields a shorter list would hide the thing being audited."""
    (job / "02-scope.md").write_text("# Scope\n\nNo table here.\n")
    with pytest.raises(st.ScopeError, match="no '## Deliverables' heading"):
        st.parse_scope(job)

    (job / "02-scope.md").write_text("## Deliverables\n\nProse, no table.\n")
    with pytest.raises(st.ScopeError, match="no table under it"):
        st.parse_scope(job)

    (job / "02-scope.md").write_text("## Deliverables\n\n| Thing | Format |\n|---|---|\n| A | Doc |\n")
    with pytest.raises(st.ScopeError, match="three columns"):
        st.parse_scope(job)

    (job / "02-scope.md").write_text(
        "## Deliverables\n\n| Deliverable | Delivered as | Includes |\n|---|---|---|\n| A | Doc |\n")
    with pytest.raises(st.ScopeError, match="row 1 has 2 cells"):
        st.parse_scope(job)

    (job / "02-scope.md").write_text(
        "## Deliverables\n\n| Deliverable | Delivered as | Includes |\n|---|---|---|\n| A | Doc |  |\n")
    with pytest.raises(st.ScopeError, match="'subject' column is empty"):
        st.parse_scope(job)


def test_the_final_gate_will_not_raise_with_an_unstated_promise(job, tmp_path):
    """THE CYPRESS CASE. The guidelines microsite exists, is substantial and is
    internally consistent; voice, one of the seven subjects the row bought, is not
    answered. The row passes. The gate must not."""
    at_final(job, tmp_path)
    write_audit(job)
    assert st.readiness(job, st.load(job), "final") == [], "a fully answered audit raises the gate"

    write_audit(job, {"6.subject.voice": ("unstated", "")})
    probs = st.readiness(job, st.load(job), "final")
    assert any("6.subject.voice" in p and "unstated" in p for p in probs), probs
    # and the row-level view of the same job is clean, which is the whole point
    assert st.nonempty(job / "50-applications")
    assert (job / "50-applications" / "tessel-guidelines-v1.html").exists()
    assert st.main(["gate", "raise", "final", "--job", str(job)]) == 1


def test_the_final_gate_will_not_raise_without_an_audit_at_all(job, tmp_path):
    """Cypress: readiness passed on 50-applications/ being non-empty and the pack
    was written from what the roles reported."""
    at_final(job, tmp_path)
    probs = st.readiness(job, st.load(job), "final")
    assert any("scope-audit.md is missing" in p for p in probs), probs
    assert any("promise lines" in p for p in probs)


def test_shipped_needs_evidence_that_resolves(job, tmp_path):
    at_final(job, tmp_path)
    write_audit(job, {"9.format.pptx": ("shipped", "50-applications/tessel-deck-v1.pptx")})
    probs = st.readiness(job, st.load(job), "final")
    assert any("9.format.pptx" in p and "does not exist in the job" in p for p in probs), probs

    (job / "50-applications" / "tessel-deck-v1.pptx").write_text("x")
    assert st.readiness(job, st.load(job), "final") == []

    write_audit(job, {"9.format.pptx": ("shipped", "")})
    assert any("shipped with no evidence" in p for p in st.readiness(job, st.load(job), "final"))

    write_audit(job, {"9.format.pptx": ("shipped", "https://claude.ai/artifact/abc")})
    assert st.readiness(job, st.load(job), "final") == [], "an artifact URL is evidence too"


def test_absent_by_decision_must_name_a_gate_that_decided_it(job, tmp_path):
    """Cypress row 7: imagery was parked by Tim at the direction gate, so nobody owes
    anybody anything. The state is only safe because the tool can check it."""
    at_final(job, tmp_path)
    imagery = [p["key"] for p in st.parse_scope(job) if p["row"] == 7]
    write_audit(job, {k: ("absent-by-decision", "direction") for k in imagery})
    assert st.readiness(job, st.load(job), "final") == [], "parked at a decided gate is a decision, not a gap"

    write_audit(job, {k: ("absent-by-decision", "") for k in imagery})
    assert any("names no gate" in p for p in st.readiness(job, st.load(job), "final"))

    write_audit(job, {k: ("absent-by-decision", "handover") for k in imagery})
    assert any("not a gate on this track" in p for p in st.readiness(job, st.load(job), "final"))

    write_audit(job, {k: ("absent-by-decision", "final") for k in imagery})
    assert any("carries no recorded decision" in p for p in st.readiness(job, st.load(job), "final")), \
        "the final gate has not been decided yet, so it cannot be what parked a deliverable"


def test_short_and_client_blocked_need_a_note(job, tmp_path):
    at_final(job, tmp_path)
    write_audit(job, {"2.subject.boilerplate": ("short", "")})
    assert any("no note saying what is outstanding" in p for p in st.readiness(job, st.load(job), "final"))
    write_audit(job, {"2.subject.boilerplate": ("short", "no boilerplate anywhere in the job")})
    assert st.readiness(job, st.load(job), "final") == []
    write_audit(job, {"8.subject.recorded-morning": ("client-blocked", "the client owes the destination URL")})
    assert st.readiness(job, st.load(job), "final") == []
    write_audit(job, {"2.subject.boilerplate": ("nearly", "almost there")})
    assert any("is not one of" in p for p in st.readiness(job, st.load(job), "final"))


def test_a_role_cannot_cross_read_its_own_scope_audit(job, tmp_path):
    """Rule 4: the failure was three roles each verifying their own half."""
    at_final(job, tmp_path)
    write_audit(job, filled="delivery", cross="Delivery")
    probs = st.readiness(job, st.load(job), "final")
    assert any("cannot cross-read its own completeness claim" in p for p in probs), probs
    write_audit(job, filled="{{a role}}", cross="producer")
    assert any("'filled-by' is not filled in" in p for p in st.readiness(job, st.load(job), "final"))


def test_a_scope_change_after_the_audit_reopens_it(job, tmp_path):
    """The Builder's point: a generated document cannot be quietly out of date."""
    at_final(job, tmp_path)
    write_audit(job)
    assert st.readiness(job, st.load(job), "final") == []
    import os
    scope = job / "02-scope.md"
    scope.write_text(scope.read_text().replace(
        "| Handover | Folder plus a README | Source files, fonts and licences, tokens |",
        "| Handover | Folder plus a README | Source files, fonts and licences, tokens |\n"
        "| Motion | Lottie | A logo animation |"))
    os.utime(scope, (os.path.getmtime(scope) + 60, os.path.getmtime(scope) + 60))
    assert any("older than 02-scope.md" in p for p in st.readiness(job, st.load(job), "final"))


def test_regenerating_the_audit_keeps_answers_and_opens_new_promises(job, tmp_path):
    at_final(job, tmp_path)
    write_audit(job, {"2.subject.boilerplate": ("short", "not written yet")})
    scope = job / "02-scope.md"
    scope.write_text(scope.read_text().replace(
        "| Motion | Lottie | A logo animation |", "").replace(
        "| Handover | Folder plus a README | Source files, fonts and licences, tokens |",
        "| Handover | Folder plus a README | Source files, fonts and licences, tokens |\n"
        "| Motion | Lottie | A logo animation |"))
    assert st.main(["scope-audit", "--job", str(job)]) == 0
    meta, rows = st.parse_audit(job)
    assert meta["filled-by"] == "delivery" and meta["cross-read-by"] == "producer", "names are carried over"
    assert rows["2.subject.boilerplate"] == ("short", "not written yet"), "answers are carried over by key"
    assert rows["11.format.lottie"] == ("unstated", ""), \
        "a promise the scope has just gained arrives unstated, not as an absence nobody sees"


def test_the_final_pack_carries_a_generated_scope_section(job, tmp_path):
    """Cypress: the template had no section that had to be filled from the scope,
    so nothing in the document prompted the check."""
    at_final(job, tmp_path)
    write_audit(job, {"2.subject.boilerplate": ("short", "not written yet")})
    assert st.main(["gate", "raise", "final", "--job", str(job), "--force"]) == 0
    pack = (job / "gates" / "final.md").read_text()
    assert "## Scope" in pack and pack.index("## Scope") < pack.index("## Trade-offs and risks")
    assert "1 short" in pack and "2. Verbal identity" in pack
    assert "Complete" in pack


# --------------------------------------------------------------------------- 0.3.7: cross-read

def test_every_gate_but_brief_needs_a_cross_read(job):
    """Three roles, one sourcing failure, none caught by its author."""
    cypress_scope(job)
    fill(job / "01-brief.md")
    validate_intake(job)
    assert st.readiness(job, st.load(job), "brief") == [], "the brief gate is exempt: nobody else is here yet"
    approve(job, "brief")
    (job / "10-strategy" / "positioning.md").write_text("x")
    for t in ("T1", "T2", "T3"):
        (job / "20-territories" / t).mkdir(exist_ok=True)
        (job / "20-territories" / t / "board.md").write_text("x")
    probs = st.readiness(job, st.load(job), "direction")
    assert any("no cross-read recorded for 'direction'" in p for p in probs), probs
    assert st.main(["gate", "raise", "direction", "--job", str(job)]) == 1
    cross_read(job, "direction", by="creative-lead", of="strategist")
    assert st.readiness(job, st.load(job), "direction") == []
    cr = st.load(job)["gates"]["direction"]["cross_read"]
    assert cr["by"] == "creative-lead" and cr["of"] == "strategist" and cr["against"] == "02-scope.md"
    assert "Cross-read for gate 'direction'" in (job / "90-decisions.md").read_text()


def test_a_role_cannot_cross_read_itself(job):
    with pytest.raises(SystemExit, match="cannot cross-read its own"):
        st.main(["cross-read", "direction", "--by", "Producer", "--of", "producer", "--job", str(job)])
    # and a record forced in by hand is caught at the gate, not only at the command
    d = st.load(job)
    d["gates"]["direction"]["cross_read"] = {"by": "producer", "of": "producer"}
    st.save(job, d)
    assert any("checking its own completeness claim" in p
               for p in st.readiness(job, st.load(job), "direction"))


# --------------------------------------------------------------------------- 0.3.7: the vault lint at the gate

def test_the_vault_lint_runs_at_every_gate_because_the_hook_may_never_fire(job, tmp_path):
    """A job driven from the Claude app through the device shell writes every file
    with no PostToolUse hook in the loop, so the lint has to be a gate condition."""
    (job / "vault" / "tokens.json").write_text((filled(tmp_path / "v") / "tokens.json").read_text())
    cypress_scope(job)
    fill(job / "01-brief.md")
    validate_intake(job)
    assert st.readiness(job, st.load(job), "brief") == []
    (job / "50-applications").mkdir(exist_ok=True)
    (job / "50-applications" / "page.css").write_text(".a{color:#ff0000}\n")
    probs = st.readiness(job, st.load(job), "brief")
    assert any("vault lint" in p and "#ff0000" in p for p in probs), probs
    assert any("50-applications/page.css" in p for p in probs)


def test_the_gate_lint_does_not_fire_on_svg_editor_chrome(job, tmp_path):
    """CYPRESS: tessel-wordmark-v2.svg failed the lint on Inkscape namedview chrome.
    It is non-rendering, an editor writes it unasked, and a check that fires on it
    gets switched off inside a month."""
    (job / "vault" / "tokens.json").write_text((filled(tmp_path / "v") / "tokens.json").read_text())
    cypress_scope(job)
    fill(job / "01-brief.md")
    validate_intake(job)
    d = job / "30-identity" / "mark"
    d.mkdir(parents=True, exist_ok=True)
    (d / "wordmark-v2.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">\n'
        '  <sodipodi:namedview\n'
        '     id="namedview7"\n'
        '     pagecolor="#ffffff"\n'
        '     bordercolor="#000000"\n'
        '     inkscape:deskcolor="#d1d1d1" />\n'
        '  <path d="M0 0h10v10H0z" fill="#0B1B3F"/>\n'
        '</svg>\n')
    assert st.readiness(job, st.load(job), "brief") == [], "editor chrome is not a literal colour in the artwork"

    (d / "wordmark-v3.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg">\n'
        '  <sodipodi:namedview pagecolor="#ffffff" />\n'
        '  <path d="M0 0h10v10H0z" fill="#ff0000"/>\n'
        '</svg>\n')
    probs = st.readiness(job, st.load(job), "brief")
    assert any("#ff0000" in p for p in probs), "a real literal beside the chrome is still caught"
    assert not any("#ffffff" in p for p in probs)


# --------------------------------------------------------------------------- 0.3.7: the stopping rule

def test_checking_stops_on_a_pass_that_found_nothing(job):
    """Cypress ran four verification passes at handover with no rule saying when to stop."""
    assert st.VERIFY_BUDGET["sprint"] == 3
    assert st.main(["verify-pass", "handover", "--found", "9", "--job", str(job)]) == 0
    with pytest.raises(SystemExit, match="found 9 thing"):
        st.main(["verify-close", "handover", "--call", "looks fine", "--job", str(job)])
    assert st.main(["verify-pass", "handover", "--found", "0", "--job", str(job)]) == 0
    assert st.main(["verify-close", "handover", "--call",
                    "two passes, the second clean, nothing found would ship wrong", "--job", str(job)]) == 0
    log = (job / "90-decisions.md").read_text()
    assert "VERIFICATION CLOSED on 'handover' after 2 pass(es)" in log
    assert "Producer's call: two passes, the second clean" in log
    v = st.load(job)["verification"]["handover"]
    assert v["closed"]["passes"] == 2 and not st.open_verifications(st.load(job))


def test_checking_cannot_close_before_it_has_run(job):
    with pytest.raises(SystemExit, match="cannot be closed before it has run"):
        st.main(["verify-close", "handover", "--call", "nothing to check", "--job", str(job)])


def test_a_pass_beyond_the_budget_is_a_stated_decision(job):
    for i in range(3):
        assert st.main(["verify-pass", "handover", "--found", "1", "--job", str(job)]) == 0
    with pytest.raises(SystemExit, match="beyond the Brand Sprint budget of 3"):
        st.main(["verify-pass", "handover", "--found", "1", "--job", str(job)])
    assert st.main(["verify-pass", "handover", "--found", "0", "--beyond",
                    "the pptx build is not reproducible, so the pair must be rebuilt and re-compared",
                    "--job", str(job)]) == 0
    assert "Beyond budget, because: the pptx build is not reproducible" in (job / "90-decisions.md").read_text()
    assert st.main(["verify-close", "handover", "--call", "clean on the fourth", "--job", str(job)]) == 0
    with pytest.raises(SystemExit, match="was closed at"):
        st.main(["verify-pass", "handover", "--found", "1", "--job", str(job)])


def test_a_job_does_not_close_with_its_verification_open(job):
    assert st.main(["verify-pass", "handover", "--found", "2", "--job", str(job)]) == 0
    assert any("verification 'handover' open: 1 of 3 pass(es), last found 2"
               in line for line in st.status_lines(job, st.load(job)))
    with pytest.raises(SystemExit, match="Verification is still open on handover"):
        st.main(["set-active", str(job), "no"])
    assert st.main(["set-active", str(job), "no", "--force"]) == 0, "a job being stopped can still be closed"
    assert st.load(job)["active"] is False
