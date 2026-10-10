{{ config(materialized='view') }}

-- detected_at is a Unix epoch (UTC). Kept as naive UTC here; converted to Chicago time in gold only.
SELECT
    d.id AS raw_id,
    CAST(timestamp_seconds(d.detected_at) AS TIMESTAMP_NTZ) AS detected_at_utc,
    l.scientific_name,
    COALESCE(
        et.common_name,
        scn.common_name,
        -- Final fallback: title-cased scientific name (not a real common name)
        initcap(replace(l.scientific_name, '_', ' '))
    ) AS common_name,
    CAST(d.confidence AS DOUBLE) AS confidence_score,
    CAST(d.latitude AS DOUBLE) AS latitude,
    CAST(d.longitude AS DOUBLE) AS longitude,
    d.clip_name AS audio_clip_name,
    d.processing_time_ms,
    CAST(d.unlikely AS INT) AS is_unlikely
FROM {{ source('birdnet', 'detections') }} d
LEFT JOIN {{ source('birdnet', 'labels') }} l
    ON d.label_id = l.id
LEFT JOIN {{ ref('stg_ebird_taxonomy') }} et
    ON LOWER(l.scientific_name) = et.scientific_name
LEFT JOIN {{ ref('species_common_names') }} scn
    ON LOWER(l.scientific_name) = scn.scientific_name
