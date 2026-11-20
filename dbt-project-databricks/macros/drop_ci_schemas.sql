{% macro drop_ci_schemas() %}
  {% if target.name != 'ci' or not target.schema.startswith('ci_pr_') %}
    {{ exceptions.raise_compiler_error("drop_ci_schemas only runs on the ci target with a ci_pr_ schema") }}
  {% endif %}
  {% for suffix in ['', '_bronze', '_silver', '_gold'] %}
    {% do run_query("drop schema if exists " ~ target.database ~ "." ~ target.schema ~ suffix ~ " cascade") %}
  {% endfor %}
{% endmacro %}