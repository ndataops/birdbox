from dagster import Definitions, run_status_sensor, DagsterRunStatus, RunFailureSensorContext
from dagster_dbt import DbtCliResource
import os
import urllib.request
import json

from .assets import bme280_reading, bronze_telemetry_sync, bronze_birdnet_sync, birdbox_dbt_assets, evidence_build, update_readme, backup_lakehouse, dbt_project_dir
from .schedules import telemetry_job, telemetry_schedule, birdnet_job, birdnet_schedule, dbt_job, dbt_schedule, backup_job, backup_schedule


@run_status_sensor(run_status=DagsterRunStatus.FAILURE)
def discord_failure_alert(context: RunFailureSensorContext):
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return
    message = {
        "content": f"🚨 **Birdbox job failed**\n"
                   f"Job: `{context.dagster_run.job_name}`\n"
                   f"Run ID: `{context.dagster_run.run_id[:8]}`\n"
                   f"Error: {context.dagster_event.message[:500] if context.dagster_event and context.dagster_event.message else '(no message)'}"
    }
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps(message).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "Birdbox-Dagster-Sensor/1.0"},
    )
    urllib.request.urlopen(req)


defs = Definitions(
    assets=[birdbox_dbt_assets, bme280_reading, bronze_telemetry_sync, bronze_birdnet_sync, evidence_build, update_readme, backup_lakehouse],
    jobs=[telemetry_job, birdnet_job, dbt_job, backup_job],
    schedules=[telemetry_schedule, birdnet_schedule, dbt_schedule, backup_schedule],
    sensors=[discord_failure_alert],
    resources={
        "dbt": DbtCliResource(project_dir=dbt_project_dir, dbt_executable="/opt/birdbox/dagster_env/bin/dbt"),
    },
)
