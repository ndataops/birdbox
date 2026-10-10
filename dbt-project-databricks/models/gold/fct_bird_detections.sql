{{ config(materialized='table', contract={'enforced': true}) }}

SELECT
    detection_id,
    convert_timezone('UTC', 'America/Chicago', detected_at_utc) AS detected_at,  -- naive Chicago local time
    common_name,
    scientific_name,
    confidence_score,
    latitude,
    longitude,
    audio_clip_name,
    processing_time_ms,
    CASE
        WHEN confidence_score >= 0.70 THEN 'High'
        WHEN confidence_score >= 0.50 THEN 'Medium'
        ELSE 'Low'
    END AS confidence_tier
FROM {{ ref('int_bird_detections_cleaned') }}
WHERE confidence_score >= 0.30
  AND is_unlikely = 0
  -- Excluding 8/16-8/17/2026 by UTC date: mic hardware testing sessions, not real detections.
  -- NOTE: this reproduces the legacy DuckDB behavior, where `detected_at::DATE` bound to the
  -- UTC source column instead of the Chicago-time alias. See docs/lessons-learned.md.
  AND CAST(detected_at_utc AS DATE) NOT IN (DATE '2026-08-16', DATE '2026-08-17')