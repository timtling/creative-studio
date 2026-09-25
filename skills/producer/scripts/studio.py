#!/usr/bin/env python3
"""studio.py: the Producer's helper for creative studio jobs.

Deterministic work only: job set-up per track, back-planning, gate readiness and
decisions, client revision rounds, feedback triage, change requests and status.
The Producer (the main session) does the judgement; this script keeps the record.

Run `python3 studio.py --help` or `python3 studio.py <command> --help`.
Standard library only, Python 3.9+.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
TEMPLATES = SKILL / "assets" / "templates"
VAULT_PY = SKILL.parent / "brand-vault" / "scripts" / "vault.py"
JOB_FILE = "studio-job.json"
SGT = dt.timezone(dt.timedelta(hours=8))

TRACKS: dict[str, dict] = {
    "sprint": {
        "label": "Brand Sprint",
        "stages": [("intake", 1), ("strategy", 2), ("territories", 2), ("identity", 3), ("applications", 2), ("handover", 1)],
        "gates": [("brief", "intake"), ("direction", "territories"), ("system", "identity"), ("final", "applications")],
        "rounds": {"brief": 1, "direction": 1, "system": 2, "final": 1},
        "brand": "builds",
    },
    "launch-kit": {
        "label": "Launch Kit",
        "stages": [("intake", 1), ("applications", 5), ("handover", 1)],
        "gates": [("brief", "intake"), ("final", "applications")],
        "rounds": {"brief": 1, "final": 2},
        "brand": "requires",
    },
    "product-ui": {
        "label": "Product UI",
        "stages": [("intake", 1), ("flows", 2), ("screens", 4), ("prototype", 2), ("handover", 1)],
        "gates": [("brief", "intake"), ("direction", "flows"), ("system", "screens"), ("final", "prototype")],
        "rounds": {"brief": 1, "direction": 1, "system": 2, "final": 1},
        "brand": "requires",
    },
    "programme": {
        "label": "Corporate Programme",
        "stages": [("intake", 2), ("strategy", 4), ("territories", 4), ("identity", 6), ("governance", 2),
                   ("applications", 5), ("handover", 2)],
        "gates": [("brief", "intake"), ("direction", "territories"), ("system", "identity"),
                  ("governance", "governance"), ("final", "applications")],
        "rounds": {"brief": 1, "direction": 1, "system": 2, "governance": 1, "final": 2},
        "brand": "builds",
    },
    "commission": {
        "label": "Commission",
        "stages": [("intake", 1), ("make", 3), ("return", 1)],
        "gates": [("brief", "intake"), ("final", "make")],
        "rounds": {"brief": 1, "final": 1},
        "brand": "requires",
    },
}
STAGE_DIRS = {
    "intake": "00-intake", "strategy": "10-strategy", "territories": "20-territories", "flows": "20-flows",
    "identity": "30-identity", "screens": "30-screens", "prototype": "40-prototype", "make": "50-make",
    "applications": "50-applications", "governance": "60-governance", "handover": "99-handover", "return": "99-return",
}
DECISIONS = ["approved", "approved-with", "rework", "skipped"]
FEEDBACK = ["in-scope", "new-request", "taste"]


# --------------------------------------------------------------------------- basics

def now() -> dt.datetime:
    return dt.datetime.now(SGT)


def iso(t: dt.datetime | None = None) -> str:
    return (t or now()).isoformat(timespec="seconds")


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def find_job(start: str | os.PathLike | None) -> Path | None:
    env = os.environ.get("STUDIO_JOB")
    if env and (Path(env) / JOB_FILE).exists():
        return Path(env)
    p = Path(start or os.getcwd()).resolve()
    for q in [p, *p.parents]:
        if (q / JOB_FILE).exists():
            return q
    return None


def job_or_exit(a) -> Path:
    j = find_job(getattr(a, "job", None))
    if j is None:
        sys.exit("Not inside a studio job. Pass --job <folder> or run from the job folder.")
    return j


def load(job: Path) -> dict:
    return json.loads((job / JOB_FILE).read_text())


def save(job: Path, d: dict) -> None:
    tmp = job / (JOB_FILE + ".tmp")
    tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(job / JOB_FILE)


def log_decision(job: Path, line: str) -> None:
    p = job / "90-decisions.md"
    with p.open("a") as f:
        f.write(f"- {now().strftime('%d %b %Y %H:%M')}: {line}\n")


def vault_module():
    spec = importlib.util.spec_from_file_location("vault", VAULT_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- dates

def add_workdays(d: dt.date, n: int) -> dt.date:
    step = 1 if n >= 0 else -1
    while n:
        d += dt.timedelta(days=step)
        if d.weekday() < 5:
            n -= step
    return d


def next_workday(d: dt.date) -> dt.date:
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


def workdays_between(a: dt.date, b: dt.date) -> int:
    """Working days strictly after a, up to and including b (negative if b is before a)."""
    if b < a:
        return -workdays_between(b, a)
    return sum(1 for i in range(1, (b - a).days + 1) if (a + dt.timedelta(days=i)).weekday() < 5)


def plan_dates(track: str, start: dt.date | None, due: dt.date | None = None) -> tuple[list[dict], dict]:
    """Stage windows planned forward from start, with the buffer (or overrun) against due."""
    stages = TRACKS[track]["stages"]
    rows = []
    cur = next_workday(start or now().date())
    for name, n in stages:
        end = add_workdays(cur, n - 1)
        rows.append({"stage": name, "days": n, "start": cur.isoformat(), "end": end.isoformat()})
        cur = add_workdays(end, 1)
    info = {"working_days": sum(n for _, n in stages), "start": rows[0]["start"], "end": rows[-1]["end"]}
    if due:
        info["buffer_days"] = workdays_between(dt.date.fromisoformat(rows[-1]["end"]), due)
        info["fits"] = info["buffer_days"] >= 0
    return rows, info


# --------------------------------------------------------------------------- templates

def render(name: str, values: dict) -> str:
    text = (TEMPLATES / name).read_text()
    for k, v in values.items():
        text = text.replace("${" + k + "}", str(v))
    return text


def rounds_table(track: str) -> str:
    t = TRACKS[track]
    rows = ["| Gate | Closes stage | Client revision rounds included |", "|---|---|---|"]
    rows += [f"| {g} | {s} | {t['rounds'][g]} |" for g, s in t["gates"]]
    return "\n".join(rows)


# --------------------------------------------------------------------------- readiness

MARKER = re.compile(r"\{\{[^}]*\}\}")
MIN_INTAKE_ANSWERS = 3


def unfilled(p: Path) -> list[str]:
    if not p.exists():
        return [f"{p.name} is missing"]
    marks = MARKER.findall(p.read_text())
    return [f"{p.name} still has {len(marks)} unfilled prompt(s), e.g. {marks[0]}"] if marks else []


# An answer line in 00-intake/validation.md: `**A:** <what Tim said>`.
ANSWERED = re.compile(r"^[ \t]*(?:[-*]|\d+\.)?[ \t]*\*\*A:\*\*[ \t]*(.+?)[ \t]*$", re.M)
NO_ANSWER = {"unanswered", "not asked", "pending", "tbc", "tbd", "todo", "none", "n/a", "na", "-", "—"}


def answered_questions(p: Path) -> list[str]:
    """Answers in the validation file that actually say something."""
    out = []
    for a in ANSWERED.findall(p.read_text()):
        a = a.strip()
        if any(c in a for c in "<>{}") or a.lower().strip(" .") in NO_ANSWER or len(a) < 2:
            continue
        out.append(a)
    return out


def intake_validated(job: Path) -> list[str]:
    """Intake is validated before a brief is drafted, not after it is written."""
    p = job / "00-intake" / "validation.md"
    if not p.exists():
        return ["00-intake/validation.md is missing: validate the intake against the checklist and ask Tim at "
                "least three questions before drafting the brief (see the studio-intake skill)"]
    problems = unfilled(p)
    answers = answered_questions(p)
    if len(answers) < MIN_INTAKE_ANSWERS:
        problems.append(f"00-intake/validation.md records {len(answers)} answered question(s); the brief gate needs "
                        f"at least {MIN_INTAKE_ANSWERS}. Ask Tim the ones that change the track, the scope, the "
                        "price or the date, and record his answers")
    return problems


def nonempty(d: Path) -> bool:
    return d.exists() and any(f.is_file() and not f.name.startswith(".") for f in d.rglob("*"))


# A final mark is refined by a named human, and the log says who. The agent prepares
# the master; it does not sign for the pass that makes the mark final.
REFINED_BY = re.compile(r"^[ \t]*[-*][ \t].*?\brefined by:[ \t]*([^\n|·]+)", re.I | re.M)
# The same bullet, with its version: `- <date> · v4 · refined by: <name> · <what>`
REFINED_ENTRY = re.compile(r"^[ \t]*[-*][ \t].*?\bv(\d+)\b.*?\brefined by:[ \t]*([^\n|·]+)", re.I | re.M)
NOT_A_PERSON = {
    "", "tbc", "tbd", "todo", "xxx", "n/a", "na", "none", "nobody", "unknown", "pending",
    "ai", "claude", "claude code", "assistant", "the assistant", "llm", "the agent", "agent",
    "the model", "model", "the studio", "studio", "the team", "team", "someone", "somebody",
    "a designer", "the designer", "designer", "a human", "the human", "human", "person",
    "identity designer", "art director", "creative lead", "strategist", "copywriter",
    "product designer", "builder", "delivery", "producer", "panel",
}
# Words that give a placeholder away even inside a longer string.
PLACEHOLDER_WORDS = {"name", "names", "role", "roles", "initials", "placeholder", "example",
                     "todo", "tbc", "tbd", "xxx", "anon", "anonymous", "redacted"}


def _person_name(raw: str) -> bool:
    """Is this the name of a person, rather than a placeholder or a role?

    The log is what supports the client's rights in the mark later, so the bar is
    a name somebody could be held to. A template's own example must not satisfy it.
    """
    if any(c in raw for c in "<>[]{}|"):      # `<name>`, `[Name]`, `{{who}}`
        return False
    n = re.sub(r"\([^)]*\)", " ", raw)        # drop "(role)", "(agent)" and the like
    n = re.sub(r"[^A-Za-z' -]", " ", n)       # drop digits and punctuation
    n = re.sub(r"\s+", " ", n).strip().lower()
    words = n.split()
    if not words or len(n) < 2:          # 'Jo' and 'Al' are names; 'x' is not
        return False
    if n in NOT_A_PERSON or any(w in PLACEHOLDER_WORDS for w in words):
        return False
    # "the identity designer", "our copywriter": a role with an article or possessive.
    stripped = " ".join(w for w in words if w not in {"the", "a", "an", "our", "my", "studio's"})
    return stripped not in NOT_A_PERSON


# --------------------------------------------------------------------------- refinement effect
# A person-attributed pass has to have changed something. Cypress found the gap:
# a hand file was saved from a real editor, logged in good faith, and rendered
# identically to the version before it. Attribution without effect is not evidence.

RENDERERS = (
    ("rsvg-convert", lambda src, out, w: ["rsvg-convert", "-w", str(w), "-o", str(out), str(src)]),
    ("inkscape", lambda src, out, w: ["inkscape", "--export-type=png", f"--export-width={w}",
                                      f"--export-filename={out}", str(src)]),
    ("cairosvg", lambda src, out, w: ["cairosvg", "-W", str(w), "-o", str(out), str(src)]),
)
RENDER_WIDTH = 1600
# Anti-aliasing and renderer noise move a handful of pixels; a real edit moves thousands.
IDENTICAL_FRACTION = 0.0002


def renderer() -> tuple[str, object] | None:
    import shutil
    for name, argv in RENDERERS:
        if shutil.which(name):
            return name, argv
    return None


def _decode_png(data: bytes) -> tuple[int, int, bytes] | None:
    import struct, zlib
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos, idat, hdr = 8, bytearray(), None
    while pos + 8 <= len(data):
        ln, typ = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            hdr = struct.unpack(">IIBBBBB", body)
        elif typ == b"IDAT":
            idat += body
        elif typ == b"IEND":
            break
        pos += 12 + ln
    if not hdr:
        return None
    w, h, depth, ctype, comp, filt, interlace = hdr
    if depth != 8 or interlace != 0 or ctype not in (0, 2, 4, 6):
        return None
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[ctype]
    stride = w * channels
    raw = zlib.decompress(bytes(idat))
    out, prev = bytearray(), bytearray(stride)
    i = 0
    for _ in range(h):
        ft = raw[i]; i += 1
        line = bytearray(raw[i:i + stride]); i += stride
        for x in range(stride):
            a = line[x - channels] if x >= channels else 0
            b = prev[x]
            c = prev[x - channels] if x >= channels else 0
            if ft == 1:
                line[x] = (line[x] + a) & 0xFF
            elif ft == 2:
                line[x] = (line[x] + b) & 0xFF
            elif ft == 3:
                line[x] = (line[x] + (a + b) // 2) & 0xFF
            elif ft == 4:
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 0xFF
        out += line
        prev = line
    return w, h, bytes(out)


def render_differs(a: Path, b: Path) -> bool | None:
    """True if the two files render differently, False if identically, None if unknown."""
    r = renderer()
    if r is None:
        return None
    import subprocess, tempfile
    _, argv = r
    pixels = []
    with tempfile.TemporaryDirectory() as td:
        for n, src in enumerate((a, b)):
            out = Path(td) / f"{n}.png"
            try:
                subprocess.run(argv(src, out, RENDER_WIDTH), check=True, capture_output=True, timeout=60)
            except Exception:
                return None
            got = _decode_png(out.read_bytes()) if out.exists() else None
            if got is None:
                return None
            pixels.append(got)
    (w1, h1, p1), (w2, h2, p2) = pixels
    if (w1, h1) != (w2, h2):
        return True
    if len(p1) != len(p2):
        return True
    diff = sum(1 for x, y in zip(p1, p2) if x != y)
    return diff > len(p1) * IDENTICAL_FRACTION


def version_pairs(job: Path, version: int) -> list[tuple[Path, Path]]:
    """Files at `version` alongside their immediate predecessor, by the naming convention."""
    out = []
    for f in sorted((job / STAGE_DIRS["identity"]).rglob(f"*-v{version}.*")):
        prev = f.with_name(f.name.replace(f"-v{version}", f"-v{version - 1}"))
        if prev.exists():
            out.append((prev, f))
    return out


def refinement_effect(job: Path, entries: list[tuple[str, str]]) -> tuple[list[str], list[str]]:
    """(problems, warnings) for the newest person-attributed pass.

    A machine with no SVG renderer cannot tell whether the pass changed anything.
    That is a gap in what was checked, so it is said out loud in the gate pack
    rather than passing quietly: a silent pass reads as a verified one.
    """
    versions = [int(v) for v, who in entries if v and _person_name(who)]
    if not versions:
        return [], []
    v = max(versions)
    if v < 2:
        return [], []
    pairs = version_pairs(job, v)
    if not pairs:
        return [], []
    if renderer() is None:
        return [], [f"effect not verified: no renderer. v{v} is attributed to a person, and this machine has no "
                    f"SVG renderer ({', '.join(n for n, _ in RENDERERS)}), so the studio has checked that a person "
                    f"is named and **not** that the pass changed anything. Verify it by hand, or run the check "
                    f"where a renderer is installed."]
    verdicts = [(prev, cur, render_differs(prev, cur)) for prev, cur in pairs]
    known = [d for _, _, d in verdicts if d is not None]
    if not known:
        return [], [f"effect not verified: the renderer could not read v{v} or its predecessor, so the pass has "
                    "not been compared. Check the files open, or verify the change by hand."]
    if any(known):
        return [], []
    names = ", ".join(cur.name for _, cur, d in verdicts if d is False)
    return [f"30-identity: v{v} is attributed to a person but renders identically to v{v - 1} ({names}). "
            "A pass that changed nothing is not a refinement: check the file was saved with the change in it, "
            "or log what actually happened."], []


def refinement_had_effect(job: Path, entries: list[tuple[str, str]]) -> list[str]:
    return refinement_effect(job, entries)[0]


def log_entries(job: Path) -> list[tuple[str, str]]:
    p = job / STAGE_DIRS["identity"] / "refinement-log.md"
    if not p.exists():
        return []
    return [(v, who.strip()) for v, who in REFINED_ENTRY.findall(p.read_text())]


def gate_warnings(job: Path, data: dict, gate: str) -> list[str]:
    """Things the studio could not check, as opposed to things it checked and failed.

    These never block a gate. They go into the pack so Tim is told what was not
    verified, because an unmentioned gap reads as a clean result.
    """
    t = TRACKS[data["track"]]
    if gate not in dict(t["gates"]):
        return []
    if dict(t["gates"])[gate] != "identity":
        return []
    return refinement_effect(job, log_entries(job))[1]


def human_refinement(job: Path) -> list[str]:
    """The identity stage is not ready until a person has signed the refinement log."""
    p = job / STAGE_DIRS["identity"] / "refinement-log.md"
    how = ("add a line per pass: `- <date> · v<n> · refined by: <full name> · <what changed and why>`")
    if not p.exists():
        return [f"30-identity/refinement-log.md is missing; {how}"]
    names = [n.strip() for n in REFINED_BY.findall(p.read_text())]
    if not names:
        return [f"30-identity/refinement-log.md has no refinement entries; {how}"]
    if not any(_person_name(n) for n in names):
        return ["30-identity/refinement-log.md names no person for the final refinement: the mark's last pass is "
                "done by a named human (Tim or a designer), not by the agent that prepared it, and not by a "
                "placeholder or a role. Found: " + ", ".join(sorted({n for n in names})[:4])]
    return refinement_had_effect(job, log_entries(job))


def vault_ok(job: Path, data: dict) -> list[str]:
    if data.get("brand_source", "vault") != "vault":
        return []
    v = job / "vault"
    if not (v / "tokens.json").exists():
        return ["vault/tokens.json is missing (run vault.py init, then fill it)"]
    try:
        errors, _ = vault_module().validate(json.loads((v / "tokens.json").read_text()))
    except Exception as e:  # malformed JSON and the like
        return [f"vault/tokens.json cannot be read: {e}"]
    return [f"vault: {e}" for e in errors[:5]] + ([f"vault: {len(errors) - 5} more errors"] if len(errors) > 5 else [])


def readiness(job: Path, data: dict, gate: str) -> list[str]:
    t = TRACKS[data["track"]]
    gates = [g for g, _ in t["gates"]]
    if gate not in gates:
        return [f"'{gate}' is not a gate on the {t['label']} track ({', '.join(gates)})"]
    problems = []
    for g in gates[: gates.index(gate)]:
        if data["gates"][g]["status"] not in ("approved", "approved-with", "skipped"):
            problems.append(f"gate '{g}' is {data['gates'][g]['status']}; it must be approved first")
    stage = dict(t["gates"])[gate]
    if gate == "brief":
        problems += intake_validated(job)
        for f in ("01-brief.md", "02-scope.md", "03-plan.md"):
            problems += unfilled(job / f)
        if data["track"] == "commission":
            problems += unfilled(job / "00-intake" / "commission.md")
        if t["brand"] == "requires" and data.get("brand_source", "vault") == "vault" and not (job / "vault" / "tokens.json").exists():
            problems.append("this track needs an existing brand: import the client's vault or set --brand external:<source>")
        return problems
    d = job / STAGE_DIRS[stage]
    if not nonempty(d):
        problems.append(f"{d.name}/ has no work in it")
    if stage == "territories":
        terr = [x for x in sorted(d.iterdir()) if x.is_dir() and nonempty(x)] if d.exists() else []
        if len(terr) < 3:
            problems.append(f"{len(terr)} territories found in {d.name}/; the studio presents three (T1, T2, T3)")
        if not nonempty(job / STAGE_DIRS["strategy"]):
            problems.append("10-strategy/ is empty; territories must answer the positioning")
    if stage == "identity":
        problems += human_refinement(job)
    if gate in ("system", "final", "governance"):
        problems += vault_ok(job, data)
    return problems


# --------------------------------------------------------------------------- commands

def cmd_init(a) -> int:
    if a.track not in TRACKS:
        sys.exit(f"Unknown track {a.track}. Tracks: {', '.join(TRACKS)}")
    job = Path(a.folder).expanduser().resolve()
    if (job / JOB_FILE).exists():
        sys.exit(f"{job / JOB_FILE} already exists.")
    t = TRACKS[a.track]
    brand = a.brand or ("vault" if t["brand"] == "builds" else "vault")
    for s, _ in t["stages"]:
        (job / STAGE_DIRS[s]).mkdir(parents=True, exist_ok=True)
    for extra in ("gates", "assets/raw", "vault/assets"):
        (job / extra).mkdir(parents=True, exist_ok=True)
    due = dt.date.fromisoformat(a.due) if a.due else None
    data = {
        "client": slug(a.client),
        "job": slug(a.job),
        "codename": a.codename,
        "track": a.track,
        "active": True,
        "created_at": iso(),
        "requester": {"type": a.requester, "ref": a.requester_ref},
        "brand_source": brand,
        "client_date": due.isoformat() if due else None,
        "stage": t["stages"][0][0],
        "gates": {g: {"closes": s, "status": "not-raised", "rounds_allowed": t["rounds"][g], "rounds_used": 0,
                      "reworks": 0, "history": []} for g, s in t["gates"]},
        "change_requests": [],
        "plan": None,
        # imagekit (image-generation skill) reads these
        "budget": {"cap_calls": 60, "cap_usd": None, "default_usd_per_call": {"recraft": None, "replicate": None}},
        "providers": {"recraft": {"paid_plan_confirmed": False, "plan": None, "confirmed_at": None, "styles": []},
                      "replicate": {"approved_models": []}},
    }
    save(job, data)
    name = a.codename or a.client
    vals = {"job": data["job"], "client": data["client"], "name": name, "track": t["label"],
            "rounds_table": rounds_table(a.track), "date": now().strftime("%d %b %Y"),
            "due": due.strftime("%d %b %Y") if due else "{{client date}}", "brand": brand}
    (job / "01-brief.md").write_text(render("brief.md", vals))
    (job / "02-scope.md").write_text(render("scope.md", vals))
    (job / "90-decisions.md").write_text(f"# Decisions: {name}\n\nOne line per decision, newest last. Written by studio.py and the Producer.\n\n")
    (job / "00-intake").mkdir(parents=True, exist_ok=True)
    (job / "00-intake" / "validation.md").write_text(render("validation.md", vals))
    if a.track == "commission":
        (job / "00-intake" / "commission.md").write_text(render("commission.md", vals))
    log_decision(job, f"Job opened on the {t['label']} track (requester: {a.requester}{' / ' + a.requester_ref if a.requester_ref else ''}; brand source: {brand}).")
    print(f"Initialised {job} ({t['label']}). Next: validate the intake in 00-intake/validation.md, "
          "then fill 01-brief.md and 02-scope.md, then `studio.py plan`.")
    return 0


def cmd_plan(a) -> int:
    job = job_or_exit(a)
    d = load(job)
    due = dt.date.fromisoformat(a.due) if a.due else (dt.date.fromisoformat(d["client_date"]) if d.get("client_date") else None)
    start = dt.date.fromisoformat(a.start) if a.start else now().date()
    rows, info = plan_dates(d["track"], start, due)
    fits = info.get("fits", True)
    gate_at = {s: g for g, s in TRACKS[d["track"]]["gates"]}
    fmt = lambda x: dt.date.fromisoformat(x).strftime("%a %d %b")
    head = (f"{TRACKS[d['track']]['label']}, {info['working_days']} working days, {fmt(info['start'])} to "
            f"{dt.date.fromisoformat(info['end']).strftime('%a %d %b %Y')}.")
    if due and fits:
        head += f" {info['buffer_days']} working day(s) of buffer before the client date ({due.strftime('%a %d %b')})."
    lines = [f"# Plan: {d.get('codename') or d['client']}", "", head, "",
             "Planned forward from the start date so any buffer sits before the client date. Weekends are excluded; "
             "public holidays and the client's own review time are not, so check both before sending.", "",
             "| Stage | Working days | Start | End | Gate at end |", "|---|---|---|---|---|"]
    lines += [f"| {r['stage']} | {r['days']} | {fmt(r['start'])} | {fmt(r['end'])} | {gate_at.get(r['stage'], '')} |" for r in rows]
    if not fits:
        lines += ["", f"**The plan does not fit:** it ends {fmt(info['end'])}, {-info['buffer_days']} working day(s) after the "
                  f"client date of {due.strftime('%a %d %b')}. Compress a stage, cut scope or move the date, and say which at the brief gate."]
    (job / "03-plan.md").write_text("\n".join(lines) + "\n")
    d["plan"] = {"rows": rows, **info, "fits": fits}
    if due:
        d["client_date"] = due.isoformat()
    save(job, d)
    print(head + ("" if fits else "\n" + lines[-1]))
    return 0 if fits else 2


def cmd_check(a) -> int:
    job = job_or_exit(a)
    d = load(job)
    probs = readiness(job, d, a.gate)
    warns = gate_warnings(job, d, a.gate)
    if probs:
        print(f"Gate '{a.gate}' is not ready:")
        for p in probs:
            print(f"  - {p}")
    else:
        print(f"Gate '{a.gate}' is ready to raise.")
    for w in warns:
        print(f"  ! {w}")
    return 1 if probs else 0


def cmd_gate_raise(a) -> int:
    job = job_or_exit(a)
    d = load(job)
    probs = readiness(job, d, a.gate)
    if probs and not a.force:
        print(f"Cannot raise gate '{a.gate}':")
        for p in probs:
            print(f"  - {p}")
        return 1
    g = d["gates"][a.gate]
    g["status"] = "pending"
    g["history"].append({"at": iso(), "event": "raised", "forced": bool(probs)})
    pack = job / "gates" / f"{a.gate}.md"
    warns = gate_warnings(job, d, a.gate)
    if not pack.exists():
        text = render("gate-pack.md", {
            "gate": a.gate, "name": d.get("codename") or d["client"], "track": TRACKS[d["track"]]["label"],
            "stage": g["closes"], "rounds": f"{g['rounds_used']} of {g['rounds_allowed']}",
            "date": now().strftime("%d %b %Y %H:%M")})
        if warns:
            block = ("\n## Not verified\n\nWritten by studio.py. Keep it in the pack: Tim is told what the studio "
                     "could not check, not only what it checked.\n\n"
                     + "\n".join(f"- **{w}**" for w in warns) + "\n")
            text = text.replace("\n## Trade-offs and risks", block + "\n## Trade-offs and risks", 1)
        pack.write_text(text)
    for w in warns:
        print(f"  ! {w}")
    save(job, d)
    log_decision(job, f"Gate '{a.gate}' raised" + (f" with {len(probs)} readiness issue(s) overridden" if probs else "") + ".")
    print(f"Gate '{a.gate}' pending. Compose gates/{a.gate}.md and send it to Tim.")
    return 0


def cmd_gate_record(a) -> int:
    job = job_or_exit(a)
    d = load(job)
    g = d["gates"].get(a.gate)
    if g is None:
        sys.exit(f"No gate '{a.gate}' on this track.")
    if g["status"] != "pending" and a.status != "skipped":
        sys.exit(f"Gate '{a.gate}' is {g['status']}, not pending. Raise it first.")
    if a.status in ("approved-with", "rework") and not a.note:
        sys.exit(f"'{a.status}' needs --note with Tim's words.")
    g["history"].append({"at": iso(), "event": a.status, "note": a.note})
    if a.status == "rework":
        g["status"] = "rework"
        g["reworks"] += 1
    else:
        g["status"] = a.status
        stages = [s for s, _ in TRACKS[d["track"]]["stages"]]
        i = stages.index(g["closes"])
        if i + 1 < len(stages) and stages.index(d["stage"]) <= i:
            d["stage"] = stages[i + 1]
    save(job, d)
    log_decision(job, f"Gate '{a.gate}': {a.status}" + (f". Tim: \"{a.note}\"" if a.note else "") + ".")
    print(f"Gate '{a.gate}' {a.status}. Stage now: {d['stage']}.")
    return 0


def cmd_round(a) -> int:
    job = job_or_exit(a)
    d = load(job)
    g = d["gates"].get(a.gate)
    if g is None:
        sys.exit(f"No gate '{a.gate}' on this track.")
    if g["rounds_used"] >= g["rounds_allowed"] and not a.change_request:
        print(f"Revision allowance used for '{a.gate}' ({g['rounds_used']} of {g['rounds_allowed']}). "
              "Further changes are a change request: re-run with --change-request to log one for Tim.")
        return 1
    if g["rounds_used"] >= g["rounds_allowed"]:
        cr = new_cr(d, a.gate, f"Extra revision round on '{a.gate}': {a.note or 'no note'}")
        save(job, d)
        log_decision(job, f"{cr['id']} opened: extra revision round on '{a.gate}'.")
        print(f"{cr['id']} logged for Tim's decision. The round has not started.")
        return 0
    g["rounds_used"] += 1
    g["history"].append({"at": iso(), "event": "client-round", "note": a.note})
    save(job, d)
    log_decision(job, f"Client revision round {g['rounds_used']} of {g['rounds_allowed']} on '{a.gate}'" + (f": {a.note}" if a.note else "") + ".")
    left = g["rounds_allowed"] - g["rounds_used"]
    print(f"Round {g['rounds_used']} of {g['rounds_allowed']} on '{a.gate}' started. {left} left.")
    return 0


def new_cr(d: dict, gate: str | None, text: str) -> dict:
    cr = {"id": f"CR-{len(d['change_requests']) + 1:03d}", "gate": gate, "text": text, "status": "open", "opened_at": iso()}
    d["change_requests"].append(cr)
    return cr


def cmd_feedback(a) -> int:
    job = job_or_exit(a)
    d = load(job)
    rec = {"at": iso(), "gate": a.gate, "class": a.cls, "from": a.source, "text": a.text}
    if a.cls == "new-request":
        cr = new_cr(d, a.gate, a.text)
        rec["cr"] = cr["id"]
        save(job, d)
        log_decision(job, f"{cr['id']} opened from client feedback: {a.text}")
    with (job / "90-feedback.jsonl").open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    msg = {"in-scope": "logged; fold it into the current round",
           "new-request": f"logged as {rec.get('cr')}; not started until Tim decides",
           "taste": "logged for Tim: a preference, not a defect"}[a.cls]
    print(f"Feedback {msg}.")
    return 0


def cmd_cr(a) -> int:
    job = job_or_exit(a)
    d = load(job)
    if a.action == "list":
        crs = d["change_requests"]
        if not crs:
            print("No change requests.")
        for c in crs:
            print(f"{c['id']} [{c['status']}] {c.get('gate') or '-'}: {c['text']}")
        return 0
    if not a.id or not a.status:
        sys.exit("cr close needs an id and --status accepted|declined")
    for c in d["change_requests"]:
        if c["id"] == a.id:
            c.update(status=a.status, closed_at=iso(), note=a.note)
            save(job, d)
            log_decision(job, f"{a.id} {a.status}" + (f": {a.note}" if a.note else "") + ".")
            print(f"{a.id} {a.status}.")
            return 0
    sys.exit(f"No {a.id}.")


def status_lines(job: Path, d: dict) -> list[str]:
    t = TRACKS[d["track"]]
    name = d.get("codename") or d["client"]
    out = [f"{name} ({t['label']}): stage {d['stage']}" + ("" if d.get("active", True) else " [inactive]")]
    if d.get("client_date"):
        days = (dt.date.fromisoformat(d["client_date"]) - now().date()).days
        out.append(f"Client date {dt.date.fromisoformat(d['client_date']).strftime('%a %d %b')} ({days} days)"
                   + ("" if (d.get("plan") or {}).get("fits", True) else ", plan does NOT fit"))
    for g, s in t["gates"]:
        x = d["gates"][g]
        extra = f", rounds {x['rounds_used']}/{x['rounds_allowed']}" if x["status"] != "not-raised" else ""
        extra += f", reworks {x['reworks']}" if x["reworks"] else ""
        out.append(f"  gate {g:<10} {x['status']}{extra}")
    open_cr = [c for c in d["change_requests"] if c["status"] == "open"]
    if open_cr:
        out.append(f"Open change requests: {', '.join(c['id'] for c in open_cr)}")
    pending = next((g for g, _ in t["gates"] if d["gates"][g]["status"] == "pending"), None)
    nxt = next((g for g, _ in t["gates"] if d["gates"][g]["status"] in ("not-raised", "rework")), None)
    if pending:
        out.append(f"Waiting on Tim: gate '{pending}'.")
    elif nxt:
        probs = readiness(job, d, nxt)
        out.append(f"Next: gate '{nxt}'" + (f", {len(probs)} thing(s) outstanding: {probs[0]}" if probs else ", ready to raise"))
    else:
        out.append("All gates closed. Next: handover.")
    return out


def cmd_status(a) -> int:
    job = job_or_exit(a)
    d = load(job)
    if a.json:
        print(json.dumps(d, indent=2))
    else:
        print("\n".join(status_lines(job, d)))
    return 0


def cmd_set_active(a) -> int:
    job = Path(a.folder).expanduser().resolve()
    d = load(job)
    d["active"] = a.value == "yes"
    save(job, d)
    log_decision(job, f"Job marked {'active' if d['active'] else 'inactive'}.")
    print(f"{d['job']}: active={d['active']}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="studio.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="open a job on a track")
    p.add_argument("folder")
    p.add_argument("--client", required=True)
    p.add_argument("--job", required=True)
    p.add_argument("--track", required=True, choices=list(TRACKS))
    p.add_argument("--codename")
    p.add_argument("--due", help="client date YYYY-MM-DD")
    p.add_argument("--requester", default="direct", help="direct, engagement-studio, or another name")
    p.add_argument("--requester-ref", help="e.g. the engagement codename")
    p.add_argument("--brand", help="vault (default) or external:<source>, e.g. external:ntt-data-brand")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("plan", help="plan forward from --start (default today) and show buffer against the client date")
    p.add_argument("--due")
    p.add_argument("--start")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("check", help="is a gate ready to raise?")
    p.add_argument("gate")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("gate", help="raise a gate or record Tim's decision")
    gs = p.add_subparsers(dest="gate_cmd", required=True)
    q = gs.add_parser("raise")
    q.add_argument("gate")
    q.add_argument("--force", action="store_true", help="raise despite readiness issues (logged)")
    q.add_argument("--job")
    q.set_defaults(fn=cmd_gate_raise)
    q = gs.add_parser("record")
    q.add_argument("gate")
    q.add_argument("--status", required=True, choices=DECISIONS)
    q.add_argument("--note")
    q.add_argument("--job")
    q.set_defaults(fn=cmd_gate_record)

    p = sub.add_parser("round", help="start a client revision round against a gate's allowance")
    p.add_argument("gate")
    p.add_argument("--note")
    p.add_argument("--change-request", action="store_true", help="log an extra round as a change request")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_round)

    p = sub.add_parser("feedback", help="log and classify one piece of client feedback")
    p.add_argument("--gate")
    p.add_argument("--class", dest="cls", required=True, choices=FEEDBACK)
    p.add_argument("--source", default="client")
    p.add_argument("--text", required=True)
    p.add_argument("--job")
    p.set_defaults(fn=cmd_feedback)

    p = sub.add_parser("cr", help="list or close change requests")
    p.add_argument("action", choices=["list", "close"])
    p.add_argument("id", nargs="?")
    p.add_argument("--status", choices=["accepted", "declined"])
    p.add_argument("--note")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_cr)

    p = sub.add_parser("status", help="stage, gates, rounds, change requests and the next action")
    p.add_argument("--json", action="store_true")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("set-active", help="mark a job active or inactive")
    p.add_argument("folder")
    p.add_argument("value", choices=["yes", "no"])
    p.set_defaults(fn=cmd_set_active)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
