from dagster import Definitions
from dagster_dbt import DbtCliResource

from .assets import bme280_reading, bronze_telemetry_sync, bronze_birdnet_sync, birdbox_dbt_assets, evidence_build, dbt_project_dir
from .schedules import telemetry_job, telemetry_schedule, birdnet_job, birdnet_schedule, dbt_job, dbt_schedule

defs = Definitions(
    assets=[birdbox_dbt_assets, bme280_reading, bronze_telemetry_sync, bronze_birdnet_sync, evidence_build],
    jobs=[telemetry_job, birdnet_job, dbt_job],
    schedules=[telemetry_schedule, birdnet_schedule, dbt_schedule],
    resources={
        "dbt": DbtCliResource(project_dir=dbt_project_dir, dbt_executable="/opt/birdbox/dagster_env/bin/dbt"),
    },
)
