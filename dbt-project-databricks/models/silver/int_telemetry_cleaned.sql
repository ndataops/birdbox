{{ config(materialized='table') }}

-- Stays in UTC. The old version applied AT TIME ZONE 'America/Chicago' to a naive UTC value,
-- which shifted readings ~5h and misaligned the weather join (see docs/lessons-learned.md).
SELECT
    recorded_at_utc,
    enclosure_temp_c,
    enclosure_temp_f,
    enclosure_humidity_pct,
    pressure_hpa
FROM {{ ref('stg_telemetry') }}
