import os
import subprocess

from dagster import AssetExecutionContext, asset
from dagster_dbt import DbtCliResource, dbt_assets


class BirdboxAssetError(Exception):
    """Raised when a Birdbox pipeline asset fails."""


BIRDEDGE_HOST = "nelson@10.0.0.233"
REMOTE_TELEMETRY_DB = "/home/nelson/telemetry/telemetry.db"
REMOTE_LOG_SCRIPT = "/home/nelson/telemetry/log_reading.py"
LOCAL_BRONZE_PATH = "/opt/birdbox/data/bronze/telemetry.db"


@asset
def bme280_reading(context: AssetExecutionContext) -> None:
    """Triggers a fresh BME280 sensor reading on birdedge, logged to its local SQLite table."""
    result = subprocess.run(
        ["ssh", BIRDEDGE_HOST, f"python3 {REMOTE_LOG_SCRIPT}"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise BirdboxAssetError(f"Sensor read failed: {result.stderr}")
    context.log.info(result.stdout.strip())


@asset(deps=[bme280_reading])
def bronze_telemetry_sync(context: AssetExecutionContext) -> None:
    """Pulls the latest telemetry.db snapshot from birdedge into bronze on birdbox."""
    result = subprocess.run(
        ["scp", f"{BIRDEDGE_HOST}:{REMOTE_TELEMETRY_DB}", LOCAL_BRONZE_PATH],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        raise BirdboxAssetError(f"Bronze sync failed: {result.stderr}")
    context.log.info(f"Synced telemetry.db to {LOCAL_BRONZE_PATH}")


dbt_project_dir = "/opt/birdbox/dbt-project"

@dbt_assets(
    manifest=os.path.join(dbt_project_dir, "target", "manifest.json")
)
def birdbox_dbt_assets(context, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()


import boto3
from botocore.client import Config as BotoConfig

MINIO_ENDPOINT = os.environ["MINIO_ENDPOINT"]
MINIO_ACCESS_KEY = os.environ["MINIO_ACCESS_KEY"]
MINIO_SECRET_KEY = os.environ["MINIO_SECRET_KEY"]
BIRDNET_BUCKET = "bird-detections-raw"
BIRDNET_KEY = "raw/data/birdnet.db"
LOCAL_BIRDNET_BRONZE_PATH = "/opt/birdbox/data/bronze/birdnet.db"


@asset
def bronze_birdnet_sync(context: AssetExecutionContext) -> None:
    """Pulls the latest birdnet.db snapshot from MinIO (synced there by birdedge's rclone cron) into bronze on birdbox."""
    s3 = boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    head = s3.head_object(Bucket=BIRDNET_BUCKET, Key=BIRDNET_KEY)
    context.log.info(f"Source birdnet.db last modified: {head['LastModified']}, size: {head['ContentLength']} bytes")

    s3.download_file(BIRDNET_BUCKET, BIRDNET_KEY, LOCAL_BIRDNET_BRONZE_PATH)
    context.log.info(f"Synced birdnet.db to {LOCAL_BIRDNET_BRONZE_PATH}")


EVIDENCE_DIR = "/opt/birdbox/field-journal"

@asset(deps=[birdbox_dbt_assets])
def evidence_build(context: AssetExecutionContext) -> None:
    """Rebuilds the Evidence static site from current DuckDB data, so the live demo stays fresh after every dbt run."""
    sources = subprocess.run(
        ["npm", "run", "sources"],
        cwd=EVIDENCE_DIR,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if sources.returncode != 0:
        raise BirdboxAssetError(f"Evidence sources refresh failed: {sources.stderr}")
    context.log.info(sources.stdout.strip())

    build = subprocess.run(
        ["npm", "run", "build"],
        cwd=EVIDENCE_DIR,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if build.returncode != 0:
        raise BirdboxAssetError(f"Evidence build failed: {build.stderr}")
    context.log.info("Evidence static site rebuilt")


@asset(deps=[evidence_build])
def update_readme(context: AssetExecutionContext) -> None:
    """Regenerates the auto-updating stats block in README.md and pushes to GitHub."""
    result = subprocess.run(
        ["/opt/birdbox/venv/bin/python3", "/opt/birdbox/scripts/update_readme_stats.py"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        raise BirdboxAssetError(f"README update failed: {result.stderr}")
    context.log.info(result.stdout.strip())


import shutil as shutil_module
from datetime import datetime, timezone

BACKUP_DIR = "/opt/birdbox/data/backups"
LAKEHOUSE_PATH = "/opt/birdbox/data/lakehouse.duckdb"
MAX_BACKUPS = 7

@asset
def backup_lakehouse(context: AssetExecutionContext) -> None:
    """Nightly backup of the DuckDB lakehouse file, keeping the last 7 days."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_path = f"{BACKUP_DIR}/lakehouse_{timestamp}.duckdb"

    shutil_module.copy2(LAKEHOUSE_PATH, backup_path)
    context.log.info(f"Backed up lakehouse to {backup_path}")

    backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.startswith("lakehouse_")],
        reverse=True,
    )
    for old_backup in backups[MAX_BACKUPS:]:
        os.remove(os.path.join(BACKUP_DIR, old_backup))
        context.log.info(f"Removed old backup: {old_backup}")
