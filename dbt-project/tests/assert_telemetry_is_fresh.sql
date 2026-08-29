-- Fails if the most recent telemetry reading is older than 30 minutes.
-- Telemetry syncs every 5 minutes; 30 min gives generous padding for
-- transient network blips without masking a genuinely broken sync
-- (the exact failure mode that silently broke the dbt layer for 6 days
-- before we caught it manually on 2026-08-28).

SELECT
    MAX(recorded_at) AS most_recent_reading,
    CURRENT_TIMESTAMP AS checked_at
FROM {{ ref('stg_telemetry') }}
HAVING MAX(recorded_at) < CURRENT_TIMESTAMP - INTERVAL 30 MINUTE
