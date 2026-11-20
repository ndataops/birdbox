-- Unity Catalog metric view over the gold layer. Defines each KPI once so
-- dashboards, SQL and AI tools share the same definitions.
-- Note: detected_at is naive America/Chicago local time, so detection_date
-- and detection_hour are Chicago local. enclosure_temp is the sealed
-- enclosure's internal temperature, not ambient.
CREATE OR REPLACE VIEW birdbox.gold.mv_detections
WITH METRICS
LANGUAGE YAML
AS $$
version: 0.1
source: birdbox.gold.fct_detections_with_weather
dimensions:
  - name: species
    expr: common_name
  - name: scientific_name
    expr: scientific_name
  - name: confidence_tier
    expr: confidence_tier
  - name: detection_date
    expr: CAST(detected_at AS DATE)
  - name: detection_hour
    expr: HOUR(detected_at)
measures:
  - name: detection_count
    expr: COUNT(1)
  - name: distinct_species
    expr: COUNT(DISTINCT common_name)
  - name: high_confidence_rate
    expr: COUNT(1) FILTER (WHERE confidence_tier = 'High') / COUNT(1)
  - name: avg_confidence
    expr: AVG(confidence_score)
  - name: avg_enclosure_temp_f
    expr: AVG(enclosure_temp_f)
$$