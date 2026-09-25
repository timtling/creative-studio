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


def approve(job, gate):
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
    assert st.readiness(job, st.load(job), "system") == []


def test_rework_and_decisions_log(job):
    fill(job / "01-brief.md")
    fill(job / "02-scope.md")
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
