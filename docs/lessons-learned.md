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

## Takeaway
Plausible-looking output isn't validation. Check joins against raw data at the real-world
timestamp, and check what a sensor physically measures before naming it.


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