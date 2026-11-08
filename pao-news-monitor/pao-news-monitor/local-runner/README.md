# Running the monitor on a CAPA PC (no GitHub)

The PC does what GitHub Actions did, at the same times (Malaysia time):

| Job | When | What |
|---|---|---|
| collect | every day 05:37 | news, Google News, email inbox, page watch |
| brief | every day 12:03 | drafts the daily brief for review |
| send | every 10 minutes | emails briefs that were approved on the site |

If the PC was off or asleep at a job's time, the job runs when the PC is back (once for that day).
The website, Supabase and Cloudflare are unchanged - only the "who runs the jobs" part moves.

## One-time setup (Windows)
1. Install **Python 3.12** from python.org. In the installer tick **Add python.exe to PATH**.
2. Copy the whole `pao-news-monitor` folder to the PC (for example `C:\pao-news-monitor`).
3. Double-click `local-runner\setup.bat`. It installs the packages and opens `.env` in Notepad.
4. Fill in `.env` with **new** keys (see `.env.example`). Save. The setup ends with "Check passed".
5. Double-click `local-runner\run.bat` and leave the window open (minimise it).

## Keep it running
- **Start with Windows:** press Win+R, type `shell:startup`, and put a shortcut to `run.bat` there.
- **Never sleep:** Settings > System > Power > Screen and sleep > set "When plugged in, put my device to sleep" to **Never** (the screen may still turn off).
- Use a PC that is normally on at 05:37 and 12:03 on workdays.

## Everyday use
- `run-now.bat collect` / `brief` / `send` runs a job straight away.
- A brief for specific dates: `python -m collector.local_runner --once brief --extra "--from 2026-10-02 --to 2026-10-05"` (run inside the app folder with the venv active).
- `python -m collector.local_runner --status` shows when each job last ran.
- Output of the latest run of each job is in `local-runner\logs\collect.log`, `brief.log`, `send.log`.

## Notes
- Keys stay in `local-runner\.env` on that PC only. Do not email or upload it.
- The **Update news** and **Create brief** buttons on the website still ask GitHub, so they will not work from the site while GitHub is unavailable. Use `run-now.bat` instead (or ask for the "without GitHub" version of those buttons).
- Do not run this and the GitHub workflows at the same time: they would both collect. Duplicates are ignored, but emails could be sent twice.
