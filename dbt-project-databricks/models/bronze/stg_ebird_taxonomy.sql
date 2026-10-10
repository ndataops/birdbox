{{ config(materialized='view') }}

SELECT
    LOWER(scientific_name) AS scientific_name,
    common_name
FROM {{ source('birdnet', 'ebird_taxonomy') }}
