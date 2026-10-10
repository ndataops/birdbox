-- Fails if the newest telemetry reading is older than the allowed window (default 180 min).
-- Loosened from 30 min because Databricks loads are batched, not every 5 minutes.
SELECT
    MAX(recorded_at_utc) AS most_recent_reading_utc,
    CAST(current_timestamp() AS TIMESTAMP_NTZ) AS checked_at_utc
FROM {{ ref('stg_telemetry') }}
HAVING MAX(recorded_at_utc) < CAST(current_timestamp() AS TIMESTAMP_NTZ) - make_interval(0, 0, 0, 0, 0, {{ var('telemetry_freshness_minutes') }}, 0)
