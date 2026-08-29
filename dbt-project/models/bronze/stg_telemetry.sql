{{ config(materialized='view') }}

SELECT
    recorded_at::TIMESTAMP AS recorded_at,
    temperature_c,
    temperature_c * 9/5 + 32 AS temperature_f,
    humidity_pct,
    pressure_hpa
FROM sqlite_scan('/opt/birdbox/data/bronze/telemetry.db', 'raw_telemetry')
