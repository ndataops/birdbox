"""Load exported files from the Unity Catalog volume into birdbox.bronze Delta tables.

Idempotent: CREATE OR REPLACE TABLE swaps the table atomically, so readers keep seeing
the old version until the new one is complete. Credentials come from environment variables.
"""
import os
import sys

from databricks import sql

VOL = "/Volumes/birdbox/bronze/raw_detections"
LOADS = {
    "detections": f"read_files('{VOL}/detections/', format => 'parquet')",
    "labels": f"read_files('{VOL}/labels/', format => 'parquet')",
    "raw_telemetry": f"read_files('{VOL}/raw_telemetry/', format => 'parquet')",
    "ebird_taxonomy": f"read_files('{VOL}/ebird_taxonomy/', format => 'csv', header => true)",
}


def main() -> int:
    with sql.connect(
        server_hostname=os.environ["DATABRICKS_HOST"],
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
    ) as conn, conn.cursor() as cur:
        for table, source in LOADS.items():
            cur.execute(f"CREATE OR REPLACE TABLE birdbox.bronze.{table} AS SELECT * FROM {source}")
            cur.execute(f"SELECT count(*) FROM birdbox.bronze.{table}")
            n = cur.fetchone()[0]
            print(f"{table}: {n} rows")
            if n == 0:
                print(f"ERROR: {table} loaded zero rows", file=sys.stderr)
                return 1
    print("bronze load done")
    return 0


if __name__ == "__main__":
    sys.exit(main())