{{ config(
    materialized='table',
    post_hook="COPY {{ this }} TO '/opt/birdbox/data/gold/fct_daily_alerts.parquet' (FORMAT PARQUET)"
) }}

WITH detections AS (
    SELECT * FROM {{ ref('fct_bird_detections') }}
),

first_sightings AS (
    SELECT 
        scientific_name,
        MIN(detected_at) AS first_detected_at
    FROM detections
    GROUP BY scientific_name
)

SELECT 
    d.detection_id,
    d.detected_at,
    d.scientific_name,
    d.common_name,
    d.confidence_score,
    'NEW_SPECIES_UNLOCKED' AS alert_type,
    '🚨 New visitor! A ' || d.common_name || ' was just detected with ' || CAST(ROUND(d.confidence_score * 100, 1) AS VARCHAR) || '% confidence.' AS alert_message
FROM detections d
JOIN first_sightings fs 
    ON d.scientific_name = fs.scientific_name 
    AND d.detected_at = fs.first_detected_at
-- Only flag sightings from the last 24 hours to prevent historical backlog spam
-- Only flag high-confidence detections to avoid misleading low-confidence "new species" claims
WHERE d.detected_at >= CURRENT_TIMESTAMP - INTERVAL 1 DAY
  AND d.confidence_score >= 0.70  -- high tier only: new-species claims need the highest bar
