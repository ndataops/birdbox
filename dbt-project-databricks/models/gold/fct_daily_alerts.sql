{{ config(materialized='table') }}

WITH detections AS (
    SELECT * FROM {{ ref('fct_bird_detections') }}
),

first_sightings AS (
    SELECT scientific_name, MIN(detected_at) AS first_detected_at
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
    concat('🚨 New visitor! A ', d.common_name, ' was just detected with ',
           CAST(ROUND(d.confidence_score * 100, 1) AS STRING), '% confidence.') AS alert_message
FROM detections d
JOIN first_sightings fs
    ON d.scientific_name = fs.scientific_name
    AND d.detected_at = fs.first_detected_at
-- Last 24 hours, compared in Chicago local time (detected_at is naive Chicago time).
-- The old version compared it to a UTC CURRENT_TIMESTAMP, so the window was ~19h.
-- High-confidence only: new-species claims need the highest bar.
WHERE d.detected_at >= convert_timezone('UTC', 'America/Chicago', CAST(current_timestamp() AS TIMESTAMP_NTZ)) - INTERVAL 1 DAY
  AND d.confidence_score >= 0.70
