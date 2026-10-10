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

## Takeaway
Plausible-looking output isn't validation, experiments belong in a verified copy, and anything scheduled needs a matching cleanup.
