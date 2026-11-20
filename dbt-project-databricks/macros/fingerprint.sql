{% macro fingerprint(model_name) %}
  {% set q %}
    select
      count(*) as n,
      coalesce(sum(crc32(concat_ws('|',
        cast(detection_id as string),
        cast(detected_at as string),
        coalesce(cast(enclosure_temp_f as string), ''),
        coalesce(cast(enclosure_humidity_pct as string), ''),
        coalesce(cast(pressure_hpa as string), '')
      ))), 0) as chk
    from {{ ref(model_name) }}
  {% endset %}
  {% set r = run_query(q) %}
  {{ log("FINGERPRINT=" ~ r.rows[0][0] ~ "|" ~ r.rows[0][1], info=True) }}
{% endmacro %}