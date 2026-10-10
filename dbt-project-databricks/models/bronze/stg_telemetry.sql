{{ config(materialized='view') }}

-- recorded_at is an ISO string with +00:00 (UTC). Kept as naive UTC.
-- NOTE: the sensor sits inside a sealed enclosure, so these are enclosure-internal readings, not ambient weather.
SELECT
    CAST(to_timestamp(recorded_at) AS TIMESTAMP_NTZ) AS recorded_at_utc,
    temperature_c AS enclosure_temp_c,
    temperature_c * 9/5 + 32 AS enclosure_temp_f,
    humidity_pct AS enclosure_humidity_pct,
    pressure_hpa
FROM {{ source('birdnet', 'raw_telemetry') }}
