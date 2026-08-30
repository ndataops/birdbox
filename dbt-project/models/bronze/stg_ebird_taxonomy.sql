{{ config(materialized='view') }}

SELECT
    LOWER(scientific_name) AS scientific_name,
    common_name
FROM read_csv_auto('/opt/birdbox/data/bronze/ebird_taxonomy.csv')
