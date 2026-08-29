from dagster import ScheduleDefinition, define_asset_job
from .assets import birdbox_dbt_assets, evidence_build

telemetry_job = define_asset_job(
    name="telemetry_job",
    selection=["bme280_reading", "bronze_telemetry_sync"],
)

telemetry_schedule = ScheduleDefinition(
    job=telemetry_job,
    cron_schedule="*/5 * * * *",
)

birdnet_job = define_asset_job(
    name="birdnet_job",
    selection=["bronze_birdnet_sync"],
)

birdnet_schedule = ScheduleDefinition(
    job=birdnet_job,
    cron_schedule="*/10 * * * *",
)

dbt_job = define_asset_job(
    name="dbt_job",
    selection=[birdbox_dbt_assets, evidence_build],
)

dbt_schedule = ScheduleDefinition(
    job=dbt_job,
    cron_schedule="*/15 * * * *",
)
