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
# How many full verification passes a stage's work gets before continuing becomes a
# decision rather than a habit. Checking stops when a pass finds nothing that would
# ship wrong; the budget is what forces the Producer to make that call out loud.
# Cypress ran four passes at handover with no rule saying when to stop.
VERIFY_BUDGET = {"sprint": 3, "launch-kit": 2, "product-ui": 3, "programme": 4, "commission": 2}
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


# --------------------------------------------------------------------------- scope audit

class ScopeError(Exception):
    """The deliverables table could not be read.

    Always raised, never worked around. A parser that yields a shorter list of
    promises than the scope contains would hide exactly what this check exists to
    find, so failing loudly with the row it could not read is the only safe mode.
    """


SCOPE_HEAD = re.compile(r"^#{2,}\s*Deliverables\s*$", re.M)
TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
RULE_ROW = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
# Deliberately over-splits. An over-split promise costs one answered line; an
# under-split one hides a promise, which is the failure the audit exists for.
PROMISE_SPLIT = re.compile(r",|;|\band\b|\bplus\b|\bwith\b", re.I)
LEADING_NOISE = {"a", "an", "the", "its", "in", "one", "exports", "export", "including",
                 "includes", "for", "of", "to", "as", "at", "then"}
AUDIT_STATES = ("shipped", "absent-by-decision", "short", "client-blocked")
AUDIT_FILE = "scope-audit.md"
AUDIT_META = re.compile(r"^(filled-by|cross-read-by|scope-read):[ \t]*(.*)$", re.M)


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _promises(cell: str, row: int, kind: str) -> list[str]:
    out = []
    for part in PROMISE_SPLIT.split(cell):
        if ":" in part:                              # "the system, in use: mark" -> "mark"
            part = part.split(":", 1)[1]
        words = part.strip().strip("`*.…").split()
        while words and words[0].lower().strip(",.`") in LEADING_NOISE:
            words = words[1:]
        p = " ".join(words).strip(" `*.…")
        if p:
            out.append(p)
    if not out:
        raise ScopeError(f"02-scope.md row {row}: the '{kind}' column is empty, "
                         "so the row promises nothing that can be audited")
    return out


def parse_scope(job: Path) -> list[dict]:
    """Every promise in 02-scope.md's deliverables table: one per format, one per subject.

    The unit is the promise and never the row, because on Cypress four of the five
    scope gaps sat inside a row that a row-level check passes. Twelve SVG masters
    existed while the PNG set, the mark PDF and the Design System artifact did not.
    `voice.md` existed without its boilerplate. Fourteen slides and a correct PDF
    existed without the `.pptx`. And a twelve-section guidelines microsite existed,
    internally consistent and complete against `system.md`, with voice - one of the
    seven subjects the row bought - missing from it entirely.
    """
    p = job / "02-scope.md"
    if not p.exists():
        raise ScopeError("02-scope.md is missing")
    m = SCOPE_HEAD.search(p.read_text())
    if not m:
        raise ScopeError("02-scope.md has no '## Deliverables' heading, so there is no table to audit")
    body = re.split(r"^#{2,}\s", p.read_text()[m.end():], maxsplit=1, flags=re.M)[0]
    lines = [ln for ln in body.splitlines() if TABLE_ROW.match(ln)]
    if not lines:
        raise ScopeError("02-scope.md has a '## Deliverables' heading with no table under it")
    head = _cells(lines[0])
    if len(head) != 3 or head[0].lower() != "deliverable":
        raise ScopeError("02-scope.md's deliverables table needs three columns, "
                         f"'Deliverable | Delivered as | Includes'. Found: {' | '.join(head) or '(nothing)'}")
    out: list[dict] = []
    seen: set[str] = set()
    row = 0
    for line in lines[1:]:
        if RULE_ROW.match(line):
            continue
        row += 1
        c = _cells(line)
        if len(c) != 3:
            raise ScopeError(f"02-scope.md deliverable row {row} has {len(c)} cells, not 3: {line.strip()[:70]}")
        name = c[0].strip("*` ")
        if not name:
            raise ScopeError(f"02-scope.md deliverable row {row} has no name in the first column")
        for kind, cell in (("format", c[1]), ("subject", c[2])):
            for promise in _promises(cell, row, kind):
                base = f"{row}.{kind}.{slug(promise)[:44] or 'unnamed'}"
                key, n = base, 2
                while key in seen:
                    key, n = f"{base}-{n}", n + 1
                seen.add(key)
                out.append({"key": key, "row": row, "deliverable": name, "kind": kind, "promise": promise})
    if not out:
        raise ScopeError("02-scope.md's deliverables table has a header and no deliverable rows")
    return out


def audit_path(job: Path) -> Path:
    return job / "gates" / AUDIT_FILE


def parse_audit(job: Path) -> tuple[dict, dict]:
    """(meta, {key: (state, evidence)}) read back out of gates/scope-audit.md."""
    text = audit_path(job).read_text()
    meta = {k: v.strip() for k, v in AUDIT_META.findall(text)}
    rows: dict[str, tuple[str, str]] = {}
    for line in text.splitlines():
        if not TABLE_ROW.match(line) or RULE_ROW.match(line):
            continue
        c = _cells(line)
        if len(c) != 5 or c[0].lower() == "key":
            continue
        rows[c[0].strip("` ")] = (c[3].strip().lower(), c[4].strip())
    return meta, rows


def render_audit(job: Path, d: dict, promises: list[dict], meta: dict, keep: dict) -> str:
    name = d.get("codename") or d["client"]
    fmts = sum(1 for p in promises if p["kind"] == "format")
    out = [
        f"# Scope audit: {name}",
        "",
        f"{len(promises)} promises across {len({p['row'] for p in promises})} bought deliverables: "
        f"{fmts} formats and {len(promises) - fmts} subjects.",
        "",
        "Generated by `studio.py scope-audit` from `02-scope.md`, **one line per promise and never",
        "one per deliverable**. Delivery fills it at the end of the making stage; the Producer",
        "cross-reads it. `studio.py check final` will not raise the final gate until every line",
        "has a state and every piece of evidence resolves.",
        "",
        "Do not hand-edit the Key, Bought or Kind columns. Re-run the command after any scope",
        "change: states are carried over by key, and a promise the scope has just gained arrives",
        "as `unstated` rather than as an absence nobody sees.",
        "",
        f"filled-by: {meta.get('filled-by') or '{{the role that audited the work, usually Delivery}}'}",
        f"cross-read-by: {meta.get('cross-read-by') or '{{the role that checked it, which must differ}}'}",
        f"scope-read: {now().strftime('%d %b %Y %H:%M')}",
        "",
        "## What the states mean",
        "",
        "| State | The evidence it needs |",
        "|---|---|",
        "| `shipped` | a job-relative path that resolves, or an `https://` artifact URL |",
        "| `absent-by-decision` | the gate that decided it, which must carry a recorded decision |",
        "| `short` | one line saying what is missing |",
        "| `client-blocked` | one line saying what the client still owes |",
        "| `unstated` | nobody has answered yet. The final gate will not raise while one remains |",
        "",
        "`absent-by-decision` is the state that separates a decision from a gap, and it is the one",
        "the tool can check against Tim's own recorded words. *Complete* and *short* are about what",
        "the studio owes; *client-blocked* is about what the client owes.",
        "",
        "| Key | Bought | Kind | State | Evidence |",
        "|---|---|---|---|---|",
    ]
    for p in promises:
        state, ev = keep.get(p["key"], ("unstated", ""))
        out.append(f"| {p['key']} | {p['deliverable']} · {p['promise']} | {p['kind']} | {state} | {ev} |")
    return "\n".join(out) + "\n"


def audit_problems(job: Path, d: dict) -> list[str]:
    """Why the final gate cannot raise.

    Never a judgement about the quality of the work: every line here is a promise
    nobody has answered, or a piece of evidence that does not resolve.
    """
    try:
        promises = parse_scope(job)
    except ScopeError as e:
        return [str(e)]
    p = audit_path(job)
    if not p.exists():
        return [f"gates/{AUDIT_FILE} is missing. Run `studio.py scope-audit`, have Delivery answer all "
                f"{len(promises)} promise lines, then cross-read it as the Producer"]
    if p.stat().st_mtime < (job / "02-scope.md").stat().st_mtime:
        return [f"gates/{AUDIT_FILE} is older than 02-scope.md: the scope moved after the audit was written. "
                "Re-run `studio.py scope-audit` (answered states are kept) and answer any new line"]
    meta, rows = parse_audit(job)
    probs = []
    filled, cross = meta.get("filled-by", ""), meta.get("cross-read-by", "")
    for label, who in (("filled-by", filled), ("cross-read-by", cross)):
        if not who or MARKER.search(who):
            probs.append(f"gates/{AUDIT_FILE}: '{label}' is not filled in")
    if filled and cross and not MARKER.search(filled) and not MARKER.search(cross) \
            and slug(filled) == slug(cross):
        probs.append(f"gates/{AUDIT_FILE}: filled-by and cross-read-by are both '{filled}'. A role cannot "
                     "cross-read its own completeness claim, which is the failure this check exists for")
    missing = [p2["key"] for p2 in promises if p2["key"] not in rows]
    if missing:
        probs.append(f"gates/{AUDIT_FILE} has no line for {len(missing)} promise(s), e.g. {missing[0]}. "
                     "Re-run `studio.py scope-audit`")
    decided = {g for g, x in d["gates"].items() if x["status"] in ("approved", "approved-with", "skipped")}
    bad = []
    for p2 in promises:
        state, ev = rows.get(p2["key"], ("unstated", ""))
        label = f"{p2['key']} ({p2['deliverable']}: {p2['promise']})"
        if state in ("", "unstated"):
            bad.append(f"{label} is unstated")
        elif state not in AUDIT_STATES:
            bad.append(f"{label} has state '{state}', which is not one of {', '.join(AUDIT_STATES)}")
        elif state == "shipped":
            if not ev:
                bad.append(f"{label} is shipped with no evidence: give a job-relative path or an https:// URL")
            elif not ev.lower().startswith(("http://", "https://")):
                target = ev.strip("`* ").split()[0].strip("`")
                if not (job / target).exists():
                    bad.append(f"{label} is shipped, and '{target}' does not exist in the job")
        elif state == "absent-by-decision":
            g = ev.strip("`* ").split()[0].lower().strip("`,") if ev.strip() else ""
            if not g:
                bad.append(f"{label} is absent-by-decision and names no gate. Name the gate that decided it")
            elif g not in d["gates"]:
                bad.append(f"{label} names '{g}', which is not a gate on this track")
            elif g not in decided:
                bad.append(f"{label} names gate '{g}', which carries no recorded decision")
        elif not ev:
            bad.append(f"{label} is '{state}' with no note saying what is outstanding")
    probs += bad[:8]
    if len(bad) > 8:
        probs.append(f"and {len(bad) - 8} more promise line(s) unanswered or unresolved")
    return probs


def audit_pack_section(job: Path, d: dict) -> str:
    """The final gate pack's scope table, rendered from the audit rather than written.

    The pack template had no section that had to be filled from 02-scope.md, so
    nothing in the document prompted the check that would have caught Cypress's
    four scope gaps. This is that section, and it is generated.
    """
    try:
        promises = parse_scope(job)
    except ScopeError:
        return ""
    if not audit_path(job).exists():
        return ""
    _, rows = parse_audit(job)
    by_row: dict[int, dict] = {}
    for p in promises:
        state = rows.get(p["key"], ("unstated", ""))[0]
        r = by_row.setdefault(p["row"], {"name": p["deliverable"], "states": {}})
        r["states"][state] = r["states"].get(state, 0) + 1
    lines = ["\n## Scope\n",
             "Written by studio.py from `gates/scope-audit.md`, one row per bought deliverable and "
             "counted per promise. Nothing here is a report of what a role said it finished.\n",
             "| Bought | Promises | State |", "|---|---|---|"]
    for row in sorted(by_row):
        r = by_row[row]
        n = sum(r["states"].values())
        if set(r["states"]) == {"shipped"}:
            verdict = "**Complete**"
        else:
            verdict = ", ".join(f"{c} {s}" for s, c in sorted(r["states"].items()) if s != "shipped")
            if r["states"].get("shipped"):
                verdict = f"{r['states']['shipped']} shipped, " + verdict
        lines.append(f"| {row}. {r['name']} | {n} | {verdict} |")
    return "\n".join(lines) + "\n"


def cross_read_problems(d: dict, gate: str) -> list[str]:
    """One role checks another's completeness claim against the commissioning document.

    Cypress produced three instances of the same failure in one day - the Producer's
    gate pack written from what roles reported, the Strategist's README written from
    the scope rather than from the file, the Builder's microsite written from
    system.md rather than from the scope - and not one was caught by its author. The
    rule is not "be more careful": it is that somebody else reads the claim, which is
    cheaper because it does not require anyone to be more careful.

    Exempt at the brief gate, where the Producer is the only role in the job and the
    commissioning document is the client's own material. Intake validation already
    holds that gate.
    """
    if gate == "brief":
        return []
    cr = (d["gates"].get(gate) or {}).get("cross_read")
    if not cr:
        return [f"no cross-read recorded for '{gate}'. One role checks another's completeness claim against "
                f"the commissioning document: `studio.py cross-read {gate} --by <role> --of <role> "
                "--against <document>`"]
    if slug(cr.get("by", "")) == slug(cr.get("of", "")):
        return [f"the cross-read for '{gate}' has '{cr.get('by')}' checking its own completeness claim"]
    return []


def vault_lint(job: Path, data: dict) -> list[str]:
    """The vault lint, run as a gate condition rather than left to the write hook.

    The PostToolUse hook reports literal colours as they are written, but it only
    fires where the hook is in the loop. A job driven from the Claude app through the
    device shell writes files with no hook running at all, so on those jobs the lint
    has never run by the time a gate is raised. Checking it here costs a second and
    is the difference between a rule and a hope.
    """
    if data.get("brand_source", "vault") != "vault":
        return []
    if not (job / "vault" / "tokens.json").exists():
        return []
    try:
        mod = vault_module()
        files = [p for p in sorted(job.rglob("*")) if p.is_file() and p.suffix.lower() in mod.LINT_EXT]
        res = mod.lint_files(files, job / "vault")
    except Exception as e:                                   # a half-written vault is vault_ok's problem
        return [f"vault lint could not run: {e}"]
    out = []
    for f, issues in sorted(res.items())[:5]:
        try:
            rel = Path(f).resolve().relative_to(job.resolve())
        except ValueError:
            rel = Path(f)
        line, lit, why = issues[0]
        more = f", and {len(issues) - 1} more in this file" if len(issues) > 1 else ""
        out.append(f"vault lint: {rel}:{line} {lit} ({why}){more}")
    if len(res) > 5:
        out.append(f"vault lint: {len(res) - 5} more file(s) carry literal colours")
    return out


def verification(d: dict, key: str) -> dict:
    return d.setdefault("verification", {}).setdefault(key, {"passes": [], "closed": None})


def open_verifications(d: dict) -> list[str]:
    return [k for k, v in (d.get("verification") or {}).items() if v.get("passes") and not v.get("closed")]


def readiness(job: Path, data: dict, gate: str) -> list[str]:
    t = TRACKS[data["track"]]
    gates = [g for g, _ in t["gates"]]
    if gate not in gates:
        return [f"'{gate}' is not a gate on the {t['label']} track ({', '.join(gates)})"]
    problems = []
    for g in gates[: gates.index(gate)]:
        if data["gates"][g]["status"] not in ("approved", "approved-with", "skipped"):
            problems.append(f"gate '{g}' is {data['gates'][g]['status']}; it must be approved first")
    problems += cross_read_problems(data, gate)
    problems += vault_lint(job, data)
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
    if gate == "final":
        problems += audit_problems(job, data)
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


def cmd_log(a) -> int:
    """Append a decision, timestamped from the machine clock.

    The Producer must never type a time. Hand-typed timestamps drift, and on the
    studio's first job they drifted past a midnight that had not happened yet.
    """
    job = job_or_exit(a)
    line = " ".join(a.line).strip()
    if not line:
        sys.exit("Nothing to log.")
    log_decision(job, line)
    print(f"{now().strftime('%d %b %Y %H:%M')}: {line[:72]}{'...' if len(line) > 72 else ''}")
    return 0


def cmd_scope_audit(a) -> int:
    job = job_or_exit(a)
    d = load(job)
    try:
        promises = parse_scope(job)
    except ScopeError as e:
        sys.exit(f"Cannot read the scope: {e}")
    p = audit_path(job)
    meta, keep = parse_audit(job) if p.exists() else ({}, {})
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_audit(job, d, promises, meta, keep))
    unstated = [x for x in promises if keep.get(x["key"], ("unstated", ""))[0] not in AUDIT_STATES]
    fmts = sum(1 for x in promises if x["kind"] == "format")
    print(f"gates/{AUDIT_FILE}: {len(promises)} promises across {len({x['row'] for x in promises})} "
          f"deliverables ({fmts} formats, {len(promises) - fmts} subjects). "
          f"{len(promises) - len(unstated)} answered, {len(unstated)} to go.")
    for x in unstated[:60]:
        print(f"  unstated  {x['key']}  {x['deliverable']} \u00b7 {x['promise']}")
    if len(unstated) > 60:
        print(f"  ... and {len(unstated) - 60} more")
    return 0


def cmd_cross_read(a) -> int:
    job = job_or_exit(a)
    d = load(job)
    if a.gate not in d["gates"]:
        sys.exit(f"No gate '{a.gate}' on this track.")
    if slug(a.by) == slug(a.of):
        sys.exit(f"'{a.by}' cannot cross-read its own completeness claim. The point of a cross-read is that "
                 "somebody else reads it, because a role asking itself to catch its own blind spot is the "
                 "thing that failed three times on Cypress.")
    d["gates"][a.gate]["cross_read"] = {"at": iso(), "by": a.by, "of": a.of,
                                        "against": a.against, "note": a.note}
    save(job, d)
    log_decision(job, f"Cross-read for gate '{a.gate}': {a.by} checked {a.of}'s completeness claim against "
                      f"{a.against or 'the commissioning document'}." + (f" {a.note}" if a.note else ""))
    print(f"Cross-read recorded for '{a.gate}': {a.by} checked {a.of}.")
    return 0


def cmd_verify_pass(a) -> int:
    job = job_or_exit(a)
    d = load(job)
    v = verification(d, a.key)
    if v.get("closed"):
        sys.exit(f"Verification on '{a.key}' was closed at {v['closed']['at'][:16]}. Reopen it by recording "
                 "why, not by adding a pass to a closed record.")
    budget = VERIFY_BUDGET[d["track"]]
    n = len(v["passes"]) + 1
    if n > budget and not a.beyond:
        sys.exit(f"Pass {n} is beyond the {TRACKS[d['track']]['label']} budget of {budget}. Continuing is a "
                 f"decision rather than a habit: either close it with `studio.py verify-close {a.key} "
                 "--call \"<why it is done>\"`, or re-run this with --beyond \"<why another pass is "
                 "warranted>\".")
    v["passes"].append({"at": iso(), "found": a.found, "note": a.note, "beyond": a.beyond})
    save(job, d)
    log_decision(job, f"Verification pass {n} of {budget} on '{a.key}': {a.found} thing(s) found that would "
                      f"ship wrong." + (f" {a.note}" if a.note else "")
                 + (f" Beyond budget, because: {a.beyond}" if a.beyond else ""))
    print(f"Pass {n} of {budget} on '{a.key}': found {a.found}."
          + ("" if a.found else " Nothing would ship wrong, so this pass can close the verification."))
    return 0


def cmd_verify_close(a) -> int:
    job = job_or_exit(a)
    d = load(job)
    v = verification(d, a.key)
    if not v["passes"]:
        sys.exit(f"No verification passes recorded on '{a.key}'. Checking cannot be closed before it has run.")
    last = v["passes"][-1]
    if last["found"]:
        sys.exit(f"The last pass on '{a.key}' found {last['found']} thing(s) that would ship wrong. Fix them "
                 "and run another pass: checking stops when a pass finds nothing, not when the budget "
                 "runs out.")
    v["closed"] = {"at": iso(), "call": a.call, "passes": len(v["passes"])}
    save(job, d)
    log_decision(job, f"VERIFICATION CLOSED on '{a.key}' after {len(v['passes'])} pass(es), the last of which "
                      f"found nothing that would ship wrong. Producer's call: {a.call}")
    print(f"'{a.key}': verification closed after {len(v['passes'])} pass(es) of "
          f"{VERIFY_BUDGET[d['track']]}.")
    return 0


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
        if a.gate == "final":
            scope = audit_pack_section(job, d)
            if scope:
                text = text.replace("\n## Trade-offs and risks", scope + "\n## Trade-offs and risks", 1)
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
    for k in open_verifications(d):
        v = d["verification"][k]
        out.append(f"  verification '{k}' open: {len(v['passes'])} of {VERIFY_BUDGET[d['track']]} pass(es), "
                   f"last found {v['passes'][-1]['found']}")
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
    if a.value == "no" and not a.force:
        stuck = open_verifications(d)
        if stuck:
            sys.exit(f"Verification is still open on {', '.join(stuck)}. Close it with `studio.py verify-close "
                     "<key> --call \"<why it is done>\"` so the record says who decided checking was "
                     "finished, or pass --force if the job is being stopped rather than delivered.")
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

    p = sub.add_parser("log", help="append a decision, timestamped from the machine clock")
    p.add_argument("line", nargs="+")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_log)
    p = sub.add_parser("scope-audit", help="generate gates/scope-audit.md from 02-scope.md, one line per promise")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_scope_audit)

    p = sub.add_parser("cross-read", help="record that one role checked another's completeness claim")
    p.add_argument("gate")
    p.add_argument("--by", required=True, help="the role doing the reading")
    p.add_argument("--of", required=True, help="whose completeness claim it read; must differ from --by")
    p.add_argument("--against", help="the commissioning document it was checked against, e.g. 02-scope.md")
    p.add_argument("--note")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_cross_read)

    p = sub.add_parser("verify-pass", help="record one verification pass and what it found")
    p.add_argument("key", help="what is being verified, e.g. handover or applications")
    p.add_argument("--found", type=int, required=True, help="how many things it found that would ship wrong")
    p.add_argument("--note")
    p.add_argument("--beyond", help="why a pass beyond the track's budget is warranted")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_verify_pass)

    p = sub.add_parser("verify-close", help="the Producer's call that checking is done")
    p.add_argument("key")
    p.add_argument("--call", required=True, help="why it is done, in one line, for the decisions log")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_verify_close)

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
    p.add_argument("--force", action="store_true",
                   help="close a job with verification still open, for one stopped rather than delivered")
    p.add_argument("folder")
    p.add_argument("value", choices=["yes", "no"])
    p.set_defaults(fn=cmd_set_active)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
