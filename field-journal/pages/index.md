# The Birdbox Live Feed

A production-grade analytical data product capturing urban wildlife from a rooftop.

```stats_summary
SELECT 
    count(*) AS total_detections,
    count(DISTINCT common_name) AS species_count,
    datediff('day', min(detected_at), max(detected_at)) AS days_running,
    strftime(max(detected_at), '%b %-d, %-I:%M %p') AS last_detection
FROM birdbox.fct_bird_detections
```

<BigValue data={stats_summary} value=total_detections title="Total detections"/>
<BigValue data={stats_summary} value=species_count title="Species identified"/>
<BigValue data={stats_summary} value=days_running title="Days running" fmt="0"/>
<BigValue data={stats_summary} value=last_detection title="Last detection"/>

```date_bounds
SELECT detected_at FROM birdbox.fct_bird_detections
```

<DateRange
    name=date_filter
    data={date_bounds}
    dates=detected_at
    range="All Time"
/>

## New Arrivals

```fct_new_arrivals
SELECT scientific_name, detected_at, confidence_score, alert_message
FROM birdbox.fct_daily_alerts
ORDER BY detected_at DESC
LIMIT 5
```

{#if fct_new_arrivals.length > 0}
<ul>
{#each fct_new_arrivals as alert}
<li>{alert.alert_message}</li>
{/each}
</ul>
{:else}
No new species in the last 24 hours — check back soon.
{/if}

## Detection Confidence

Confidence tiers reflect BirdNET-Go's identification certainty: **High** (70%+) is reliable, **Medium** (50–69%) is plausible but unverified, **Low** (30–49%) is uncertain and may include misidentifications. Detections below 30% confidence are excluded entirely. The New Arrivals feed above only surfaces high-confidence detections, to avoid false "new species" claims.

```fct_confidence_breakdown
SELECT confidence_tier, count(*) AS detections
FROM birdbox.fct_bird_detections
WHERE detected_at::DATE >= '${inputs.date_filter.start}'::DATE
  AND detected_at::DATE <= '${inputs.date_filter.end}'::DATE
GROUP BY confidence_tier
ORDER BY CASE confidence_tier WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END
```

<BarChart
    data={fct_confidence_breakdown}
    x=confidence_tier
    y=detections
    sort=false
    title="Detections by Confidence Tier"
/>

## Detections by Species

```fct_bird_detections_summary
SELECT common_name AS species, count(*) AS detections 
FROM birdbox.fct_bird_detections 
WHERE detected_at::DATE >= '${inputs.date_filter.start}'::DATE
  AND detected_at::DATE <= '${inputs.date_filter.end}'::DATE
GROUP BY common_name 
ORDER BY detections DESC 
LIMIT 15
```

<BarChart 
    data={fct_bird_detections_summary} 
    x=species 
    y=detections 
    swapXY=true 
    sort=false
    title="Top 15 Species by Detection Count"
/>

## Activity by Hour of Day

```fct_bird_detections_by_hour
SELECT 
    EXTRACT(HOUR FROM detected_at) AS hour_of_day,
    count(*) AS detections
FROM birdbox.fct_bird_detections 
WHERE detected_at::DATE >= '${inputs.date_filter.start}'::DATE
  AND detected_at::DATE <= '${inputs.date_filter.end}'::DATE
GROUP BY hour_of_day
ORDER BY hour_of_day
```

<BarChart 
    data={fct_bird_detections_by_hour} 
    x=hour_of_day 
    y=detections 
    title="Detections by Hour of Day (24hr, Local Time)"
/>

## Species Activity Patterns

```fct_species_hour_heatmap
WITH top_species AS (
    SELECT common_name
    FROM birdbox.fct_bird_detections
    WHERE detected_at::DATE >= '${inputs.date_filter.start}'::DATE
      AND detected_at::DATE <= '${inputs.date_filter.end}'::DATE
    GROUP BY common_name
    ORDER BY count(*) DESC
    LIMIT 10
)
SELECT 
    d.common_name AS species,
    LPAD(CAST(EXTRACT(HOUR FROM d.detected_at) AS VARCHAR), 2, '0') AS hour_of_day,
    count(*) AS detections
FROM birdbox.fct_bird_detections d
WHERE d.detected_at::DATE >= '${inputs.date_filter.start}'::DATE
  AND d.detected_at::DATE <= '${inputs.date_filter.end}'::DATE
  AND d.common_name IN (SELECT common_name FROM top_species)
GROUP BY d.common_name, hour_of_day
ORDER BY hour_of_day, d.common_name
```

<Heatmap
    data={fct_species_hour_heatmap}
    x=hour_of_day
    y=species
    value=detections
    title="Top 10 Species by Hour of Day"
/>

## Weather Conditions at Detection Time

```species_list
SELECT DISTINCT common_name
FROM birdbox.fct_detections_with_weather
WHERE temperature_f IS NOT NULL
ORDER BY common_name
```

<Dropdown data={species_list} name=species_filter value=common_name multiple selectAllByDefault title="Filter species">
</Dropdown>

```fct_weather_scatter
SELECT temperature_f, humidity_pct, common_name, detected_at
FROM birdbox.fct_detections_with_weather
WHERE temperature_f IS NOT NULL
  AND detected_at::DATE >= '${inputs.date_filter.start}'::DATE
  AND detected_at::DATE <= '${inputs.date_filter.end}'::DATE
  AND common_name IN ${inputs.species_filter.value}
```

<ScatterPlot
    data={fct_weather_scatter}
    x=temperature_f
    y=humidity_pct
    yFmt="0.0'%'"
    series=common_name
    title="Temperature vs Humidity at Detection Time"
/>

## 🎙️ Recent Visitors Log

```fct_bird_detections_table
SELECT strftime(detected_at, '%Y-%m-%d %I:%M:%S %p') AS "Timestamp", common_name AS "Common Name", scientific_name AS "Scientific Name", confidence_tier AS "Confidence Tier" FROM birdbox.fct_bird_detections ORDER BY detected_at DESC
```

<DataTable data={fct_bird_detections_table} search=true />
