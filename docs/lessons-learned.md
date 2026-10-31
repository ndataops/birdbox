# Lessons learned

## 1. A double timezone conversion silently misaligned the weather join

**Symptom:** none visible. Dashboard numbers looked plausible.

**Cause:** `int_telemetry_cleaned` applied `AT TIME ZONE 'America/Chicago'` to a naive UTC
timestamp. DuckDB reads a naive value as already being local, so telemetry shifted ~5 hours
later. Gold `detected_at` is naive Chicago time, so each detection was paired with a sensor
reading from ~10 hours earlier (a 12:48 PM detection got a 2:45 AM temperature).

**How it was found:** while porting to Databricks, compared the assigned weather against
raw `telemetry.db` readings at the true time and at the suspected shifted time.

**Fix / rule:** source timestamps are UTC (`detected_at` is a Unix epoch, `recorded_at` is
ISO +00:00). Keep bronze and silver in UTC and convert to Chicago time only in gold.

## 2. The sensor measures enclosure temperature, not ambient weather

**Finding:** once the join was corrected, midday October readings were ~102-106 F. The
BME280 sits in a sealed rooftop enclosure beside a Raspberry Pi (solar gain plus heat).

**Decision:** the sensor can't be moved in its current design, so the data is relabeled as
enclosure-internal temperature and humidity. The dashboard framing is updated to match.
Pressure is barely affected by the enclosure and is unchanged.

## 3. Experiment files landed in the live project (a failed `cd` that didn't stop the script)

**What happened:** a command block started with `cd` into a directory that didn't exist yet
(the copy step had been skipped), then wrote ~20 files. The `cd` failed, the rest ran anyway,
and the Databricks port ended up inside the live DuckDB project. One long heredoc pasted into
the terminal was also mangled.

**Recovery:** the project was in git, so `git status` showed exactly what changed. A lean copy
(`git ls-files -co --exclude-standard | rsync --files-from=-`) saved the work, then
`git stash push -u` restored the live project. `dbt parse` and row counts confirmed no data
was lost.

**Rules:**
- Chain dependent commands with `&&`, and check `pwd` before writing files.
- Experiment in a verified copy or branch, and commit first.
- Write multi-line files in an editor, not by pasting heredocs into a terminal.
- Check folder size with `du` before `cp -a`.

**Side finding:** `dbt-project/target/` had grown to ~8.3 GB of per-run folders, the same
accumulation pattern as the Evidence `build/` leak. It needs periodic cleanup.


## 4. Anything that writes files on a schedule needs a matching cleanup

**Pattern:** three separate leaks, all the same shape: a scheduled job writes new hash-named
output on every run and nothing ever deletes the old output.
- Evidence `build/` grew to 47 GB and filled the disk (dashboard stale for a week, Oct 2026).
- dbt `target/birdbox_dbt_assets-<hash>` folders reached 8.3 GB (~3,500 folders).
- Evidence `build/` was back to 12 GB four days after the manual cleanup.

**Fix for dbt:** a nightly cron job that deletes run folders older than 24 hours. The age margin
means it can never touch an in-flight run, and `manifest.json` (which Dagster reads) is left alone.

**Fix for Evidence:** a build/site split. Scratch `build/` is wiped on every run, and `site/` (what the
web server serves) is only updated via `rsync --delete` after a successful build. A failed build
leaves the last good dashboard serving, and disk use stays flat (~120 MB each instead of growing ~3 GB/day).

**Rule:** when you add a scheduled job, add its cleanup in the same change, and add a
disk-usage alert so a leak shows up as a warning instead of an outage.


## 5. A WHERE clause silently bound to the source column, not the same-named alias

**What happened:** `fct_bird_detections` selected `detected_at AT TIME ZONE 'America/Chicago' AS detected_at`,
then filtered `WHERE detected_at::DATE NOT IN ('2026-08-16', '2026-08-17')`. In DuckDB the `WHERE` resolved to
the *source* UTC column, so the filter excluded UTC dates while its comment described Chicago dates. Seven
evening detections from 8/17 (local time) were kept that the comment suggests should have been excluded.

**How it was found:** a row-count and checksum parity check of the Databricks port against the DuckDB
gold tables (11,038 vs 11,045 rows), then tracing the 7-row difference back to the date filter.

**Resolution:** the port deliberately reproduces the legacy behavior (filtering on UTC date), and a comment in
the model says so. With that change the Databricks gold matches DuckDB exactly: 11,045 rows, identical id and
confidence checksums. The only intended difference is the corrected weather join.

**Rule:** don't reuse a source column name as an alias in the same SELECT, because alias resolution in WHERE
differs between engines. Port first with identical behavior, prove parity with checksums, and make behavior
changes in a separate, documented commit.


## 6. Tools match patterns anywhere in a tree, and empty results can break a pipeline

**rsync `--exclude build`** matched every folder named `build` at any depth, including
`node_modules/@google-cloud/bigquery/build/`, which broke Evidence's plugin loading in the scratch copy.
Anchor patterns with a leading slash (`--exclude /build`) when you mean only the top level.
`.gitignore` matches the same way.

**Empty tables:** Evidence's Databricks connector writes a zero-byte file when a query returns no rows,
and the static build then fails loading it. A table that can legitimately be empty (here, new-species
alerts on a quiet day) needs a typed placeholder row in the source query, plus a filter on the pages
(`WHERE detection_id > 0`).

**Workflow:** build in a scratch copy, confirm the build succeeded, and only then serve it. A 404 from a
preview server usually means the build folder is missing, not a network problem.


## 7. Green checks don't prove a change works

**README stats:** the auto-updating block labeled `detected_at` as UTC when gold stores Chicago time,
and printed a "Last updated" time about 5 hours in the future, because it read the telemetry column
that the timezone bug (lesson 1) had shifted. It sat on the public README unnoticed. Rebuilding the
script against the corrected Databricks tables fixed both, and a `--dry-run` mode let the new output be
compared with the old before anything was pushed.

**Backups:** the new backup asset passed `py_compile` and `ruff` yet still had two flaws that only a real
run exposed. A missing `import sqlite3` compiles fine (names resolve at runtime, so use
`ruff check --select F821`). And SQLite databases in WAL mode produce `-wal` and `-shm` sidecar files,
which tripled the file count per backup and would have cut the 7-day retention to about 2 days.
A restore test (open the newest backup, compare its row count to the source) is the real check.

**Reading terminals:** long lines wrap in the terminal and copying them drops the space at the wrap
(`notf`, `theeBird`, `needsa`). Before "fixing" a typo seen in terminal output, check the file with
`grep -c`.

**Rules:**
- Syntax checks prove syntax. Run the thing, then verify its output against the source.
- Test retention and cleanup logic against the files the tool really produces.
- Before editing a suspected typo, confirm with `grep`, not by eye.

## 8. Power loss → 8 silent days offline (+ Databricks capacity error on recovery)
**Impact:** birdbox (ThinkCentre M720q) was powered off from Sun Oct 11, 8:08 AM CDT,
until Mon Oct 19, ~9:49 AM CDT. No hourly Databricks refresh, README stats commits,
or backups ran for 8 days, and the public dashboard was frozen at Oct 11.
**No data was lost:** birdedge (Pi) kept detecting and buffering, and the backlog
flowed through once birdbox was back.

### What happened
- The journal for the previous boot ends mid-stream at 13:08 UTC Oct 11, during the
  `databricks_refresh` step of a scheduled run, with no shutdown sequence. That
  pattern indicates power was cut, not a crash or clean shutdown.
- The M720q's BIOS default for **After Power Loss** is to stay off, so the box never
  came back on its own.
- Nothing alerted. The Discord failure sensor runs *on birdbox*, so when birdbox is
  off, there are no failures to report. The outage was found by noticing the
  dashboard was down. Tailscale showed birdbox "last seen 8d ago."

### Recovery
- Powered on; all systemd services and Dagster schedules resumed with no intervention.
- The run interrupted by the power cut was stuck in "Started" (193h). A normal
  terminate hangs waiting on a process that no longer exists; force termination clears it.
- The first two `databricks_refresh` runs failed with
  `BAD_REQUEST: Cannot create the resource, please try again later` when opening a
  session. `databricks warehouses start` from the CLI failed the same way. Starting the
  warehouse from the UI a few minutes later succeeded. Diagnosis: transient serverless
  capacity on Databricks' side. Free Edition makes no capacity guarantees.
- After a manual `databricks_job` run, the dashboard was current again (12,632 detections).
**Verified end to end (Oct 19):** after a deliberate reboot, all services came back on their own, the next scheduled `databricks_job` succeeded with no intervention, and its Healthchecks.io ping turned the check green.

### What changed
| Gap | Fix |
|---|---|
| Box stays off after a power blip | BIOS: Power → After Power Loss → **Power On**. Verified with a reboot: all services active within a minute. |
| Transient Databricks errors cost a full hour | `RetryPolicy(max_retries=3, delay=60, backoff=EXPONENTIAL)` on `databricks_refresh` (retries at 1, 2, and 4 min) |
| No alert when the box itself goes down | **Dead-man's switch:** the end of `update_readme` (the last step of `databricks_job`) pings Healthchecks.io. Period 1h, grace 1h; alerts go to Discord and email. Silence now alerts within ~2h. The ping URL lives in `/etc/birdbox-secrets.env`, and a failed ping only logs a warning. |

### Also checked: birdedge disk
- The Pi was at 83% of 29G, with 17G in BirdNET-Go audio clips. BirdNET-Go's retention is
  `policy: usage, maxusage: 80%`, so it prunes clips itself and holds steady around 80%.
- The systemd journal (1.2G) was **not** managed. It's now capped at 200M through
  `/etc/systemd/journald.conf.d/size.conf`.

### Lessons
- **Alerting can't live only on the thing it monitors.** In-process failure alerts
  catch broken jobs, not a dead host. An external heartbeat catches both.
- **Read the end of the previous boot's journal first** (`journalctl -b -1 -e`). A log
  that stops mid-stream points to power loss, and that one check settled the root cause.
- **Check firmware defaults on always-on hardware.** Mini PCs ship configured as desktops.
- **Free-tier cloud compute is best-effort.** Design for retries, and know where you
  can see the platform's own error (the warehouse UI was clearer than the connector).
- Small gotchas: `ssh birdbox` points at the LAN IP, so it fails off-network.
  `journalctl --vacuum-*` only removes *archived* files. Pasting into VS Code can
  double-indent the first line, so always run `py_compile` after an edit.
  - **A failing check nobody sees isn't monitoring.** After the Databricks cutover, master's
  lint was red for about a week; it only surfaced when PR #1 ran CI. GitHub failed-workflow
  email notifications are now on, and the Actions tab is part of the weekly review.

### Follow-ups
- [X] Investigate intermittent `telemetry_job` failures (Oct 19, 9:50 and 10:45 AM);
      consider the same retry policy if they're transient. (likely the same Wi-Fi uplink problem, see lesson 10)
- [X] Cap the journal on birdbox too
- [ ] Decide on a fallback if Databricks Free Edition is unavailable for an extended period

## 9. A retry budget has to outlast the outage it's meant to ride out

**What happened (Oct 30):** the Databricks Serverless warehouse stopped around midday and
`databricks_refresh` failed with the same `BAD_REQUEST: Cannot create the resource` seen on
Oct 19. The retry policy added after that incident (retries at 1, 2 and 4 min) was spent in
about 7 minutes, but the warehouse stayed down for roughly four hours, until it was started by
hand in the UI. The cause is unconfirmed (Free Edition quota or capacity, or a failed
auto-start).

**What worked:** the Healthchecks.io dead-man's switch from lesson 8 fired and caught it. No
data was lost. `MAX(detected_at)` in gold was current, and the hourly detection counts had no
hole, because the Pi and the bucket sync kept running.

**Rules:**
- Retries cover blips that clear in seconds to minutes. For an outage of hours, rely on the
  next scheduled run plus an alert.
- Add a cheap warm-up (`SELECT 1` with a longer timeout) so a cold start fails fast and visibly.
- Alert on freshness of the output table, not only on job success.
- Next time, check the Free Edition usage page before pressing Start, to tell quota from capacity.

## 10. Reachability isn't throughput: a weak link needs store-and-forward

**What happened:** `telemetry_job` failed every run from 7 PM Oct 30 into the next morning.
The `scp` in `bronze_telemetry_sync` hit its 30 s timeout each time. Ping had 0% loss, a
1500-byte don't-fragment ping passed, SSH worked, the Pi had 20 days of uptime, and reading the
file locally took 9 ms. Only sustained Pi-to-hub transfers stalled (~140-240 KB/s, sometimes
zero), while hub-to-Pi and hub-to-internet transfers were fast. The Pi is on Wi-Fi with no
Ethernet option on the roof. Pausing `rclone` helped only modestly.

**Fix:** the Pi now snapshots `telemetry.db` every 5 min with SQLite's backup API and uploads it
to the bucket (`rclone` retries on its own). The hub pulls from the bucket, downloads to a temp
file, runs `PRAGMA quick_check`, swaps it in with `os.replace()`, fails if the copy is over
15 min old, and retries with backoff. Verified: 12 readings per hour for 24 h with no gaps,
and the Dagster run is green.

**Rules:**
- Ping and small commands passing says nothing about bulk throughput. Test a real transfer in
  each direction.
- Rule out one layer at a time (ping, MTU, SSH, disk read, each direction, internet) instead of
  guessing.
- Don't


## Takeaway

- **Plausible output isn't validation.** Check joins against raw data at the real timestamp, and check what a sensor physically measures before naming it (lessons 1, 2).
- **Experiment in a verified copy, and prove parity before changing behavior.** Chain dependent commands with `&&`, commit first, and port with identical behavior before making deliberate changes (lessons 3, 5).
- **Anything scheduled needs a matching cleanup.** Every job that writes files on a schedule needs its cleanup in the same change, plus a disk alert (lesson 4).
- **Patterns match more than you mean.** Anchor excludes, and give tables that can be empty a typed placeholder (lesson 6).
- **Green checks prove syntax, not behavior.** Run the thing, then verify its output against the source, for example with a restore test (lesson 7).
- **Monitoring can't live only inside what it monitors.** In-process alerts catch failing jobs, not a dead host; an external heartbeat catches both. Pair it with self-healing defaults: firmware that powers back on, and retries for transient cloud errors (lesson 8).
- **A retry budget must outlast the outage.** Retries cover blips, not hours-long capacity failures; pair them with a warm-up step and a freshness alert (lesson 9).
- **Reachable isn't fast.** Ping and small commands can pass while bulk transfers stall; test real throughput, and move weak links off the critical path with store-and-forward (lesson 10).