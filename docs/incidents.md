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
