# Incident Log

Detailed write-ups of production bugs found and fixed during a hardening pass on Birdbox. Kept separate from the main README to keep that concise — this is the deeper version, useful for technical interviews or anyone curious about the debugging process itself.

---

## 1. Silent 6-day pipeline outage (dbt under systemd)

**Symptom:** The dashboard's gold-layer tables hadn't updated in six days. Nothing had crashed — Dagster's webserver and daemon both showed `active (running)`, and a basic GraphQL query against the run history returned results. Every surface-level health check passed.

**Investigation:** Checking `dbt-project/target/run_results.json` directly showed its `generated_at` timestamp frozen at the exact moment things went stale — meaning dbt itself hadn't executed since then, not just one model. Pulling the full (untruncated) systemd journal for the Dagster services — rather than trusting the tail of `journalctl`, which had been silently cutting off the real error — surfaced a `pydantic_core.ValidationError`:

```
DbtCliResource
dbt_executable
  Value error, The dbt executable 'dbt' does not exist.
```

**Root cause:** `DbtCliResource` was configured with the bare executable name `dbt`, resolved via `$PATH`. That worked fine in an interactive SSH shell, where the venv was already activated — but systemd services get a minimal, explicit environment that doesn't include that shell's `$PATH` modifications. The dbt resource had been silently failing to initialize since the moment the services were first converted to systemd.

**Fix:** Passed the full absolute path to the venv's `dbt` binary explicitly in the resource config, removing all dependence on `$PATH` resolution.

**Lesson:** A process reporting `active (running)` says nothing about whether its actual work is succeeding. The fix here wasn't really the one-line path change — it was learning to distrust "looks healthy" signals and check the artifact that matters (did the data actually update) before trusting anything else.

---

## 2. Unbounded cron stacking (resource exhaustion)

**Symptom:** The edge device (a Raspberry Pi 4) became completely unresponsive — not slow, not degraded, just gone. No SSH, no ping, nothing.

**Investigation:** After a power cycle, checking `ps aux` on boot showed three separate `rclone copy` processes running concurrently, all started roughly a minute apart, none finished. The crontab had this sync job scheduled `* * * * *` — every single minute — with no lock or overlap protection.

**Root cause:** If any single sync run took longer than 60 seconds (plausible for `.wav` audio files over WiFi), the next minute's cron fired anyway, stacking another instance on top. Three-plus concurrent `rclone` processes fighting for CPU, memory, and network on a resource-constrained Pi 4 is a very plausible explanation for total unresponsiveness — not a random crash, a self-inflicted resource pileup.

**Fix:** Wrapped the cron job in `flock -n`, so a new run skips entirely (rather than queuing or stacking) if a previous run is still holding the lock. A skipped minute is harmless — it catches up next run — but a stacked pile of processes had taken the whole device down.

**Lesson:** `* * * * *` is an easy default to reach for and an easy one to regret. Any cron job whose duration isn't strictly bounded and well under its interval needs explicit overlap protection, especially on constrained hardware.

---

## 3. A pipeline that was never built (not broken — missing)

**Symptom:** Bird detection counts had been frozen for over a week, while the underlying BirdNET-Go database on the edge device was actively updating with fresh detections the whole time.

**Investigation:** Traced the dbt model's source — a local file path on the hub machine — and found it hadn't been touched since a specific date, matching the freeze. Checking the Dagster pipeline code directly, there was no schedule, sensor, or asset referencing bird detections at all. Telemetry had a real scheduled sync asset; bird detections had never gotten the equivalent. The last local copy had been a one-time manual file transfer during initial setup, never automated.

**Fix:** Built a new scheduled asset from scratch, matching the existing medallion pattern: pull the latest detections database from the object storage bucket the edge device already syncs to (rather than direct machine-to-machine `scp`, for a cleaner architectural fit), on a 10-minute schedule.

**Lesson:** Not every stale-data bug is a regression. Sometimes what looks like "this used to work and broke" is actually "this only ever worked once, by hand." Worth checking whether automation genuinely exists before assuming it's just failing.

---

## 4. Plaintext credentials in two separate places

**Symptom:** No functional symptom — found during a deliberate security review, not because anything broke.

**Investigation:** A MinIO access secret was hardcoded in dbt's `profiles.yml`. Fixed that with `env_var()` substitution backed by a single `chmod 600` secrets file. Weeks later, while preparing the project for its first public git commit, the same plaintext secret turned up again — this time in `docker-compose.yml`, the file that actually starts the MinIO container in the first place. A separately-generated debug/context dump file had also captured the plaintext value from before the first fix.

**Fix:** Applied the same `${VAR}`-substitution pattern to the compose file, deleted the stale debug dump, and used the moment of writing the `.gitignore` for the first commit as a forcing function to review every file for embedded secrets before anything went public.

**Lesson:** Fixing a credential leak in the place you noticed it doesn't mean you've found every place it lives. The same secret had propagated to a second config file and a stray log/dump file, neither of which were touched by the first fix. Worth treating "clean up this credential" as "find every place this credential appears," not a single edit.

---

## 5. A hand-maintained lookup table that kept needing hand-maintenance

**Symptom:** Species names occasionally showed up in the dashboard as title-cased Latin binomials (e.g., "Astur Cooperii") instead of real common names (Cooper's Hawk) — readable, but clearly not intended.

**Investigation:** The original design mapped scientific names to common names via a `CASE WHEN` block, later converted to a dbt seed CSV, covering ~80 commonly-seen local species. Every time BirdNET-Go detected something outside that list — a rarer visitor, a recently-reclassified genus (Cooper's Hawk moved from *Accipiter* to *Astur* in recent taxonomic updates) — it fell through to a title-case fallback of the scientific name. The seed worked, but it meant a recurring, low-grade maintenance burden: any new species required a manual PR to a static list.

**Fix:** Replaced the seed as primary lookup with a scheduled asset pulling eBird's full public taxonomy (~17,900 species) via their API, refreshed weekly. The dbt join now checks eBird's taxonomy first, falls back to the original manual seed second, and the title-case fallback last — so even if eBird's API is ever unreachable, existing behavior degrades gracefully rather than breaking.

**Lesson:** A hardcoded lookup table is often the fastest way to ship something, and also the first thing to revisit once the "sometimes wrong" cases start recurring. The real fix wasn't adding more rows — it was noticing the pattern (this keeps happening) and swapping the hand-maintained list for the actual upstream reference data source it was always trying to approximate.


---

## 6. Databricks warehouse stopped and refused to restart (managed compute provisioning)

**Symptom:** A healthchecks.io alert reported Birdbox down. Dagster's `databricks_refresh` asset had exhausted its retries.

**Investigation:** The Dagster traceback ended in `databricks.sql.exc.RequestError: BAD_REQUEST: Cannot create the resource, please try again later`, raised from the connector's `OpenSession` call. That means the connector reached Databricks, but the platform would not provision or attach compute. The warehouse's Monitoring page showed regular query bursts from the refresh job until about midday, then nothing for roughly four hours. The Serverless Starter Warehouse had stopped, and starting it manually brought it back.

**Root cause:** Not confirmed. The likely candidates are a Free Edition compute quota or capacity limit, or an implicit auto-start that failed. The error alone does not distinguish them.

**Fix:** Started the warehouse manually, then materialized `databricks_job` (refresh, Evidence build, README update), which succeeded. Verified the data directly rather than trusting the green run: `MAX(detected_at)` in `gold.fct_bird_detections` was current, and the hourly detection distribution matched local time with no gap during the outage window. Nothing was lost, because the edge device and bucket sync kept running throughout.

**Lesson:** Managed compute can fail to provision, so "it will wake itself up" is an assumption, not a guarantee. The three quick retries all landed inside the same bad window, so retries without backoff only help with failures that clear in seconds.

**Open follow-ups:**
- Lengthen the existing retry policy (currently 1, 2 and 4 min, spent in about 7 minutes) or accept that an outage of hours is handled by the next scheduled run and the Healthchecks alert.
- A trivial warm-up query with a longer timeout before the real refresh, so a cold start fails fast and visibly.
- A freshness alert on the gold tables, so "job succeeded but produced no new data" is also caught.

---

## 7. Telemetry sync failures: a weak uplink hidden behind healthy reachability checks

**Symptom:** `telemetry_job` failed on every run from at least 7:00 PM through the next morning. Each failure lasted 41-42 seconds, and the Discord alert fired each time. The sensor reading step succeeded; the `scp` in `bronze_telemetry_sync` hit its 30-second timeout.

**Investigation:** Reachability looked healthy at every layer. Ping had 0% loss, MTU with the don't-fragment flag passed at 1500 bytes, short SSH commands worked, the Pi had 20 days of uptime, and reading the 1.7 MB file locally took 9 ms. Only sustained transfers failed:
- Pi to hub: `scp` stalled at 0 bytes, and 20 MB of data over SSH never finished. A 5 MB test moved at roughly 140-240 KB/s, with stalls.
- Hub to Pi: 5 MB in about 3 seconds.
- Hub to the internet: 5 MB in 0.6 seconds.

Pausing the Pi's `rclone` sync improved throughput only modestly. The `flock` from incident #2 was holding, with no process pileup. The wifi-sentinel log did not exist, so it had never fired. The Pi is on Wi-Fi only (no Ethernet is possible on the roof), with link quality 45/70 at -65 dBm: usable but mediocre.

**Root cause:** A slow and intermittently stalling Wi-Fi transmit path from the Pi, made visible by a pipeline design that required a synchronous 30-second pull over that path. I did not isolate the exact cause (signal, interference, or power-save behavior), because the wireless tools were not installed on the Pi.

**Fix:** Moved to store-and-forward, the same pattern as bird detections.
- The Pi snapshots `telemetry.db` every 5 minutes using SQLite's backup API (a consistent copy, not the live file) and uploads it to the bucket with `rclone`, which retries on its own. It runs under its own `flock`.
- The hub asset now pulls from the bucket instead of using `scp`. It downloads to a temp file, runs `PRAGMA quick_check`, then replaces the bronze file with `os.replace()`, so a partial download can never corrupt it. It has a retry policy with exponential backoff and fails if the bucket copy is more than 15 minutes old, so a dead Pi cron cannot silently serve stale data.
- Added `ConnectTimeout` and `BatchMode` to the remaining SSH call (`bme280_reading`).
- Fixed `wifi-sentinel.sh`, which ran from a user crontab but needed root, and lacked `/usr/sbin` in cron's PATH (the same class of bug as incident #1). It now runs from root's crontab with an explicit PATH.
- The Pi's detections `rclone` now uses `--max-age 2d`, so each run no longer re-lists every old clip. BirdNET-Go's own `usage` retention policy (80% cap) manages the Pi's disk, so no separate delete cron was added.

**Result:** The snapshot carried the full history, so the bronze table had every 5-minute reading for the last 24 hours (12 per hour, no gaps), including the failure window. The `telemetry_job` run on the new bucket-based sync is green in Dagster.

**Lesson:** Ping and small commands passing does not mean the link carries real data. When a pipeline depends on a pull over a weak link, move to store-and-forward instead of tuning the timeout. A caveat: the bucket is MinIO on the hub, so the Pi's upload still crosses the same Wi-Fi. The gain is that `rclone` retries on the Pi's side and a slow transfer no longer fails the Dagster run.

**Open follow-up:** Bucket retention. MinIO holds every clip since August (27 GB as of Oct 31, with about 41 GB free on the hub), while the Pi prunes its own copies. Add a lifecycle rule that expires old `.wav` clips (for example, older than 90 days) before the disk fills. Leave `.db` files out of the rule, and first confirm nothing downstream reads clips from the bucket.