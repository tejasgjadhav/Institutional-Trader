"""CONFIG LEDGER — every tunable change recorded, with the exact commit to roll back to.

WHY. On 5-Aug-2026 the user asked "maybe we changed something on Monday or Tuesday" after a bad
GRASIM signal. Answering it needed a hand-run `git log -- engine/config.py`, and even that only shows
changes that were COMMITTED — a value edited and left uncommitted for a session would be invisible.
The answer mattered (it was no: zero config changes on Monday, the first Tuesday change landed at
18:36, three hours after the signal fired at 15:10), and it should not have taken archaeology.

WHAT IT DOES. On every engine start it snapshots every tunable in `engine/config.py`, diffs it against
the previous snapshot, and if anything moved it writes:
  1. a row in `data/engine.db` -> table `config_changes`   (queryable history)
  2. an entry in `CONFIG_CHANGELOG.md` at the repo root    (human-readable, committed -> visible on
     GitHub, which is the "system log on github" the user asked for)
  3. a full snapshot in `data/config_snapshots/`           (the exact prior state, for comparison)

HOW ROLLBACK WORKS. `engine/config.py` is git-tracked, so git IS the rollback mechanism and this
module deliberately does not try to rewrite config itself — auto-editing a live trading config is a
worse failure mode than any it prevents. Each entry records the git SHA that was checked out when the
snapshot was taken, so reverting is:

    git checkout <sha> -- engine/config.py

and `python -m engine.config_ledger --rollback-cmd` prints that line for the last change.

READ-ONLY with respect to trading. It reads config, writes only its own db table, changelog and
snapshots, and every path is wrapped so a ledger failure can never disturb the engine.
"""
import os
import json
import glob
import sqlite3
import logging
import subprocess
from datetime import datetime

from engine import config
from engine.config import DATA_DIR, IST

logger = logging.getLogger(__name__)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# ABSOLUTE paths, always. config.DATA_DIR is RELATIVE ("data/..."), so it resolves against the
# caller's cwd — a ledger run from anywhere but the repo root silently wrote to a different
# engine.db and its history vanished (observed 5-Aug-2026). A ledger that loses history is worse
# than none, so anchor everything to the repo root regardless of where the process was started.
_DATA = DATA_DIR if os.path.isabs(DATA_DIR) else os.path.join(REPO_ROOT, DATA_DIR)
SNAP_DIR = os.path.join(_DATA, "config_snapshots")
CHANGELOG = os.path.join(REPO_ROOT, "CONFIG_CHANGELOG.md")
DB_PATH = os.path.join(_DATA, "engine.db")

# Values that are not tunables and would make every snapshot look "changed".
_SKIP = {"IST", "DATA_DIR", "LOG_DIR", "BASE_DIR", "REPO_ROOT"}


def _git(*args) -> str:
    try:
        return subprocess.run(["git", "-C", REPO_ROOT, *args], capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def snapshot() -> dict:
    """Every UPPERCASE tunable in config.py, JSON-safe. Callables/modules are skipped."""
    out = {}
    for k in dir(config):
        if not k.isupper() or k in _SKIP or k.startswith("_"):
            continue
        v = getattr(config, k)
        if callable(v) or isinstance(v, type(os)):
            continue
        try:
            json.dumps(v)
            out[k] = v
        except (TypeError, ValueError):
            out[k] = repr(v)
    return out


def _last_snapshot() -> tuple:
    """(values, path) of the most recent snapshot, or ({}, None)."""
    try:
        files = sorted(glob.glob(os.path.join(SNAP_DIR, "*.json")))
        if not files:
            return {}, None
        with open(files[-1]) as f:
            return json.load(f).get("values", {}), files[-1]
    except Exception:
        return {}, None


def _diff(old: dict, new: dict) -> list:
    """[(key, before, after)] — 'added'/'removed' shown as the sentinel string ∅."""
    keys = sorted(set(old) | set(new))
    return [(k, old.get(k, "∅"), new.get(k, "∅")) for k in keys if old.get(k, "∅") != new.get(k, "∅")]


def _write_db(ts: str, sha: str, changes: list) -> None:
    con = sqlite3.connect(DB_PATH, timeout=10)
    try:
        con.execute("""CREATE TABLE IF NOT EXISTS config_changes (
                         ts TEXT, git_sha TEXT, key TEXT, before TEXT, after TEXT)""")
        con.executemany("INSERT INTO config_changes VALUES (?,?,?,?,?)",
                        [(ts, sha, k, json.dumps(b), json.dumps(a)) for k, b, a in changes])
        con.commit()
    finally:
        con.close()


def _write_changelog(ts: str, sha: str, subject: str, changes: list) -> None:
    head = ("# Config changelog\n\n"
            "Every change to a tunable in `engine/config.py`, recorded automatically by\n"
            "`engine/config_ledger.py` on engine start. Newest first.\n\n"
            "**To roll back a change**, `engine/config.py` is git-tracked, so:\n\n"
            "```bash\n"
            "git checkout <the SHA shown below> -- engine/config.py\n"
            "```\n\n"
            "then restart the engine. The ledger never rewrites config itself — auto-editing a live\n"
            "trading config is a worse failure mode than the one it would prevent.\n\n---\n\n")
    entry = [f"## {ts}", ""]
    if sha:
        entry.append(f"commit at snapshot: `{sha}`" + (f" — {subject}" if subject else ""))
        entry.append("")
    entry.append("| tunable | before | after |")
    entry.append("|---|---|---|")
    for k, b, a in changes:
        entry.append(f"| `{k}` | `{json.dumps(b)}` | `{json.dumps(a)}` |")
    entry += ["", f"Roll back with: `git checkout {sha or '<sha>'} -- engine/config.py`", "", "---", ""]
    body = "\n".join(entry) + "\n"
    if os.path.exists(CHANGELOG):
        with open(CHANGELOG) as f:
            old = f.read()
        marker = "---\n\n"
        i = old.find(marker)
        new = (old[:i + len(marker)] + body + old[i + len(marker):]) if i >= 0 else old + body
    else:
        new = head + body
    with open(CHANGELOG, "w") as f:
        f.write(new)


def record(reason: str = "engine start") -> int:
    """Snapshot, diff against the last one, and persist any change. Returns changes recorded."""
    try:
        os.makedirs(SNAP_DIR, exist_ok=True)
        now = datetime.now(IST)
        ts = now.strftime("%Y-%m-%d %H:%M:%S %Z")
        cur = snapshot()
        old, old_path = _last_snapshot()
        changes = _diff(old, cur)
        sha = _git("rev-parse", "--short", "HEAD")
        subject = _git("log", "-1", "--format=%s")
        dirty = bool(_git("status", "--porcelain", "--", "engine/config.py"))

        if old_path is None:
            # first run: seed silently, or the whole config would read as one giant "change"
            path = os.path.join(SNAP_DIR, now.strftime("%Y-%m-%dT%H-%M-%S") + ".json")
            with open(path, "w") as f:
                json.dump({"ts": ts, "git_sha": sha, "reason": "initial seed",
                           "config_dirty": dirty, "values": cur}, f, indent=1)
            logger.info("config_ledger: seeded initial snapshot (%d tunables)", len(cur))
            return 0
        if not changes:
            return 0

        path = os.path.join(SNAP_DIR, now.strftime("%Y-%m-%dT%H-%M-%S") + ".json")
        with open(path, "w") as f:
            json.dump({"ts": ts, "git_sha": sha, "reason": reason, "config_dirty": dirty,
                       "changed": [k for k, _, _ in changes], "values": cur}, f, indent=1)
        _write_db(ts, sha, changes)
        _write_changelog(ts, sha + (" (UNCOMMITTED EDITS)" if dirty else ""), subject, changes)
        for k, b, a in changes:
            logger.info("config_ledger: %s  %r -> %r", k, b, a)
        logger.info("config_ledger: %d tunable(s) changed — recorded (%s)", len(changes), reason)
        return len(changes)
    except Exception as e:
        logger.warning("config_ledger: %s", e)
        return 0


def history(limit: int = 20) -> list:
    """Recent rows from the db, newest first."""
    try:
        con = sqlite3.connect(DB_PATH, timeout=10)
        try:
            rows = con.execute("SELECT ts, git_sha, key, before, after FROM config_changes "
                               "ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
        finally:
            con.close()
        return rows
    except Exception:
        return []


if __name__ == "__main__":
    import sys
    if "--rollback-cmd" in sys.argv:
        h = history(1)
        print(f"git checkout {h[0][1].split()[0]} -- engine/config.py" if h else "(no recorded change)")
    elif "--history" in sys.argv:
        for ts, sha, k, b, a in history(40):
            print(f"{ts}  {sha:<12} {k}  {b} -> {a}")
    else:
        print("changes recorded:", record("manual run"))
