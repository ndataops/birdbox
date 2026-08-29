{{ config(materialized='view') }}

WITH raw_detections AS (
    SELECT *
    FROM sqlite_scan('/opt/birdbox/data/bronze/birdnet.db', 'detections')
),

raw_labels AS (
    SELECT *
    FROM sqlite_scan('/opt/birdbox/data/bronze/birdnet.db', 'labels')
)

SELECT
    d.id AS raw_id,
    to_timestamp(d.detected_at) AS detected_at,
    l.scientific_name,
    COALESCE(
        scn.common_name,
        -- Fallback for species not yet in seeds/species_common_names.csv:
        -- title-cases the scientific name so it's still readable, not a real common name
        list_aggregate(list_transform(string_split(REPLACE(l.scientific_name, '_', ' '), ' '), part -> upper(part[1:1]) || lower(part[2:])), 'string_agg', ' ')
    ) AS common_name,
    CAST(d.confidence AS DOUBLE) AS confidence_score,
    CAST(d.latitude AS DOUBLE) AS latitude,
    CAST(d.longitude AS DOUBLE) AS longitude,
    d.clip_name AS audio_clip_name,
    d.processing_time_ms,
    d.unlikely AS is_unlikely
FROM raw_detections d
LEFT JOIN raw_labels l
    ON d.label_id = l.id
LEFT JOIN {{ ref('species_common_names') }} scn
    ON LOWER(l.scientific_name) = scn.scientific_name
