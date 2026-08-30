# Birdbox

[![dbt build](https://github.com/ndataops/birdbox/actions/workflows/dbt.yml/badge.svg)](https://github.com/ndataops/birdbox/actions/workflows/dbt.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Last commit](https://img.shields.io/github/last-commit/ndataops/birdbox)

A production-grade bioacoustic monitoring lakehouse running on a two-node home network — built to contribute real detections to eBird and BirdWeather, and to demonstrate end-to-end data engineering: ingestion, orchestration, transformation, and a live analytics dashboard, all running unattended.

**Live demo:** [birdbox.tail69334c.ts.net](https://birdbox.tail69334c.ts.net)
**Repo:** [github.com/ndataops/birdbox](https://github.com/ndataops/birdbox)
**Incident log:** [docs/incidents.md](./docs/incidents.md) - deeper write-ups of the bugs below

![Birdbox dashboard](./docs/birdbox-dashboard.png)

![Birdbox architecture](./docs/birdbox-architecture.svg)

## What it does

A Raspberry Pi in a weatherproof enclosure (`birdedge`) runs [BirdNET-Go](https://github.com/tphakala/birdnet-go) against a shotgun microphone to detect and identify bird species from live audio, alongside a BME280 sensor logging temperature, humidity, and pressure. A Lenovo ThinkCentre (`birdbox`) on the same network pulls that data on a schedule, transforms it through a bronze/silver/gold medallion architecture in DuckDB via dbt, and serves it through a live dashboard — the "Field Journal."

Everything — the sensor syncs, the dbt transforms, the dashboard rebuild, even this README's stats — runs on Dagster schedules with zero manual intervention. The whole stack survives a full reboot with no steps beyond powering the machines back on.

## Stack

- **Ingestion:** BirdNET-Go, BME280 (I2C), MinIO (S3-compatible object storage)
- **Transformation:** dbt-duckdb, DuckDB, 23 passing data tests including an automated freshness check
- **Orchestration:** Dagster (asset-based scheduling, 5–15 min cadences)
- **Dashboard:** Evidence.dev, static production build
- **Infra:** systemd (all services survive reboot), Tailscale Funnel (public HTTPS demo link), GitHub Actions CI
- **Languages:** Python, SQL (DuckDB dialect)

<!-- STATS:START -->
## Live stats

- **Detections:** 2,788
- **Species identified:** 76
- **Latest detection:** 2026-08-29 19:06 UTC
- **Telemetry readings:** 1,569
- **Last updated:** 2026-08-30 05:15 UTC (auto-generated on every dbt run)
<!-- STATS:END -->

## Architecture

**Medallion layers**, all in DuckDB:
- **Bronze** — raw synced snapshots from birdedge (BirdNET-Go's SQLite output via MinIO, BME280 readings via direct pull)
- **Silver** — cleaned, deduplicated, typed (`int_bird_detections_cleaned`, `int_telemetry_cleaned`)
- **Gold** — analytics-ready facts (`fct_bird_detections`, `fct_detections_with_weather` — a nearest-15-minute join between detections and microclimate readings)

**Orchestration**, all Dagster-scheduled assets:
- `bronze_telemetry_sync` — every 5 minutes
- `bronze_birdnet_sync` — every 10 minutes, pulling from MinIO
- `birdbox_dbt_assets` + `evidence_build` + `update_readme` — every 15 minutes: full dbt build, dashboard rebuild, and this README's stats, all in one chain

## Incidents found and fixed

This system had several real, previously-undiagnosed production bugs — not staged for the portfolio, found while doing an actual hardening pass:

- **Unbounded cron stacking.** A `* * * * *` rclone sync had no lock protection; overlapping runs piled up and exhausted memory/CPU on the Pi, taking it offline. Fixed with `flock`-guarded cron.
- **Silent 6-day pipeline outage.** After moving Dagster to systemd, `dbt` resolved by bare name on `$PATH` — which worked in an interactive shell but not under systemd's minimal environment. The entire dbt layer silently stopped running; nobody noticed until a downstream chart came up empty. Fixed with an explicit executable path.
- **A pipeline that never existed.** Bird detection sync from birdedge to the lakehouse had no automation at all — a one-time manual copy from early setup, never turned into a scheduled asset. Built a proper `bronze_birdnet_sync` asset pulling from MinIO, matching the existing medallion pattern.
- **Plaintext credentials in two places.** A MinIO secret was hardcoded in both `profiles.yml` and `docker-compose.yml`. Replaced with `env_var()`/`${VAR}` substitution backed by a single `chmod 600` secrets file — zero plaintext credentials anywhere in the codebase or git history.

## Roadmap

- Port to Databricks as the primary showcase (in progress toward certification)
- Data contracts and lineage on the gold layer
- Natural-language query layer over the lakehouse
- Reusable "lakehouse spine" for sibling projects (air quality, transit, pollinators)

## Running it locally

```bash
git clone https://github.com/ndataops/birdbox.git
cd birdbox

# dbt
cd dbt-project && dbt build

# Dagster
cd ../birdbox_pipeline && dagster dev

# Dashboard
cd ../field-journal && npm install && npm run sources && npm run build && npm run preview
```

Requires exported `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` for the MinIO-backed assets.
