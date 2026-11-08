"""The no-GitHub scheduler: settings file, schedule rules, no double starts, command line."""
import threading
from datetime import datetime, timedelta, timezone

from collector import local_runner as lr

MY = timezone(timedelta(hours=8))


def at(h, m=0, day=8):
    return datetime(2026, 11, day, h, m, tzinfo=MY)


# ---- settings file
def test_env_file_parses_quotes_comments_and_bom(tmp_path):
    f = tmp_path / ".env"
    f.write_text('﻿# comment\nA=1\n\nB = "two words"\nexport C=\'x\'\nD=a=b\nnonsense\n', encoding="utf-8")
    assert lr.read_env_file(f) == {"A": "1", "B": "two words", "C": "x", "D": "a=b"}


def test_env_file_missing_is_empty(tmp_path):
    assert lr.read_env_file(tmp_path / "nope") == {}


def test_problems_names_missing_keys_but_never_values():
    errors, warnings = lr.problems({"SUPABASE_URL": "u", "SUPABASE_SERVICE_KEY": "SECRET"})
    assert any("send: missing GMAIL_ADDRESS" in e for e in errors)
    assert not any("SECRET" in x for x in errors + warnings)
    assert any("no AI key" in w for w in warnings)


def test_complete_settings_have_no_problems():
    env = {k: "x" for k in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "GEMINI_API_KEY")}
    assert lr.problems(env) == ([], [])


# ---- schedule
def test_daily_job_waits_for_its_time_then_runs_once():
    job = lr.JOBS["brief"]                                        # 12:03
    assert not lr.is_due(job, at(12, 2), None)
    assert lr.is_due(job, at(12, 3), None)
    assert not lr.is_due(job, at(15), at(12, 4))                  # already ran today
    assert lr.is_due(job, at(12, 3, day=9), at(12, 4, day=8))     # next day


def test_daily_job_catches_up_after_the_pc_was_off():
    job = lr.JOBS["collect"]                                      # 05:37
    assert lr.is_due(job, at(9), at(5, 40, day=7))                # PC was off at 05:37, back at 09:00


def test_morning_start_does_not_run_yesterdays_missed_slot_twice():
    job = lr.JOBS["collect"]
    assert not lr.is_due(job, at(4), at(5, 40, day=7))            # before today's slot: wait


def test_interval_job():
    job = lr.JOBS["send"]
    assert lr.is_due(job, at(10), None)
    assert not lr.is_due(job, at(10, 9), at(10, 0))
    assert lr.is_due(job, at(10, 10), at(10, 0))


def test_state_round_trip(tmp_path):
    f = tmp_path / "s" / "state.json"
    lr.save_state({"collect": at(5, 37)}, f)
    assert lr.load_state(f) == {"collect": at(5, 37)}
    assert lr.load_state(tmp_path / "missing.json") == {}
    f.write_text("{broken")
    assert lr.load_state(f) == {}


# ---- runner
FULL = {k: "x" for k in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "GMAIL_ADDRESS", "GMAIL_APP_PASSWORD")}


def make(tmp_path, now, run, env=FULL):
    return lr.Runner(env, run=run, clock=lambda: now[0], state_path=tmp_path / "state.json")


def test_tick_starts_due_jobs_once(tmp_path):
    ran, now = [], [at(12, 5)]
    r = make(tmp_path, now, lambda job, env: ran.append(job.name))
    assert sorted(r.tick(wait=True)) == ["brief", "collect", "send"]
    assert r.tick(wait=True) == []                       # nothing is due a second later
    now[0] = at(12, 16)
    assert r.tick(wait=True) == ["send"]
    assert sorted(ran) == ["brief", "collect", "send", "send"]


def test_a_running_job_is_not_started_twice(tmp_path):
    gate, started = threading.Event(), []
    now = [at(12, 5)]

    def slow(job, env):
        started.append(job.name)
        gate.wait(5)

    r = make(tmp_path, now, slow)
    r.tick()
    now[0] = at(12, 30)                                   # send is due again while the first send still runs
    assert "send" not in r.tick()
    gate.set()
    for _ in range(100):
        if not r.running:
            break
        threading.Event().wait(0.02)
    assert started.count("send") == 1


def test_a_crashing_job_does_not_stop_the_runner_or_loop_tightly(tmp_path):
    now = [at(12, 5)]

    def boom(job, env):
        raise RuntimeError("x")

    r = make(tmp_path, now, boom)
    r.tick(wait=True)
    assert r.running == set()
    assert r.tick(wait=True) == []                        # marked as started, so no retry every 30 seconds


def test_jobs_missing_their_keys_are_skipped(tmp_path):
    ran = []
    r = make(tmp_path, [at(12, 5)], lambda job, env: ran.append(job.name), env={"SUPABASE_URL": "u", "SUPABASE_SERVICE_KEY": "k"})
    r.tick(wait=True)
    assert sorted(ran) == ["brief", "collect"]            # send needs Gmail


def test_state_survives_restart(tmp_path):
    ran, now = [], [at(12, 5)]
    make(tmp_path, now, lambda j, e: ran.append(j.name)).tick(wait=True)
    ran.clear()
    make(tmp_path, now, lambda j, e: ran.append(j.name)).tick(wait=True)    # "restart" the same minute
    assert ran == []


# ---- running a real command
def test_run_job_uses_app_folder_and_env_and_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(lr, "LOG_DIR", tmp_path)
    job = lr.Job("probe", ("-c", "import os;print(os.getcwd());print(os.environ['PAO_TEST'])"), 30, every=60)
    assert lr.run_job(job, {"PAO_TEST": "hello"}) == 0
    out = (tmp_path / "probe.log").read_text()
    assert str(lr.APP_DIR) in out and "hello" in out


def test_run_job_reports_failure_and_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(lr, "LOG_DIR", tmp_path)
    assert lr.run_job(lr.Job("bad", ("-c", "raise SystemExit(3)"), 30, every=60), {}) == 3
    assert lr.run_job(lr.Job("slow", ("-c", "import time;time.sleep(5)"), 1, every=60), {}) == 124
    assert "longer than" in (tmp_path / "slow.log").read_text()


def test_commands_match_the_github_workflows():
    assert lr.JOBS["collect"].args == ("-m", "collector")
    assert lr.JOBS["brief"].args == ("-m", "collector.brief", "--days", "1")
    assert lr.JOBS["send"].args == ("-m", "collector.send_brief")
    assert (lr.JOBS["collect"].at, lr.JOBS["brief"].at, lr.JOBS["send"].every) == ((5, 37), (12, 3), 600)


# ---- command line
def test_cli_without_env_file_explains(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(lr, "LOG_DIR", tmp_path)
    assert lr.cli(["--env-file", str(tmp_path / "none"), "--check"]) == 2
    assert ".env.example" in capsys.readouterr().out


def test_cli_check_passes_and_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(lr, "LOG_DIR", tmp_path)
    f = tmp_path / ".env"
    f.write_text("SUPABASE_URL=u\n")
    assert lr.cli(["--env-file", str(f), "--check"]) == 1
    f.write_text("\n".join(f"{k}=x" for k in FULL) + "\nGEMINI_API_KEY=x\n")
    assert lr.cli(["--env-file", str(f), "--check"]) == 0


def test_cli_once_passes_extra_options(tmp_path, monkeypatch):
    monkeypatch.setattr(lr, "LOG_DIR", tmp_path)
    f = tmp_path / ".env"
    f.write_text("\n".join(f"{k}=x" for k in FULL))
    seen = {}
    monkeypatch.setattr(lr, "run_job", lambda job, env, extra=(): seen.update(job=job.name, extra=extra) or 0)
    assert lr.cli(["--env-file", str(f), "--once", "brief", "--extra", "--from 2026-10-02 --to 2026-10-05"]) == 0
    assert seen == {"job": "brief", "extra": ("--from", "2026-10-02", "--to", "2026-10-05")}
