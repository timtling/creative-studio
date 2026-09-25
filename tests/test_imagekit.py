"""Tests for skills/image-generation/scripts/imagekit.py. Run: python3 -m pytest tests -q"""
import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "image-generation" / "scripts" / "imagekit.py"
sys.path.insert(0, str(SCRIPT.parent))
import imagekit as ik  # noqa: E402

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def run(*args, stdin=None, cwd=None, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin, capture_output=True, text=True,
                          cwd=cwd, env=env)


@pytest.fixture
def job(tmp_path, monkeypatch):
    monkeypatch.delenv("STUDIO_JOB", raising=False)
    j = tmp_path / "acme-sprint"
    assert ik.main(["init", str(j), "--client", "Acme", "--job", "Acme Brand Sprint", "--cap-calls", "3"]) == 0
    return j


def hook(tool, tool_input, cwd, response=None, event="pre"):
    payload = {"tool_name": tool, "tool_input": tool_input, "cwd": str(cwd)}
    if response is not None:
        payload["tool_response"] = response
    r = run(f"hook-{event}", stdin=json.dumps(payload), cwd=cwd)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else None


def test_classify():
    assert ik.classify("mcp__Recraft__generate_image") == ("recraft", "generate_image", True)
    assert ik.classify("mcp__Recraft__list_styles")[2] is False
    assert ik.classify("mcp__Recraft__vectorize_image")[2] is True
    assert ik.classify("mcp__replicate__create_predictions") == ("replicate", "create_predictions", True)
    assert ik.classify("mcp__Replicate__get_predictions")[2] is False
    assert ik.classify("mcp__Replicate__search_models")[2] is False
    assert ik.classify("mcp__Gmail__send_message")[0] is None
    assert ik.classify("Write")[0] is None


def test_recraft_needs_paid_plan(job):
    out = hook("mcp__Recraft__generate_image", {"prompt": "a harbour at dawn"}, job)
    assert out["permissionDecision"] == "deny" and "paid plan" in out["permissionDecisionReason"]
    ik.main(["confirm-recraft-paid", "--plan", "Pro", "--job", str(job)])
    assert hook("mcp__Recraft__generate_image", {"prompt": "a harbour at dawn"}, job) is None


def test_reads_are_never_blocked(job):
    assert hook("mcp__Recraft__list_styles", {}, job) is None
    assert hook("mcp__Replicate__search_models", {"query": "flux"}, job) is None


def test_replicate_needs_cleared_commercial_model(job):
    call = {"model_owner": "black-forest-labs", "model_name": "flux-1.1-pro", "input": {"prompt": "x"}}
    out = hook("mcp__Replicate__create_models_predictions", call, job)
    assert out["permissionDecision"] == "deny" and "none" in out["permissionDecisionReason"]
    ik.main(["approve-model", "black-forest-labs/flux-1.1-pro", "--licence", "Commercial via Replicate",
             "--url", "https://replicate.com/black-forest-labs/flux-1.1-pro", "--commercial", "yes", "--job", str(job)])
    assert hook("mcp__Replicate__create_models_predictions", call, job) is None
    ik.main(["approve-model", "someone/research-model", "--licence", "Non-commercial", "--url", "https://x",
             "--commercial", "no", "--job", str(job)])
    out = hook("mcp__Replicate__create_predictions", {"version": "someone/research-model:abc"}, job)
    assert out["permissionDecision"] == "deny" and "not cleared" in out["permissionDecisionReason"]


def test_budget_cap(job):
    ik.main(["confirm-recraft-paid", "--plan", "Pro", "--job", str(job)])
    for _ in range(3):
        ik.append_jsonl(ik.calls_path(job), {"spends": True, "est_usd": None})
    out = hook("mcp__Recraft__generate_image", {"prompt": "x"}, job)
    assert out["permissionDecision"] == "deny" and "3/3" in out["permissionDecisionReason"]


def test_usd_cap(job):
    ik.main(["confirm-recraft-paid", "--plan", "Pro", "--job", str(job)])
    ik.main(["budget", "--cap-calls", "100", "--cap-usd", "1", "--recraft-usd", "0.4", "--job", str(job)])
    ik.append_jsonl(ik.calls_path(job), {"spends": True, "est_usd": 0.4})
    ik.append_jsonl(ik.calls_path(job), {"spends": True, "est_usd": 0.4})
    out = hook("mcp__Recraft__generate_image", {"prompt": "x"}, job)
    assert out["permissionDecision"] == "deny" and "cap" in out["permissionDecisionReason"]


def test_outside_a_job_is_allowed(tmp_path, monkeypatch):
    monkeypatch.delenv("STUDIO_JOB", raising=False)
    assert hook("mcp__Recraft__generate_image", {"prompt": "x"}, tmp_path) is None


def test_two_active_jobs_block_spend(tmp_path, monkeypatch):
    monkeypatch.delenv("STUDIO_JOB", raising=False)
    for c in ("acme", "zenith"):
        ik.main(["init", str(tmp_path / "jobs" / c), "--client", c, "--job", f"{c}-sprint"])
    out = hook("mcp__Recraft__generate_image", {"prompt": "x"}, tmp_path)
    assert out["permissionDecision"] == "deny" and "More than one" in out["permissionDecisionReason"]
    ik.main(["set-active", str(tmp_path / "jobs" / "zenith"), "no"])
    out = hook("mcp__Recraft__generate_image", {"prompt": "x"}, tmp_path)
    assert "paid plan" in out["permissionDecisionReason"]  # resolves to acme, which is unconfirmed


def test_extract_outputs_prefers_output_and_skips_inputs():
    tin = {"input": {"image": "https://replicate.delivery/in/ref.png", "prompt": "p"}}
    resp = [{"type": "text", "text": json.dumps({
        "id": "abc", "status": "succeeded",
        "input": {"image": "https://replicate.delivery/in/ref.png"},
        "output": ["https://replicate.delivery/xezq/out-1.webp", "https://replicate.delivery/xezq/out-2.webp"],
        "urls": {"get": "https://api.replicate.com/v1/predictions/abc"}})}]
    urls, inline = ik.extract_outputs(tin, resp)
    assert urls == ["https://replicate.delivery/xezq/out-1.webp", "https://replicate.delivery/xezq/out-2.webp"]
    assert inline == []


def test_extract_recraft_text_and_inline_image():
    resp = {"content": [
        {"type": "text", "text": "Done. Image: https://img.recraft.ai/abc123/raster_image.png (see mcp.recraft.ai)"},
        {"type": "image", "data": base64.b64encode(PNG).decode(), "mimeType": "image/png"}]}
    urls, inline = ik.extract_outputs({"prompt": "p"}, resp)
    assert urls == ["https://img.recraft.ai/abc123/raster_image.png"]
    assert inline == [(PNG, "image/png")]


def test_capture_saves_and_records(job, monkeypatch):
    ik.main(["confirm-recraft-paid", "--plan", "Pro", "--job", str(job)])
    monkeypatch.setattr(ik, "download", lambda url, timeout=20: (PNG, "image/png"))
    resp = {"content": [{"type": "text", "text": "https://img.recraft.ai/a1/one.png https://img.recraft.ai/a2/two.svg"}]}
    new = ik.capture(job, "mcp__Recraft__generate_image", {"prompt": "harbour, dawn", "style": "x"}, resp)
    assert [r["id"] for r in new] == ["A-001", "A-002"]
    assert new[0]["status"] == "candidate" and (job / new[0]["file"]).read_bytes() == PNG
    assert new[1]["file"].endswith(".svg")
    assert new[0]["prompt"] == "harbour, dawn" and new[0]["licence"]["commercial"] is True
    assert ik.capture(job, "mcp__Recraft__generate_image", {"prompt": "x"}, resp) == []  # dedupe by URL


def test_capture_pending_then_fetch(job, monkeypatch):
    def fail(url, timeout=20):
        raise OSError("blocked by allowlist")
    monkeypatch.setattr(ik, "download", fail)
    ik.main(["approve-model", "google/imagen-4", "--licence", "Commercial", "--url", "https://x", "--commercial", "yes",
             "--job", str(job)])
    resp = {"output": "https://replicate.delivery/xezq/hero.jpg"}
    new = ik.capture(job, "mcp__Replicate__get_predictions", {"id": "p1", "model": "google/imagen-4"}, resp)
    assert new[0]["status"] == "pending-fetch" and new[0]["expires_at"] and new[0]["model"] == "google/imagen-4"
    monkeypatch.setattr(ik, "download", lambda url, timeout=20: (PNG, "image/jpeg"))
    assert ik.main(["fetch", "--job", str(job)]) == 0
    rec = ik.read_jsonl(ik.ledger_path(job))[0]
    assert rec["status"] == "candidate" and rec["file"].endswith(".jpg")


def test_expired_is_marked(job):
    ik.append_jsonl(ik.ledger_path(job), {"id": "A-001", "provider": "replicate", "status": "pending-fetch",
                                          "source_url": "https://replicate.delivery/x.png",
                                          "expires_at": "2020-01-01T00:00:00+08:00"})
    ik.main(["fetch", "--job", str(job)])
    assert ik.read_jsonl(ik.ledger_path(job))[0]["status"] == "expired"


def test_mark_guards_and_report(job, monkeypatch, tmp_path):
    ik.main(["confirm-recraft-paid", "--plan", "Pro", "--job", str(job)])
    monkeypatch.setattr(ik, "download", lambda url, timeout=20: (PNG, "image/png"))
    ik.capture(job, "mcp__Recraft__generate_image", {"prompt": "mark | test"}, "https://img.recraft.ai/z/1.png")
    ik.append_jsonl(ik.ledger_path(job), {"id": "A-002", "provider": "replicate", "status": "pending-fetch",
                                          "licence": {"commercial": True}})
    with pytest.raises(SystemExit):
        ik.main(["mark", "selected", "A-002", "--job", str(job)])
    photo = tmp_path / "stock.jpg"
    photo.write_bytes(PNG)
    ik.main(["add", str(photo), "--provider", "stock", "--licence", "Editorial only", "--commercial", "no",
             "--job", str(job)])
    with pytest.raises(SystemExit):
        ik.main(["mark", "selected", "A-003", "--job", str(job)])
    assert ik.main(["mark", "selected", "A-001", "--territory", "T2", "--job", str(job)]) == 0
    ik.main(["add-style", "acme-t2-v1", "--style-id", "st_123", "--model", "recraftv4", "--job", str(job)])
    with pytest.raises(SystemExit):
        ik.main(["add-style", "zenith-t1-v1", "--style-id", "st_9", "--job", str(job)])
    ik.main(["report", "--job", str(job)])
    rep = (job / "assets" / "provenance.md").read_text()
    assert "A-001" in rep and "mark / test" in rep and "acme-t2-v1" in rep and "A-003" not in rep
    ik.main(["sheet", "--job", str(job)])
    sheet = (job / "assets" / "contact-sheet.html").read_text()
    assert 'src="raw/A-001-recraft.png"' in sheet and "Selected (1)" in sheet and "mark | test" in sheet


def test_hook_post_end_to_end(job):
    """No network to the image host from the test runner: the asset is recorded as pending and the agent is told."""
    ik.main(["confirm-recraft-paid", "--plan", "Pro", "--job", str(job)])
    out = hook("mcp__Recraft__generate_image", {"prompt": "p"}, job,
               response=[{"type": "text", "text": "https://img.recraft.ai/nonexistent-test/x.png"}], event="post")
    ctx = out["additionalContext"]
    assert "Budget: 1/3" in ctx and ("A-001" in ctx)
    assert len(ik.read_jsonl(ik.calls_path(job))) == 1


def test_hook_ignores_other_tools(job):
    assert hook("mcp__Gmail__send_message", {"to": "x"}, job) is None
    assert hook("Write", {"file_path": "x"}, job, response={}, event="post") is None
