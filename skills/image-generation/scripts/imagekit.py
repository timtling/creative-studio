#!/usr/bin/env python3
"""imagekit.py: image generation book-keeping for the creative studio.

Owns everything deterministic about generated imagery on a job:

  * the job file (studio-job.json): client, budget, the Recraft paid-plan
    confirmation, cleared Replicate models and the client's Recraft styles
  * the provenance ledger (assets/ledger.jsonl): one record per asset with
    provider, model, prompt, parameters, licence basis, file and sha256
  * capture: downloads generated files before they expire (Replicate deletes
    API outputs after one hour) and saves inline images returned by a tool
  * the two plugin hooks: hook-pre (budget, paid plan, model licence) and
    hook-post (log the call, capture its outputs, tell the agent what happened)

Run `python3 imagekit.py --help` or `python3 imagekit.py <command> --help`.
Standard library only, Python 3.9+.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import mimetypes
import os
import re
import shutil
import ssl
import sys
import urllib.request
from pathlib import Path

JOB_FILE = "studio-job.json"
SGT = dt.timezone(dt.timedelta(hours=8))
STATUSES = ["candidate", "selected", "rejected", "delivered", "pending-fetch", "expired"]
REPLICATE_TTL_MIN = 60  # Replicate deletes API prediction outputs after an hour

TOOL_RE = re.compile(r"^mcp__(.+?)__(.+)$")
READ_RE = re.compile(r"^(list|get|search|read|account|user|whoami|describe|cancel|delete|check|status)")
SPEND_RE = re.compile(
    r"(generat|predict|vectori|upscal|remov|replac|edit|inpaint|variation|to_image|"
    r"erase|outpaint|style|create|run)"
)
ASSET_URL_RE = re.compile(
    r"https://(?:[a-z0-9-]+\.)*(?:recraft\.ai|replicate\.delivery)/[^\s\"'<>)\]\\]+",
    re.IGNORECASE,
)
MEDIA_EXT = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".mp4", ".webm", ".mov"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist"}


# --------------------------------------------------------------------------- basics

def now() -> dt.datetime:
    return dt.datetime.now(SGT)


def iso(t: dt.datetime | None = None) -> str:
    return (t or now()).isoformat(timespec="seconds")


def parse_iso(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        return None


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


class AmbiguousJob(Exception):
    pass


def find_job(cwd: str | os.PathLike | None = None) -> Path | None:
    """Return the job folder, or None when not inside a studio job.

    Order: $STUDIO_JOB, then cwd and its parents, then active jobs below cwd
    (depth 3). More than one active job below cwd raises AmbiguousJob so an
    asset can never land in the wrong client's ledger.
    """
    env = os.environ.get("STUDIO_JOB")
    if env:
        p = Path(env).expanduser()
        p = p.parent if p.name == JOB_FILE else p
        if (p / JOB_FILE).exists():
            return p
    start = Path(cwd or os.getcwd()).resolve()
    for p in [start, *start.parents]:
        if (p / JOB_FILE).exists():
            return p
    found = []
    for root, dirs, files in os.walk(start):
        depth = len(Path(root).relative_to(start).parts)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")] if depth < 3 else []
        if JOB_FILE in files:
            try:
                if json.loads((Path(root) / JOB_FILE).read_text()).get("active", True):
                    found.append(Path(root))
            except (OSError, json.JSONDecodeError):
                continue
    if len(found) > 1:
        raise AmbiguousJob(", ".join(str(f.relative_to(start)) for f in found))
    return found[0] if found else None


def load_job(job: Path) -> dict:
    return json.loads((job / JOB_FILE).read_text())


def save_job(job: Path, data: dict) -> None:
    (job / JOB_FILE).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def ledger_path(job: Path) -> Path:
    return job / "assets" / "ledger.jsonl"


def calls_path(job: Path) -> Path:
    return job / "assets" / "calls.jsonl"


def read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def append_jsonl(p: Path, rec: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_jsonl(p: Path, recs: list[dict]) -> None:
    tmp = p.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs))
    tmp.replace(p)


def next_id(recs: list[dict]) -> str:
    n = max((int(r["id"].split("-")[1]) for r in recs if r.get("id", "").startswith("A-")), default=0)
    return f"A-{n + 1:03d}"


# --------------------------------------------------------------------------- classification

def classify(tool_name: str) -> tuple[str | None, str, bool]:
    """(provider, tool, spends) for an MCP tool name; provider None if not ours."""
    m = TOOL_RE.match(tool_name or "")
    if not m:
        return None, tool_name, False
    server, tool = m.group(1).lower(), m.group(2).lower()
    provider = "recraft" if "recraft" in server else "replicate" if "replicate" in server else None
    if provider is None:
        return None, tool, False
    spends = not READ_RE.match(tool) and bool(SPEND_RE.search(tool))
    return provider, tool, spends


def matched_model(job_data: dict, tool_input) -> dict | None:
    """The cleared model a Replicate call names, as owner/name anywhere in its input
    (including owner:version refs) or split across model_owner/model_name fields."""
    blob = json.dumps(tool_input, ensure_ascii=False).lower()
    names = set()
    for o in _walk(tool_input or {}):
        if isinstance(o, dict):
            for ok, nk in (("model_owner", "model_name"), ("owner", "name"), ("owner", "model")):
                if isinstance(o.get(ok), str) and isinstance(o.get(nk), str):
                    names.add(f"{o[ok]}/{o[nk]}".lower())
    for m in job_data.get("providers", {}).get("replicate", {}).get("approved_models", []):
        mid = m.get("id", "").lower()
        if mid and (mid in blob or mid in names):
            return m
    return None


def est_cost(job_data: dict, provider: str, model: dict | None) -> float | None:
    if model and model.get("est_usd_per_call") is not None:
        return float(model["est_usd_per_call"])
    rate = job_data.get("budget", {}).get("default_usd_per_call", {}).get(provider)
    return float(rate) if rate is not None else None


def spend_so_far(job: Path) -> tuple[int, float]:
    calls = [c for c in read_jsonl(calls_path(job)) if c.get("spends")]
    return len(calls), sum(c.get("est_usd") or 0.0 for c in calls)


def pre_check(job: Path, tool_name: str, tool_input) -> str | None:
    """Return a denial reason, or None to allow."""
    provider, tool, spends = classify(tool_name)
    if not provider or not spends:
        return None
    data = load_job(job)
    if not data.get("active", True):
        return f"Job '{data.get('job')}' is inactive. Reactivate it with `imagekit.py set-active {job} yes` before generating."
    prov = data.get("providers", {})
    model = None
    if provider == "recraft":
        if not prov.get("recraft", {}).get("paid_plan_confirmed"):
            return (
                "Recraft paid plan not confirmed for this job. Free-plan images are public, owned by Recraft and "
                "not licensed for commercial use, and upgrading later does not transfer them. Ask Tim to confirm the "
                "plan, then run `imagekit.py confirm-recraft-paid --plan <name>`."
            )
    else:
        model = matched_model(data, tool_input)
        if model is None:
            cleared = [m["id"] for m in prov.get("replicate", {}).get("approved_models", [])]
            return (
                "No cleared Replicate model named in this call. Name the model as owner/name. Cleared on this job: "
                + (", ".join(cleared) if cleared else "none")
                + ". To clear one, read its licence on the model page and run `imagekit.py approve-model owner/name "
                "--licence ... --url ... --commercial yes`."
            )
        if not model.get("commercial"):
            return f"{model['id']} is recorded as not cleared for commercial use ({model.get('licence', 'no licence noted')})."
    budget = data.get("budget", {})
    used, usd = spend_so_far(job)
    cap_calls = budget.get("cap_calls")
    if cap_calls is not None and used >= int(cap_calls):
        return f"Generation budget reached: {used}/{cap_calls} calls on '{data.get('job')}'. Tim raises the cap with `imagekit.py budget --cap-calls N`."
    cap_usd = budget.get("cap_usd")
    cost = est_cost(data, provider, model)
    if cap_usd is not None and cost is not None and usd + cost > float(cap_usd):
        return f"Estimated spend would pass the cap: US${usd + cost:.2f} > US${float(cap_usd):.2f} on '{data.get('job')}'."
    return None


# --------------------------------------------------------------------------- output extraction

def _walk(obj):
    """Yield every dict and string inside obj, parsing JSON-looking strings."""
    stack = [obj]
    while stack:
        o = stack.pop()
        if isinstance(o, dict):
            yield o
            stack.extend(o.values())
        elif isinstance(o, list):
            stack.extend(o)
        elif isinstance(o, str):
            yield o
            s = o.strip()
            if s[:1] in "{[" and len(s) < 5_000_000:
                try:
                    stack.append(json.loads(s))
                except json.JSONDecodeError:
                    pass


def _urls(obj) -> list[str]:
    blob = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    out = []
    for u in ASSET_URL_RE.findall(blob):
        u = u.rstrip(".,;")
        host = u.split("/")[2].lower()
        ext = Path(u.split("?")[0]).suffix.lower()
        if host.startswith("mcp.") or host.startswith("www."):
            continue
        if ext in MEDIA_EXT or host.endswith("replicate.delivery") or host.startswith("img."):
            if u not in out:
                out.append(u)
    return out


def extract_outputs(tool_input, tool_response) -> tuple[list[str], list[tuple[bytes, str]]]:
    """(urls, inline images as (bytes, mime)) produced by a call, excluding inputs."""
    inputs = set(_urls(tool_input or {}))
    output_dicts, inline = [], []
    for o in _walk(tool_response):
        if isinstance(o, dict):
            if "output" in o and o["output"]:
                output_dicts.append(o["output"])
            if o.get("type") == "image":
                data = o.get("data") or (o.get("source") or {}).get("data")
                mime = o.get("mimeType") or o.get("media_type") or (o.get("source") or {}).get("media_type") or "image/png"
                if data:
                    try:
                        inline.append((base64.b64decode(data), mime))
                    except (ValueError, TypeError):
                        pass
    urls: list[str] = []
    for src in (output_dicts if output_dicts else [tool_response]):
        for u in _urls(src):
            if u not in inputs and u not in urls:
                urls.append(u)
    return urls, inline


def find_prompt(tool_input) -> str | None:
    for o in _walk(tool_input or {}):
        if isinstance(o, dict):
            for k in ("prompt", "text_prompt", "description"):
                if isinstance(o.get(k), str) and o[k].strip():
                    return o[k]
    return None


# --------------------------------------------------------------------------- capture

def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        path = os.environ.get(var)
        if path and Path(path).exists():
            try:
                ctx.load_verify_locations(path)
            except (ssl.SSLError, OSError):
                pass
    return ctx


def download(url: str, timeout: int = 20) -> tuple[bytes, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "creative-studio-imagekit/0.1"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
        return r.read(), (r.headers.get_content_type() or "")


def _ext(url: str | None, mime: str) -> str:
    if url:
        e = Path(url.split("?")[0]).suffix.lower()
        if e in MEDIA_EXT:
            return e
    return {"image/svg+xml": ".svg", "image/jpeg": ".jpg"}.get(mime) or mimetypes.guess_extension(mime or "") or ".bin"


def store(job: Path, rec: dict, content: bytes, mime: str) -> None:
    raw = job / "assets" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    f = raw / f"{rec['id']}-{rec['provider']}{_ext(rec.get('source_url'), mime)}"
    f.write_bytes(content)
    rec.update(
        file=str(f.relative_to(job)),
        sha256=hashlib.sha256(content).hexdigest(),
        bytes=len(content),
        mime=mime or mimetypes.guess_type(f.name)[0],
        fetched_at=iso(),
        status="candidate",
        error=None,
    )


def licence_basis(job_data: dict, provider: str, model: dict | None) -> dict:
    if provider == "recraft":
        r = job_data.get("providers", {}).get("recraft", {})
        return {"basis": f"Recraft paid plan ({r.get('plan', 'plan not named')}), confirmed {r.get('confirmed_at', '?')}",
                "commercial": bool(r.get("paid_plan_confirmed"))}
    if model:
        return {"basis": model.get("licence"), "url": model.get("url"), "commercial": bool(model.get("commercial")),
                "checked": model.get("checked")}
    return {"basis": "not recorded", "commercial": False}


def capture(job: Path, tool_name: str, tool_input, tool_response) -> list[dict]:
    provider, tool, _ = classify(tool_name)
    data = load_job(job)
    recs = read_jsonl(ledger_path(job))
    known = {r.get("source_url") for r in recs if r.get("source_url")}
    known_sha = {r.get("sha256") for r in recs if r.get("sha256")}
    model = matched_model(data, tool_input) if provider == "replicate" else None
    urls, inline = extract_outputs(tool_input, tool_response)
    base = {
        "job": data.get("job"),
        "client": data.get("client"),
        "provider": provider,
        "tool": tool,
        "model": (model or {}).get("id") or ((tool_input or {}).get("model") if isinstance(tool_input, dict) else None),
        "model_version": (model or {}).get("version"),
        "prompt": find_prompt(tool_input),
        "params": json.dumps(tool_input, ensure_ascii=False)[:4000],
        "licence": licence_basis(data, provider, model),
        "territory": None,
        "created_at": iso(),
        "note": None,
    }
    new = []
    for u in urls:
        if u in known:
            continue
        rec = dict(base, id=next_id(recs + new), source_url=u)
        try:
            content, mime = download(u)
            store(job, rec, content, mime)
        except Exception as e:  # network blocked, expired, TLS: record and move on
            rec.update(status="pending-fetch", error=f"{type(e).__name__}: {e}"[:300], file=None, sha256=None)
            if provider == "replicate":
                rec["expires_at"] = iso(now() + dt.timedelta(minutes=REPLICATE_TTL_MIN))
        new.append(rec)
    for content, mime in inline:
        sha = hashlib.sha256(content).hexdigest()
        if sha in known_sha:
            continue
        rec = dict(base, id=next_id(recs + new), source_url=None)
        store(job, rec, content, mime)
        known_sha.add(sha)
        new.append(rec)
    for r in new:
        append_jsonl(ledger_path(job), r)
    return new


# --------------------------------------------------------------------------- hooks

def _hook_input() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}


def cmd_hook_pre(_args) -> int:
    h = _hook_input()
    provider, _, spends = classify(h.get("tool_name", ""))
    if not provider or not spends:
        return 0
    try:
        job = find_job(h.get("cwd"))
    except AmbiguousJob as e:
        reason = (f"More than one active studio job below the working folder ({e}). Set STUDIO_JOB to the job "
                  "folder or deactivate the others, so the asset lands in the right client's ledger.")
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": reason}}))
        return 0
    if job is None:
        return 0
    reason = pre_check(job, h.get("tool_name", ""), h.get("tool_input"))
    if reason:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                                 "permissionDecisionReason": reason}}))
    return 0


def cmd_hook_post(_args) -> int:
    h = _hook_input()
    tool_name = h.get("tool_name", "")
    provider, tool, spends = classify(tool_name)
    if not provider:
        return 0
    try:
        job = find_job(h.get("cwd"))
    except AmbiguousJob as e:
        urls, inline = extract_outputs(h.get("tool_input"), h.get("tool_response"))
        if urls or inline:
            msg = (f"Ledger: outputs were NOT recorded because more than one studio job is active ({e}). "
                   "Set STUDIO_JOB and record them with `imagekit.py add`, or re-fetch them into the right job.")
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))
        return 0
    if job is None:
        return 0
    data = load_job(job)
    tin = h.get("tool_input")
    if spends:
        model = matched_model(data, tin) if provider == "replicate" else None
        append_jsonl(calls_path(job), {"at": iso(), "provider": provider, "tool": tool, "spends": True,
                                       "model": (model or {}).get("id"), "est_usd": est_cost(data, provider, model),
                                       "tool_use_id": h.get("tool_use_id")})
    new = capture(job, tool_name, tin, h.get("tool_response"))
    if not new and not spends:
        return 0
    used, usd = spend_so_far(job)
    cap = data.get("budget", {}).get("cap_calls")
    saved = [r["id"] for r in new if r.get("status") == "candidate"]
    pending = [r for r in new if r.get("status") == "pending-fetch"]
    parts = []
    if saved:
        parts.append(f"Ledger: saved {', '.join(saved)} to {job.name}/assets/raw.")
    if pending:
        exp = pending[0].get("expires_at")
        when = f" before {parse_iso(exp).strftime('%H:%M')} SGT, when Replicate deletes them" if exp else ""
        parts.append(
            f"Ledger: {', '.join(r['id'] for r in pending)} could not be downloaded ({pending[0]['error'][:80]}). "
            f"Save them{when}: run `imagekit.py fetch`, or ask Tim to add the image host to the network allowlist."
        )
    if spends:
        parts.append(f"Budget: {used}/{cap if cap is not None else 'no cap'} generation calls used.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": " ".join(parts)}}))
    return 0


# --------------------------------------------------------------------------- commands

def _job(args) -> Path:
    try:
        job = find_job(getattr(args, "job", None) or None)
    except AmbiguousJob as e:
        sys.exit(f"More than one active job below here ({e}). Pass --job <folder> or set STUDIO_JOB.")
    if job is None:
        sys.exit("Not inside a studio job. Run `imagekit.py init <folder> --client ... --job ...` or pass --job.")
    return job


def cmd_init(args) -> int:
    job = Path(args.folder).expanduser().resolve()
    if (job / JOB_FILE).exists():
        sys.exit(f"{job / JOB_FILE} already exists.")
    (job / "assets" / "raw").mkdir(parents=True, exist_ok=True)
    data = {
        "client": slug(args.client),
        "job": slug(args.job),
        "active": True,
        "created_at": iso(),
        "budget": {"cap_calls": args.cap_calls, "cap_usd": args.cap_usd,
                   "default_usd_per_call": {"recraft": None, "replicate": None}},
        "providers": {"recraft": {"paid_plan_confirmed": False, "plan": None, "confirmed_at": None, "styles": []},
                      "replicate": {"approved_models": []}},
    }
    save_job(job, data)
    ledger_path(job).touch()
    print(f"Initialised {job}/{JOB_FILE} for {data['client']} / {data['job']} (cap {args.cap_calls} calls).")
    return 0


def cmd_confirm_recraft_paid(args) -> int:
    job = _job(args)
    d = load_job(job)
    d["providers"]["recraft"].update(paid_plan_confirmed=True, plan=args.plan, confirmed_at=iso())
    save_job(job, d)
    print(f"Recraft paid plan '{args.plan}' confirmed for {d['job']}.")
    return 0


def cmd_approve_model(args) -> int:
    job = _job(args)
    if not re.match(r"^[\w.-]+/[\w.-]+$", args.model):
        sys.exit("Model must be owner/name, e.g. black-forest-labs/flux-1.1-pro.")
    d = load_job(job)
    models = [m for m in d["providers"]["replicate"]["approved_models"] if m["id"] != args.model]
    models.append({"id": args.model, "version": args.version, "licence": args.licence, "url": args.url,
                   "commercial": args.commercial == "yes", "est_usd_per_call": args.usd, "checked": iso()})
    d["providers"]["replicate"]["approved_models"] = models
    save_job(job, d)
    print(f"{args.model}: recorded, commercial={args.commercial}.")
    return 0


def cmd_add_style(args) -> int:
    job = _job(args)
    d = load_job(job)
    if not slug(args.name).startswith(d["client"] + "-"):
        sys.exit(f"Style names start with the client slug: {d['client']}-<territory>-v<n>.")
    d["providers"]["recraft"]["styles"].append({"name": slug(args.name), "style_id": args.style_id,
                                                 "model": args.model, "territory": args.territory, "created_at": iso()})
    save_job(job, d)
    print(f"Style {slug(args.name)} ({args.style_id}) recorded.")
    return 0


def cmd_budget(args) -> int:
    job = _job(args)
    d = load_job(job)
    b = d.setdefault("budget", {})
    if args.cap_calls is not None:
        b["cap_calls"] = args.cap_calls
    if args.cap_usd is not None:
        b["cap_usd"] = args.cap_usd
    for p in ("recraft", "replicate"):
        v = getattr(args, f"{p}_usd")
        if v is not None:
            b.setdefault("default_usd_per_call", {})[p] = v
    save_job(job, d)
    used, usd = spend_so_far(job)
    print(f"Budget: {used}/{b.get('cap_calls')} calls, est. US${usd:.2f}/{b.get('cap_usd') or 'no cap'}.")
    return 0


def cmd_set_active(args) -> int:
    job = Path(args.folder).expanduser().resolve()
    d = load_job(job)
    d["active"] = args.value == "yes"
    save_job(job, d)
    print(f"{d['job']}: active={d['active']}")
    return 0


def cmd_fetch(args) -> int:
    job = _job(args)
    recs = read_jsonl(ledger_path(job))
    done = failed = expired = 0
    for r in recs:
        if r.get("status") != "pending-fetch":
            continue
        exp = parse_iso(r.get("expires_at"))
        if exp and now() > exp:
            r.update(status="expired")
            expired += 1
            continue
        try:
            content, mime = download(r["source_url"])
            store(job, r, content, mime)
            done += 1
        except Exception as e:
            r["error"] = f"{type(e).__name__}: {e}"[:300]
            failed += 1
    write_jsonl(ledger_path(job), recs)
    print(f"Fetched {done}, still pending {failed}, expired {expired}.")
    return 1 if failed else 0


def cmd_add(args) -> int:
    job = _job(args)
    d = load_job(job)
    recs = read_jsonl(ledger_path(job))
    rec = {"id": next_id(recs), "job": d["job"], "client": d["client"], "provider": args.provider, "tool": "manual",
           "model": None, "model_version": None, "prompt": args.prompt, "params": None,
           "licence": {"basis": args.licence, "url": args.source, "commercial": args.commercial == "yes"},
           "territory": args.territory, "created_at": iso(), "note": args.note, "source_url": args.source}
    src = Path(args.file).expanduser()
    content = src.read_bytes()
    store(job, rec, content, mimetypes.guess_type(src.name)[0] or "")
    append_jsonl(ledger_path(job), rec)
    print(f"{rec['id']} recorded from {src.name}.")
    return 0


def cmd_mark(args) -> int:
    job = _job(args)
    recs = read_jsonl(ledger_path(job))
    ids = set(args.ids)
    hit = 0
    for r in recs:
        if r["id"] in ids:
            if args.status in ("selected", "delivered") and not r.get("file"):
                sys.exit(f"{r['id']} has no saved file ({r.get('status')}); fetch it before selecting it.")
            if args.status in ("selected", "delivered") and not (r.get("licence") or {}).get("commercial"):
                sys.exit(f"{r['id']} has no commercial licence basis recorded; it cannot be selected for a client.")
            r["status"] = args.status
            if args.territory:
                r["territory"] = args.territory
            if args.note:
                r["note"] = args.note
            hit += 1
    write_jsonl(ledger_path(job), recs)
    print(f"Marked {hit} as {args.status}.")
    return 0 if hit == len(ids) else 1


def cmd_status(args) -> int:
    job = _job(args)
    d = load_job(job)
    recs = read_jsonl(ledger_path(job))
    used, usd = spend_so_far(job)
    b = d.get("budget", {})
    counts = {s: sum(1 for r in recs if r.get("status") == s) for s in STATUSES}
    print(f"{d['client']} / {d['job']}  active={d.get('active', True)}")
    print(f"  Budget: {used}/{b.get('cap_calls')} calls, est. US${usd:.2f} (cap {b.get('cap_usd') or 'none'})")
    rp = d["providers"]["recraft"]
    print(f"  Recraft paid plan: {'confirmed (' + str(rp.get('plan')) + ')' if rp.get('paid_plan_confirmed') else 'NOT confirmed'}; styles: {len(rp.get('styles', []))}")
    am = d["providers"]["replicate"]["approved_models"]
    print(f"  Replicate models cleared: {', '.join(m['id'] for m in am if m.get('commercial')) or 'none'}")
    print("  Assets: " + ", ".join(f"{k} {v}" for k, v in counts.items() if v) if recs else "  Assets: none")
    for r in recs:
        if r.get("status") == "pending-fetch":
            exp = parse_iso(r.get("expires_at"))
            left = f", {int((exp - now()).total_seconds() // 60)} min left" if exp else ""
            print(f"  PENDING {r['id']} {r['provider']}{left}: {r['source_url']}")
    return 0


def cmd_report(args) -> int:
    job = _job(args)
    d = load_job(job)
    recs = read_jsonl(ledger_path(job))
    chosen = [r for r in recs if r.get("status") in ("selected", "delivered")]
    lines = [
        f"# Image provenance: {d['client']} / {d['job']}",
        "",
        f"Generated {now().strftime('%d %b %Y %H:%M')} SGT from `assets/ledger.jsonl`. "
        f"{len(chosen)} assets selected or delivered out of {len(recs)} recorded.",
        "",
        "Every asset below was generated or sourced for this job and carries a commercial licence basis. "
        "AI-generated imagery may not be eligible for copyright protection in every jurisdiction; "
        "names and marks need separate trademark clearance.",
        "",
        "| ID | File | Source | Model | Prompt | Licence basis | SHA-256 |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in chosen:
        prompt = (r.get("prompt") or "").replace("|", "/").replace("\n", " ")
        prompt = prompt[:90] + ("..." if len(prompt) > 90 else "")
        lic = (r.get("licence") or {}).get("basis") or ""
        lines.append(f"| {r['id']} | {r.get('file')} | {r['provider']} | {r.get('model') or ''} | {prompt} | "
                     f"{lic.replace('|', '/')} | {(r.get('sha256') or '')[:12]} |")
    styles = d["providers"]["recraft"].get("styles", [])
    if styles:
        lines += ["", "## Recraft styles", "", "| Name | Style ID | Model | Territory |", "|---|---|---|---|"]
        lines += [f"| {s['name']} | {s['style_id']} | {s.get('model') or ''} | {s.get('territory') or ''} |" for s in styles]
    models = d["providers"]["replicate"]["approved_models"]
    if models:
        lines += ["", "## Replicate models used", "", "| Model | Version | Licence | Checked |", "|---|---|---|---|"]
        lines += [f"| {m['id']} | {m.get('version') or 'latest at run'} | [{m.get('licence')}]({m.get('url')}) | "
                  f"{(m.get('checked') or '')[:10]} |" for m in models]
    out = job / "assets" / "provenance.md"
    out.write_text("\n".join(lines) + "\n")
    print(f"Wrote {out.relative_to(job.parent)} ({len(chosen)} assets).")
    return 0


def cmd_sheet(args) -> int:
    """Write assets/contact-sheet.html: every saved asset, grouped by status, for the panel and gate packs."""
    import html as h
    job = _job(args)
    d = load_job(job)
    recs = [r for r in read_jsonl(ledger_path(job)) if r.get("file")]
    order = ["selected", "delivered", "candidate", "rejected"]
    if not args.all:
        order = [s for s in order if s != "rejected"]
    groups = []
    for s in order:
        items = [r for r in recs if r.get("status") == s]
        if not items:
            continue
        cards = []
        for r in items:
            src = h.escape(os.path.relpath(job / r["file"], job / "assets"))
            media = (f'<video src="{src}" muted loop controls></video>' if (r.get("mime") or "").startswith("video")
                     else f'<img src="{src}" alt="{h.escape(r["id"])}" loading="lazy">')
            prompt = h.escape((r.get("prompt") or r.get("note") or "")[:160])
            cards.append(
                f'<figure>{media}<figcaption><b>{h.escape(r["id"])}</b> · {h.escape(r["provider"])}'
                f'{" · " + h.escape(r["model"]) if r.get("model") else ""}'
                f'{" · " + h.escape(r["territory"]) if r.get("territory") else ""}<br><span>{prompt}</span></figcaption></figure>'
            )
        groups.append(f"<h2>{s.capitalize()} ({len(items)})</h2><div class=grid>{''.join(cards)}</div>")
    page = f"""<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{h.escape(d['client'])} contact sheet</title>
<style>:root{{--bg:#fafaf8;--fg:#1a1a1a;--mute:#6b6b6b;--line:#e2e2de;--tile:#fff}}
@media (prefers-color-scheme:dark){{:root{{--bg:#141414;--fg:#eee;--mute:#9a9a9a;--line:#2c2c2c;--tile:#1d1d1d}}}}
body{{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif}}
h1{{font-size:20px;font-weight:600;margin:0 0 4px}}h2{{font-size:15px;font-weight:600;margin:28px 0 10px}}
p{{color:var(--mute);margin:0}}.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}}
figure{{margin:0;background:var(--tile);border:1px solid var(--line);border-radius:8px;overflow:hidden}}
img,video{{display:block;width:100%;aspect-ratio:1;object-fit:contain;background:repeating-conic-gradient(#8881 0 25%,#0000 0 50%) 0 0/16px 16px}}
figcaption{{padding:8px 10px;font-size:12px}}figcaption span{{color:var(--mute)}}</style>
<h1>{h.escape(d['client'])} / {h.escape(d['job'])}</h1><p>Contact sheet, {now().strftime('%d %b %Y %H:%M')} SGT. {len(recs)} saved assets. AI-generated concepts unless the ledger says otherwise.</p>
{''.join(groups) or '<p>No saved assets yet.</p>'}</html>
"""
    out = job / "assets" / "contact-sheet.html"
    out.write_text(page)
    print(f"Wrote {out.relative_to(job.parent)} ({len(recs)} assets).")
    return 0


# --------------------------------------------------------------------------- cli

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="imagekit.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="create studio-job.json and the assets folders")
    p.add_argument("folder")
    p.add_argument("--client", required=True)
    p.add_argument("--job", required=True)
    p.add_argument("--cap-calls", type=int, default=60)
    p.add_argument("--cap-usd", type=float, default=None)
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("confirm-recraft-paid", help="record that the Recraft account is on a paid plan")
    p.add_argument("--plan", required=True)
    p.add_argument("--job")
    p.set_defaults(fn=cmd_confirm_recraft_paid)

    p = sub.add_parser("approve-model", help="clear a Replicate model for this job after reading its licence")
    p.add_argument("model")
    p.add_argument("--licence", required=True)
    p.add_argument("--url", required=True)
    p.add_argument("--commercial", choices=["yes", "no"], required=True)
    p.add_argument("--version")
    p.add_argument("--usd", type=float, help="estimated US$ per call")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_approve_model)

    p = sub.add_parser("add-style", help="record a Recraft custom style for this client")
    p.add_argument("name")
    p.add_argument("--style-id", required=True)
    p.add_argument("--model")
    p.add_argument("--territory")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_add_style)

    p = sub.add_parser("budget", help="show or change the generation budget")
    p.add_argument("--cap-calls", type=int)
    p.add_argument("--cap-usd", type=float)
    p.add_argument("--recraft-usd", type=float, help="estimated US$ per Recraft call")
    p.add_argument("--replicate-usd", type=float, help="default estimated US$ per Replicate call")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_budget)

    p = sub.add_parser("set-active", help="mark a job active or inactive")
    p.add_argument("folder")
    p.add_argument("value", choices=["yes", "no"])
    p.set_defaults(fn=cmd_set_active)

    p = sub.add_parser("fetch", help="download pending outputs before they expire")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_fetch)

    p = sub.add_parser("add", help="record a non-generated asset (stock, photographer, client-supplied)")
    p.add_argument("file")
    p.add_argument("--provider", required=True, help="stock, photographer, illustrator, client, manual")
    p.add_argument("--licence", required=True)
    p.add_argument("--commercial", choices=["yes", "no"], required=True)
    p.add_argument("--source")
    p.add_argument("--prompt")
    p.add_argument("--territory")
    p.add_argument("--note")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_add)

    p = sub.add_parser("mark", help="set asset status: candidate, selected, rejected, delivered")
    p.add_argument("status", choices=["candidate", "selected", "rejected", "delivered"])
    p.add_argument("ids", nargs="+")
    p.add_argument("--territory")
    p.add_argument("--note")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_mark)

    p = sub.add_parser("status", help="budget, licences and pending downloads")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("report", help="write assets/provenance.md for handoff")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("sheet", help="write assets/contact-sheet.html for review")
    p.add_argument("--all", action="store_true", help="include rejected assets")
    p.add_argument("--job")
    p.set_defaults(fn=cmd_sheet)

    sub.add_parser("hook-pre", help="PreToolUse hook (reads hook JSON on stdin)").set_defaults(fn=cmd_hook_pre)
    sub.add_parser("hook-post", help="PostToolUse hook (reads hook JSON on stdin)").set_defaults(fn=cmd_hook_post)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
