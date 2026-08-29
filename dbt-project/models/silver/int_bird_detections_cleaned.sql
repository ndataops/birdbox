{{ config(materialized='table') }}

SELECT
    raw_id AS detection_id,
    detected_at,
    common_name,
    TRIM(LOWER(scientific_name)) AS scientific_name,
    confidence_score,
    latitude,
    longitude,
    audio_clip_name,
    processing_time_ms,
    is_unlikely
FROM {{ ref('stg_birdnet_detections') }}
