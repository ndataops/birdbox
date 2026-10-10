"""Regenerates the auto-updating stats block in README.md from the Databricks gold/silver tables.

Usage: update_readme_stats.py [--dry-run]   (--dry-run prints the block; no file write, commit or push)
Credentials: DATABRICKS_TOKEN, or EVIDENCE_SOURCE__birdbox__token (already in the Dagster environment).
"""
import os
import re
import subprocess
import sys

from databricks import sql

HOST = os.environ.get("DATABRICKS_HOST", "dbc-5a058c14-7622.cloud.databricks.com")
HTTP_PATH = os.environ.get("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/ec72e9e9841313a7")
TOKEN = os.environ.get("DATABRICKS_TOKEN") or os.environ.get("EVIDENCE_SOURCE__birdbox__token")
README_PATH = "/opt/birdbox/README.md"

if not TOKEN:
    sys.exit("ERROR: no Databricks token in the environment")

with sql.connect(server_hostname=HOST, http_path=HTTP_PATH, access_token=TOKEN) as conn, conn.cursor() as cur:
    cur.execute("SELECT COUNT(*), COUNT(DISTINCT common_name), MAX(detected_at) FROM birdbox.gold.fct_bird_detections")
    detections, species, last_detection = cur.fetchone()
    cur.execute("SELECT COUNT(*), MAX(recorded_at_utc) FROM birdbox.silver.int_telemetry_cleaned")
    telemetry_count, last_telemetry = cur.fetchone()

if not detections or last_detection is None or last_telemetry is None:
    sys.exit("ERROR: empty result from Databricks, leaving README unchanged")

new_block = f"""<!-- STATS:START -->
## Live stats

- **Detections:** {detections:,}
- **Species identified:** {species}
- **Latest detection:** {last_detection.strftime('%Y-%m-%d %H:%M')} CT
- **Telemetry readings:** {telemetry_count:,}
- **Last updated:** {last_telemetry.strftime('%Y-%m-%d %H:%M UTC')} (auto-generated hourly from Databricks)
<!-- STATS:END -->"""

if "--dry-run" in sys.argv:
    print(new_block)
    sys.exit(0)

readme = open(README_PATH).read()
updated = re.sub(
    r"<!-- STATS:START -->.*?<!-- STATS:END -->",
    new_block,
    readme,
    flags=re.DOTALL,
)

if updated == readme:
    print("No stats change, skipping commit")
else:
    open(README_PATH, "w").write(updated)
    subprocess.run(["git", "add", "README.md"], cwd="/opt/birdbox", check=True)
    result = subprocess.run(
        ["git", "commit", "-m", "chore: auto-update README stats [skip ci]", "--", "README.md"],
        cwd="/opt/birdbox",
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        subprocess.run(["git", "push"], cwd="/opt/birdbox", check=True)
        print("README stats updated and pushed")
    else:
        print(f"Nothing to commit or commit failed: {result.stdout} {result.stderr}")