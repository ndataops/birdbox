"""MERGE exported files from the UC volume into birdbox.bronze Delta tables.

Event tables (detections, raw_telemetry) are MERGEd on a stable key: new rows are
inserted, changed rows updated, rows missing from the snapshot deleted. Small
reference tables stay CREATE OR REPLACE. Use --test to run against *_merge_test clones.
"""
import os
import sys

from databricks import sql

VOL = "/Volumes/birdbox/bronze/raw_detections"

# table -> (source expression, key columns). Keys are assumptions: verify with DESCRIBE.
MERGES = {
    "detections": (f"read_files('{VOL}/detections/', format => 'parquet')", ["id"]),
    "raw_telemetry": (f"read_files('{VOL}/raw_telemetry/', format => 'parquet')", ["recorded_at"]),
}
REPLACES = {
    "labels": f"read_files('{VOL}/labels/', format => 'parquet')",
    "ebird_taxonomy": f"read_files('{VOL}/ebird_taxonomy/', format => 'csv', header => true)",
}
MIN_RATIO = 0.9  # refuse to MERGE if the snapshot has < 90% of the current rows


def merge_table(cur, source: str, keys: list[str], target: str) -> dict:
    cur.execute(f"DESCRIBE TABLE {target}")
    cols = []
    for name, *_ in cur.fetchall():
        if not name or name.startswith("#"):
            break
        cols.append(name)

    non_keys = [c for c in cols if c not in keys]
    key_list = ", ".join(f"`{k}`" for k in keys)
    on = " AND ".join(f"t.`{k}` = s.`{k}`" for k in keys)
    changed = " OR ".join(f"NOT (t.`{c}` <=> s.`{c}`)" for c in non_keys)
    src = (
        f"(SELECT * FROM {source} "
        f"QUALIFY row_number() OVER (PARTITION BY {key_list} ORDER BY {key_list}) = 1)"
    )

    cur.execute(f"SELECT count(*) FROM {src}")
    n_src = cur.fetchone()[0]
    cur.execute(f"SELECT count(*) FROM {target}")
    n_tgt = cur.fetchone()[0]
    if n_src == 0 or n_src < MIN_RATIO * n_tgt:
        raise RuntimeError(f"{target}: snapshot has {n_src} rows vs {n_tgt} in table; refusing to MERGE")

    cur.execute(f"""
        MERGE INTO {target} AS t
        USING {src} AS s
        ON {on}
        WHEN MATCHED AND ({changed}) THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
        WHEN NOT MATCHED BY SOURCE THEN DELETE
    """)
    stats = dict(zip([d[0] for d in cur.description], cur.fetchone()))
    return {"source_rows": n_src, "rows_before": n_tgt, **stats}


def main() -> int:
    test = "--test" in sys.argv
    suffix = "_merge_test" if test else ""
    with sql.connect(
        server_hostname=os.environ["DATABRICKS_HOST"],
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
    ) as conn, conn.cursor() as cur:
        for table, (source, keys) in MERGES.items():
            stats = merge_table(cur, source, keys, f"birdbox.bronze.{table}{suffix}")
            print(f"{table}: {stats}")
        if not test:
            for table, source in REPLACES.items():
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