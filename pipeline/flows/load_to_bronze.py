from datetime import datetime
from google.cloud import bigquery, storage
from prefect import flow, task
import os

client = bigquery.Client()
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")

#-------------------------------------- check max dates --------------------------------------------
def get_latest_bronze_date(entity: str) -> datetime:
    try:
        client.get_table(f"{GCP_PROJECT_ID}.bronze.{entity}")
    except Exception:
        return None #returns none if table doesnt exist, this indcates us to load everyhting in the bucket to staging
    query = f"SELECT MAX(load_date) as max_date FROM `{GCP_PROJECT_ID}.bronze.{entity}`"
    result = client.query(query).result()
    row = list(result)[0]
    max_date = row.max_date  # returns a date object or None
    return max_date

def get_gcs_dates(entity: str, incremental: bool = False) -> str:
    partition_key = "run_date" if incremental else "snapshot_date"
    prefix = f"raw/{entity}/"

    blobs = list(storage.Client().bucket(GCS_BUCKET_NAME).list_blobs(prefix=prefix))
    dates = set()
    for blob in blobs:
        for part in blob.name.split("/"):
            if part.startswith(f"{partition_key}="):
                dates.add(part.split("=")[1])
    return sorted(dates)

def get_paths_to_load(entity: str, incremental: bool = False) -> list:
    partition_key = "run_date" if incremental else "snapshot_date"
    gcs_dates = get_gcs_dates(entity, incremental)
    
    if incremental:
        max_bq_date = get_latest_bronze_date(entity)
        if max_bq_date is None:
            dates_to_load =  gcs_dates
        else:
            dates_to_load = [d for d in gcs_dates if d > str(max_bq_date)]
    else:
        dates_to_load = [gcs_dates[-1]] if gcs_dates else []
    paths_to_load = []
    for date in dates_to_load:
        paths_to_load.append([date,f"gs://{GCS_BUCKET_NAME}/raw/{entity}/{partition_key}={date}/{entity}*.ndjson"])
    return paths_to_load


#--------------------------------------- load to staging -------------------------------------------
# configure the load job to generate staging tables
stg_job_config = bigquery.LoadJobConfig(
    source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    autodetect=True,
    write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
)
@task(log_prints=True, retries=3, retry_delay_seconds=10)
def write_to_staging(entity: str, uri: str, load_date: str):
    table_ref = f"{GCP_PROJECT_ID}.bronze.stg_{entity}"
    load_job = client.load_table_from_uri(uri, table_ref, job_config=stg_job_config)
    load_job.result()
    
    query = f"""
        CREATE OR REPLACE TABLE `{table_ref}` AS
        SELECT *, '{load_date}' AS load_date
        FROM `{table_ref}`
    """
    client.query(query).result()
    print(f"Loaded to staging: {entity} for {load_date}")


@task(log_prints=True)
def audit_staging(entity: str):
    # checks here
    pass

@task(log_prints=True)
def publish_to_bronze(entity: str):
    # insert into final, drop staging
    pass

#---------------------------------------flow------------------------------------------
@flow(name="load_to_bronze")
def load_to_bronze():
    entities = [
        ("games", True),
        ("genres", False),
        ("platforms", False),
        ("publishers", False),
        ("tags", False),
    ]
    
    for entity, incremental in entities:
        paths_to_load = get_paths_to_load(entity, incremental)
        
        for load_date, uri in paths_to_load:
            write_to_staging(entity, uri, load_date)
            audit_staging(entity)
            publish_to_bronze(entity)