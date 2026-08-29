{{ config(materialized='table') }}

WITH detections AS (
    SELECT * FROM {{ ref('fct_bird_detections') }}
),

telemetry AS (
    SELECT * FROM {{ ref('int_telemetry_cleaned') }}
),

joined AS (
    SELECT
        d.*,
        t.temperature_f,
        t.humidity_pct,
        t.pressure_hpa,
        t.recorded_at AS telemetry_recorded_at,
        ROW_NUMBER() OVER (
            PARTITION BY d.detection_id
            ORDER BY ABS(EPOCH(d.detected_at) - EPOCH(t.recorded_at))
        ) AS rn
    FROM detections d
    LEFT JOIN telemetry t
        ON t.recorded_at BETWEEN d.detected_at - INTERVAL 15 MINUTE
                              AND d.detected_at + INTERVAL 15 MINUTE
)

SELECT
    detection_id,
    detected_at,
    common_name,
    scientific_name,
    confidence_score,
    confidence_tier,
    temperature_f,
    humidity_pct,
    pressure_hpa
FROM joined
WHERE rn = 1
