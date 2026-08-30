{{ config(
    materialized='table',
    contract={'enforced': true},
    post_hook="COPY {{ this }} TO '/opt/birdbox/data/gold/fct_bird_detections.parquet' (FORMAT PARQUET)"
) }}

SELECT
    detection_id,
    detected_at AT TIME ZONE 'America/Chicago' AS detected_at,
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
  -- Excluding 8/16-8/17/2026: mic hardware testing sessions, not real detections
  AND detected_at::DATE NOT IN ('2026-08-16', '2026-08-17')
