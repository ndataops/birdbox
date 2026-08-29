"""Regenerates the auto-updating stats block in README.md from live DuckDB data."""
import re
import subprocess
import duckdb

DB_PATH = "/opt/birdbox/data/lakehouse.duckdb"
README_PATH = "/opt/birdbox/README.md"

con = duckdb.connect(DB_PATH, read_only=True)
detections, species, last_detection = con.execute(
    "SELECT COUNT(*), COUNT(DISTINCT common_name), MAX(detected_at) FROM fct_bird_detections"
).fetchone()
telemetry_count, last_telemetry = con.execute(
    "SELECT COUNT(*), MAX(recorded_at) FROM int_telemetry_cleaned"
).fetchone()
con.close()

new_block = f"""<!-- STATS:START -->
## Live stats

- **Detections:** {detections:,}
- **Species identified:** {species}
- **Latest detection:** {last_detection.strftime('%Y-%m-%d %H:%M UTC')}
- **Telemetry readings:** {telemetry_count:,}
- **Last updated:** {last_telemetry.strftime('%Y-%m-%d %H:%M UTC')} (auto-generated on every dbt run)
<!-- STATS:END -->"""

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
        ["git", "commit", "-m", "chore: auto-update README stats [skip ci]"],
        cwd="/opt/birdbox",
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        subprocess.run(["git", "push"], cwd="/opt/birdbox", check=True)
        print("README stats updated and pushed")
    else:
        print(f"Nothing to commit or commit failed: {result.stdout} {result.stderr}")
