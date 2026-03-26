from datetime import datetime
from google.cloud import bigquery
from prefect import flow, task
import os

client = bigquery.Client()
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")

#-------------------------------------- check max date --------------------------------------------
@task(log_prints=True, retries=3, retry_delay_seconds=10)
def check_existing_data(entity) -> datetime:
    try:
        client.get_table(f"{GCP_PROJECT_ID}.bronze.{entity}")
    except Exception:
        return None #returns none if table doesnt exist, this indcates us to load everyhting in the bucket to staging
    query = f"SELECT MAX(load_date) as max_date FROM `{GCP_PROJECT_ID}.bronze.{entity}`"
    result = client.query(query).result()
    row = list(result)[0]
    max_date = row.max_date  # returns a date object or None
    return max_date


#--------------------------------------- load to staging -------------------------------------------
# configure the load job
stg_job_config = bigquery.LoadJobConfig(
    source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    autodetect=True,
    write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
)
@task(log_prints=True, retries=3, retry_delay_seconds=10)
def write_bucket_to_stg_bronze(entity: str, today: str, incremental: bool = False):
    # GCS URI — wildcard grabs all files for that run date
    partition_key = "run_date" if incremental else "snapshot_date"
    uri = f"gs://{GCS_BUCKET_NAME}/raw/{entity}/{partition_key}={today}/{entity}*.ndjson"

    # load into staging table
    table_ref = f"{GCP_PROJECT_ID}.bronze.stg_{entity}"
    load_job = client.load_table_from_uri(uri, table_ref, job_config=stg_job_config)
    load_job.result()  # waits for completion

    print(f"Loaded {load_job.output_rows} rows into {table_ref}")