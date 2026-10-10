#!/usr/bin/env bash
# Databricks refresh: export SQLite snapshots -> upload to UC volume -> load bronze Delta -> dbt build.
# Stops at the first failing step (set -e), so dbt never builds on a failed export or load.
set -euo pipefail

export HOME="${HOME:-/home/nelson}"

export PATH=/usr/local/bin:/usr/bin:/bin:$PATH
export DATABRICKS_HOST=dbc-5a058c14-7622.cloud.databricks.com
export DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/ec72e9e9841313a7
export DATABRICKS_TOKEN="$(awk -F' *= *' '/^token/{print $2}' "${HOME:-/home/nelson}/.databrickscfg")"
export DBT_PROFILES_DIR=/opt/birdbox/dbt-project-databricks

cd /opt/birdbox
echo "== 1/3 export + upload to volume"
/opt/birdbox/venv/bin/python scripts/export_to_databricks.py
echo "== 2/3 load bronze Delta tables"
/opt/birdbox/venv-dbx/bin/python scripts/load_databricks_bronze.py
echo "== 3/3 dbt build"
cd /opt/birdbox/dbt-project-databricks
/opt/birdbox/venv-dbx/bin/dbt build
echo "== databricks refresh done"