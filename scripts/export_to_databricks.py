import duckdb, pathlib, subprocess

OUT = pathlib.Path("/opt/birdbox/data/export")
VOL = "dbfs:/Volumes/birdbox/bronze/raw_detections"
TABLES = [
    ("/opt/birdbox/data/bronze/birdnet.db", "detections"),
    ("/opt/birdbox/data/bronze/birdnet.db", "labels"),
    ("/opt/birdbox/data/bronze/telemetry.db", "raw_telemetry"),
]

OUT.mkdir(parents=True, exist_ok=True)
con = duckdb.connect()
con.execute("INSTALL sqlite; LOAD sqlite;")
for db, table in TABLES:
    path = OUT / f"{table}.parquet"
    con.execute(f"COPY (SELECT * FROM sqlite_scan('{db}', '{table}')) TO '{path}' (FORMAT PARQUET)")
    n = con.execute(f"SELECT count(*) FROM '{path}'").fetchone()[0]
    print(f"{table}: {n} rows")
    subprocess.run(["databricks", "fs", "mkdir", f"{VOL}/{table}"], check=True)
    subprocess.run(["databricks", "fs", "cp", "--overwrite", str(path),
                    f"{VOL}/{table}/{table}.parquet"], check=True)

subprocess.run(["databricks", "fs", "mkdir", f"{VOL}/ebird_taxonomy"], check=True)
subprocess.run(["databricks", "fs", "cp", "--overwrite",
                "/opt/birdbox/data/bronze/ebird_taxonomy.csv",
                f"{VOL}/ebird_taxonomy/ebird_taxonomy.csv"], check=True)
print("done")
