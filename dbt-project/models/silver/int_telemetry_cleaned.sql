{{ config(materialized='table') }}

SELECT
    recorded_at AT TIME ZONE 'America/Chicago' AS recorded_at,
    temperature_c,
    temperature_f,
    humidity_pct,
    pressure_hpa
FROM {{ ref('stg_telemetry') }}
