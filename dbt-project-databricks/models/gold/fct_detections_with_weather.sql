{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key='detection_id',
    on_schema_change='fail'
) }}

-- Pairs each detection with the nearest enclosure reading within 15 minutes.
-- The match happens in UTC on both sides; detected_at in the output is Chicago local time.
WITH detections AS (
    SELECT
        f.detection_id,
        f.detected_at,
        f.common_name,
        f.scientific_name,
        f.confidence_score,
        f.confidence_tier,
        u.detected_at_utc
    FROM {{ ref('fct_bird_detections') }} f
    JOIN {{ ref('int_bird_detections_cleaned') }} u
        ON f.detection_id = u.detection_id
    {% if is_incremental() %}
    WHERE f.detected_at >= (
        SELECT COALESCE(
            MAX(detected_at) - INTERVAL {{ var('incremental_lookback_days', 2) }} DAY,
            CAST('1900-01-01' AS TIMESTAMP_NTZ)
        )
        FROM {{ this }}
    )
    {% endif %}
),

telemetry AS (
    SELECT * FROM {{ ref('int_telemetry_cleaned') }}
),

joined AS (
    SELECT
        d.*,
        t.enclosure_temp_f,
        t.enclosure_humidity_pct,
        t.pressure_hpa,
        ROW_NUMBER() OVER (
            PARTITION BY d.detection_id
            ORDER BY ABS(timestampdiff(SECOND, t.recorded_at_utc, d.detected_at_utc))
        ) AS rn
    FROM detections d
    LEFT JOIN telemetry t
        ON t.recorded_at_utc BETWEEN d.detected_at_utc - INTERVAL 15 MINUTE
                                 AND d.detected_at_utc + INTERVAL 15 MINUTE
)

SELECT
    detection_id,
    detected_at,
    common_name,
    scientific_name,
    confidence_score,
    confidence_tier,
    enclosure_temp_f,
    enclosure_humidity_pct,
    pressure_hpa
FROM joined
WHERE rn = 1
