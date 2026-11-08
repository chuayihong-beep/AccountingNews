"""Run the three scheduled jobs on an ordinary PC, with no GitHub involved.

It does exactly what the GitHub workflows did, on the same schedule (Malaysia time):
    collect  every day 05:37   python -m collector              (news, Google News, email, page watch)
    brief    every day 12:03   python -m collector.brief --days 1
    send     every 10 min      python -m collector.send_brief   (emails approved briefs)

Keep it running (see local-runner/README.md):
    python -m collector.local_runner                 run forever
    python -m collector.local_runner --check         check the keys and software, then stop
    python -m collector.local_runner --once collect  run one job right now, then stop
    python -m collector.local_runner --once brief --extra "--from 2026-10-02 --to 2026-10-05"
    python -m collector.local_runner --status        when each job last ran

Keys live in local-runner/.env (never in the code). If the PC was off at a job's time, the job runs as soon as the
PC is back, once for that day.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import shlex
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent          # .../pao-news-monitor (where `python -m collector` runs)
RUNNER_DIR = APP_DIR / "local-runner"
DEFAULT_ENV = RUNNER_DIR / ".env"
STATE_FILE = RUNNER_DIR / "state.json"
LOG_DIR = RUNNER_DIR / "logs"
MALAYSIA = timezone(timedelta(hours=8))                    # no daylight saving, so a fixed offset is exact
log = logging.getLogger("runner")


@dataclass(frozen=True)
class Job:
    name: str
    args: tuple
    timeout: int                    # seconds; same limits as the GitHub workflows
    at: tuple | None = None         # (hour, minute) every day, Malaysia time
    every: int | None = None        # or: every N seconds
    needs: tuple = ("SUPABASE_URL", "SUPABASE_SERVICE_KEY")
    wants: tuple = field(default_factory=tuple)   # useful but optional keys; a warning when missing


JOBS = {
    "collect": Job("collect", ("-m", "collector"), 45 * 60, at=(5, 37),
                   wants=("GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "CF_AI_TOKEN")),
    "brief": Job("brief", ("-m", "collector.brief", "--days", "1"), 30 * 60, at=(12, 3),
                 wants=("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "CF_AI_TOKEN")),
    "send": Job("send", ("-m", "collector.send_brief"), 10 * 60, every=10 * 60,
                needs=("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "GMAIL_ADDRESS", "GMAIL_APP_PASSWORD")),
}


# ---------------------------------------------------------------- settings
def read_env_file(path: Path) -> dict:
    """KEY=value lines; blank lines and # comments ignored; matching quotes around a value are removed."""
    out = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key.strip().removeprefix("export ").strip()] = value
    return out


def problems(env: dict) -> tuple[list, list]:
    """(missing required keys per job, missing optional keys). Names only - never values."""
    errors, warnings = [], []
    ai = ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "CF_AI_TOKEN")
    for job in JOBS.values():
        missing = [k for k in job.needs if not env.get(k)]
        if missing:
            errors.append(f"{job.name}: missing {', '.join(missing)}")
    if not any(env.get(k) for k in ai):
        warnings.append("no AI key set (GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY or CF_AI_TOKEN): relevance suggestions and briefs will be skipped")
    if env.get("CF_AI_TOKEN") and not env.get("CF_ACCOUNT_ID"):
        warnings.append("CF_AI_TOKEN is set but CF_ACCOUNT_ID is not")
    if not (env.get("GMAIL_ADDRESS") and env.get("GMAIL_APP_PASSWORD")):
        warnings.append("no Gmail login: the email inbox is not read and briefs cannot be sent")
    return errors, warnings


# ---------------------------------------------------------------- schedule
def is_due(job: Job, now: datetime, last: datetime | None) -> bool:
    """Daily jobs run once per day once their time has passed (so a missed slot is caught up); others by interval."""
    if job.every:
        return last is None or (now - last).total_seconds() >= job.every
    slot = now.replace(hour=job.at[0], minute=job.at[1], second=0, microsecond=0)
    return now >= slot and (last is None or last < slot)


def load_state(path: Path = STATE_FILE) -> dict:
    try:
        return {k: datetime.fromisoformat(v) for k, v in json.loads(path.read_text()).items()}
    except (OSError, ValueError):
        return {}


def save_state(state: dict, path: Path = STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({k: v.isoformat() for k, v in state.items()}, indent=1))


# ---------------------------------------------------------------- running a job
def run_job(job: Job, env: dict, extra: tuple = ()) -> int:
    """Run one job like the workflow step did. Output goes to local-runner/logs/<job>.log (replaced each run)."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, *job.args, *extra]
    started = time.monotonic()
    with open(LOG_DIR / f"{job.name}.log", "w", encoding="utf-8") as out:
        out.write(f"# {datetime.now(MALAYSIA):%Y-%m-%d %H:%M:%S} Malaysia time: {' '.join(job.args + tuple(extra))}\n")
        out.flush()
        try:
            code = subprocess.run(cmd, cwd=APP_DIR, env={**os.environ, **env, "PYTHONUTF8": "1"}, stdout=out,
                                  stderr=subprocess.STDOUT, timeout=job.timeout).returncode
        except subprocess.TimeoutExpired:
            out.write(f"\n# stopped: took longer than {job.timeout // 60} minutes\n")
            code = 124
    log.info("%s finished with exit code %s in %.0fs (log: local-runner/logs/%s.log)", job.name, code, time.monotonic() - started, job.name)
    return code


class Runner:
    def __init__(self, env: dict, run=run_job, clock=lambda: datetime.now(MALAYSIA), state_path: Path = STATE_FILE):
        self.env, self.run, self.clock, self.state_path = env, run, clock, state_path
        self.state = load_state(state_path)
        self.running: set[str] = set()
        self.lock = threading.Lock()

    def tick(self, wait: bool = False) -> list[str]:
        """Start every job that is due and not already running. Returns the names started."""
        now, started, threads = self.clock(), [], []
        with self.lock:
            for job in JOBS.values():
                if job.name in self.running or not is_due(job, now, self.state.get(job.name)):
                    continue
                if any(not self.env.get(k) for k in job.needs):
                    continue                      # reported once at start-up; don't retry every 30 seconds
                self.running.add(job.name)
                self.state[job.name] = now        # mark first: a crash must not make it re-run in a tight loop
                save_state(self.state, self.state_path)
                t = threading.Thread(target=self._go, args=(job,), daemon=True)
                threads.append(t)
                started.append(job.name)
                t.start()
        if wait:
            for t in threads:
                t.join()
        return started

    def _go(self, job: Job) -> None:
        try:
            self.run(job, self.env)
        except Exception:                          # noqa: BLE001 - one bad job must never stop the runner
            log.exception("%s crashed", job.name)
        finally:
            with self.lock:
                self.running.discard(job.name)

    def forever(self, sleep=time.sleep, stop: threading.Event | None = None, every: int = 30) -> None:
        while not (stop and stop.is_set()):
            self.tick()
            sleep(every)


# ---------------------------------------------------------------- command line
def cli(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env-file", default=str(DEFAULT_ENV), help="where the keys are (default: local-runner/.env)")
    ap.add_argument("--check", action="store_true", help="check keys and software, then stop")
    ap.add_argument("--status", action="store_true", help="show when each job last ran")
    ap.add_argument("--once", choices=sorted(JOBS), help="run one job now, then stop")
    ap.add_argument("--extra", default="", help='extra options for --once, e.g. "--only icai"')
    a = ap.parse_args(argv)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
                        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_DIR / "runner.log", encoding="utf-8")])

    if a.status:
        state = load_state()
        for job in JOBS.values():
            print(f"{job.name:8} last started: {state[job.name]:%Y-%m-%d %H:%M} Malaysia time" if job.name in state else f"{job.name:8} never run here")
        return 0

    env = read_env_file(Path(a.env_file))
    if not Path(a.env_file).exists():
        print(f"No keys file at {a.env_file}. Copy local-runner/.env.example to local-runner/.env and fill it in.")
        return 2
    errors, warnings = problems(env)
    for w in warnings:
        log.warning("Note: %s", w)
    for e in errors:
        log.error("Cannot run - %s", e)

    if a.check:
        try:
            import playwright  # noqa: F401
            log.info("Python packages: ok")
        except ImportError:
            errors.append("Python packages missing (run setup.bat)")
            log.error("Python packages missing (run setup.bat)")
        log.info("Check %s", "FAILED" if errors else "passed")
        return 1 if errors else 0

    if a.once:
        job = JOBS[a.once]
        if any(not env.get(k) for k in job.needs):
            return 2
        return run_job(job, env, tuple(shlex.split(a.extra)))

    log.info("Runner started. collect 05:37, brief 12:03, send every 10 min (Malaysia time). Leave this window open.")
    try:
        Runner(env).forever()
    except KeyboardInterrupt:
        log.info("Stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(cli())
