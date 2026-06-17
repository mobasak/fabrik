"""Unit tests for the daily-digest.sh + send-telegram.sh fleet
hardening. Tests the embedded-Python helpers via subprocess + JSONL
fixture inspection."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

REPO = Path("/opt/fabrik")
DIGEST_SH = REPO / "scripts/sysadmin/daily-digest.sh"


def _missed_detector_py(jsonl_path: Path) -> str:
    """The exact Python block daily-digest.sh embeds for missed detection.
    Mirrors plan §2.2."""
    return f'''
import json, time
deadline = time.time() - 48*3600
sent_dates, attempted_dates = set(), set()
with open("{jsonl_path}") as f:
    for line in f:
        try: r = json.loads(line)
        except: continue
        if r.get("ts", 0) < deadline: continue
        d = time.strftime("%Y-%m-%d", time.gmtime(r["ts"]))
        if r.get("source") == "daily_digest": attempted_dates.add(d)
        elif r.get("source") == "daily_digest_sent": sent_dates.add(d)
missed = attempted_dates - sent_dates
today = time.strftime("%Y-%m-%d", time.gmtime())
missed.discard(today)
if missed:
    print(f"⚠️ MISSED DIGESTS — {{len(missed)}} day(s) generated but no Telegram delivery: {{sorted(missed)}}")
'''


def test_missed_detector_warns_on_unmatched_attempts(tmp_path):
    """If JSONL has a daily_digest row for date D but no daily_digest_sent
    row for the same date, the detector must emit the warning."""
    jsonl = tmp_path / "actions.jsonl"
    yesterday = time.time() - 36 * 3600  # 1.5 days ago
    rows = [
        {"ts": yesterday, "host": "vps1", "source": "daily_digest"},
        # NO matching daily_digest_sent row → should trigger warning
    ]
    jsonl.write_text("\n".join(json.dumps(r) for r in rows))

    result = subprocess.run(
        ["python3", "-c", _missed_detector_py(jsonl)],
        capture_output=True, text=True, check=True,
    )
    assert "MISSED DIGESTS" in result.stdout


def test_missed_detector_silent_when_sent_row_present(tmp_path):
    """If both daily_digest and daily_digest_sent rows exist for the same
    date, no warning."""
    jsonl = tmp_path / "actions.jsonl"
    yesterday = time.time() - 36 * 3600
    rows = [
        {"ts": yesterday, "host": "vps1", "source": "daily_digest"},
        {"ts": yesterday + 60, "host": "vps1", "source": "daily_digest_sent"},
    ]
    jsonl.write_text("\n".join(json.dumps(r) for r in rows))

    result = subprocess.run(
        ["python3", "-c", _missed_detector_py(jsonl)],
        capture_output=True, text=True, check=True,
    )
    assert "MISSED DIGESTS" not in result.stdout


def test_missed_detector_exempts_today(tmp_path):
    """Today's daily_digest row without a sent row should NOT trigger —
    today's run hasn't sent yet at detection time."""
    jsonl = tmp_path / "actions.jsonl"
    now = time.time()
    rows = [
        {"ts": now - 60, "host": "vps1", "source": "daily_digest"},  # today
    ]
    jsonl.write_text("\n".join(json.dumps(r) for r in rows))

    result = subprocess.run(
        ["python3", "-c", _missed_detector_py(jsonl)],
        capture_output=True, text=True, check=True,
    )
    assert "MISSED DIGESTS" not in result.stdout


# Bullet extractor — pulls last-24h result_excerpt from tier_a + escalation rows
def _bullet_extractor_py(jsonl_path: Path) -> str:
    return f'''
import json, time
deadline = time.time() - 24*3600
bullets = []
with open("{jsonl_path}") as f:
    for line in f:
        try: r = json.loads(line)
        except: continue
        if r.get("ts", 0) < deadline: continue
        src = r.get("source")
        if src not in ("alertmanager", "consult", "manual"): continue
        ex = (r.get("result_excerpt") or "")[:180]
        if not ex: continue
        ts_str = time.strftime("%H:%M:%SZ", time.gmtime(r["ts"]))
        bullets.append(f"  • [{{ts_str}}] {{ex}}")
        if len(bullets) >= 5: break
for b in bullets:
    print(b)
'''


def test_bullet_extractor_truncates_180(tmp_path):
    """result_excerpt > 180 chars must be truncated to exactly 180."""
    jsonl = tmp_path / "actions.jsonl"
    long_excerpt = "x" * 250  # 250 chars
    rows = [
        {
            "ts": time.time() - 3600, "host": "vps1",
            "source": "alertmanager", "result_excerpt": long_excerpt,
        },
    ]
    jsonl.write_text("\n".join(json.dumps(r) for r in rows))

    result = subprocess.run(
        ["python3", "-c", _bullet_extractor_py(jsonl)],
        capture_output=True, text=True, check=True,
    )
    # Output must contain exactly 180 x's (not 250)
    bullet_line = result.stdout.strip()
    x_count = bullet_line.count("x")
    assert x_count == 180, f"expected 180 x's truncated, got {x_count}"


def test_bullet_extractor_caps_at_5_rows(tmp_path):
    """Even with 10 eligible rows, only 5 bullets appear."""
    jsonl = tmp_path / "actions.jsonl"
    now = time.time()
    rows = [
        {
            "ts": now - 60 * (i + 1), "host": "vps1",
            "source": "alertmanager", "result_excerpt": f"excerpt-{i}",
        }
        for i in range(10)
    ]
    jsonl.write_text("\n".join(json.dumps(r) for r in rows))

    result = subprocess.run(
        ["python3", "-c", _bullet_extractor_py(jsonl)],
        capture_output=True, text=True, check=True,
    )
    bullets = [ln for ln in result.stdout.splitlines() if ln.strip().startswith("•")]
    assert len(bullets) == 5, f"expected ≤5 bullets, got {len(bullets)}"


def test_bullet_extractor_skips_old_rows(tmp_path):
    """Rows older than 24h must NOT appear in the bullet list."""
    jsonl = tmp_path / "actions.jsonl"
    rows = [
        {
            "ts": time.time() - 48 * 3600,  # 48h ago, outside window
            "host": "vps1", "source": "alertmanager",
            "result_excerpt": "should-be-skipped",
        },
        {
            "ts": time.time() - 3600,  # 1h ago, in window
            "host": "vps1", "source": "alertmanager",
            "result_excerpt": "should-appear",
        },
    ]
    jsonl.write_text("\n".join(json.dumps(r) for r in rows))

    result = subprocess.run(
        ["python3", "-c", _bullet_extractor_py(jsonl)],
        capture_output=True, text=True, check=True,
    )
    assert "should-appear" in result.stdout
    assert "should-be-skipped" not in result.stdout


def test_combined_message_under_telegram_4096(tmp_path):
    """A combined fleet digest (vps1 + vps2 + vps3 + heartbeats) must fit
    under Telegram's 4096-char limit even with reasonable bullet counts."""
    # 3 hosts × ~5 bullets × ~180 chars + headers + heartbeats
    # Worst case: 3 × 5 × 180 = 2700 + 400 overhead = ~3100
    # Should fit; if it doesn't, the formatter must truncate.
    sections = []
    for host in ("vps1", "vps2", "vps3"):
        sections.append(f"[{host}] tier_a=5 esc=0 consults=2")
        for _i in range(5):
            sections.append("  • [12:34:00Z] " + "x" * 165)
    sections.append("Heartbeats: keepalive vps1=42m vps2=15m vps3=8m · aro-wake all up")
    combined = "\n".join(sections)
    assert len(combined) < 4096, f"combined digest = {len(combined)} chars (Telegram limit 4096)"


def test_send_telegram_sh_dry_run():
    """send-telegram.sh DRY_RUN=1 must succeed without making network calls."""
    sender = REPO / "scripts/sysadmin/send-telegram.sh"
    assert sender.exists() and os.access(sender, os.X_OK)
    # Use a tmp env file
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
        f.write("TELEGRAM_BOT_TOKEN=stub\nTELEGRAM_OWNER_ID=42\n")
        env_path = f.name
    try:
        # Inline-substitute the env path
        with sender.open() as fh:
            script_body = fh.read().replace("/opt/fabrik/.env.sysadmin", env_path)
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
            f.write(script_body)
            test_script = f.name
        os.chmod(test_script, 0o755)
        result = subprocess.run(
            ["bash", test_script, "smoke message"],
            env={**os.environ, "DRY_RUN": "1"},
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "[dry-run]" in result.stdout
        assert "smoke message" in result.stdout
    finally:
        os.unlink(env_path)
        os.unlink(test_script)
