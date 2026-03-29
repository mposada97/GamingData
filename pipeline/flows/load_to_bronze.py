from datetime import datetime
from google.cloud import bigquery, storage
from google.cloud.exceptions import NotFound
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
            dates_to_load = [d for d in gcs_dates if d >= str(max_bq_date)]
    else:
        dates_to_load = [gcs_dates[-1]] if gcs_dates else []
    paths_to_load = []
    for date in dates_to_load:
        paths_to_load.append([date,f"gs://{GCS_BUCKET_NAME}/raw/{entity}/{partition_key}={date}/{entity}*.ndjson"])
    return paths_to_load


#----------------------------- load to staging, audit and publish to bronze -------------------------------------------
# configure the load job to generate staging tables
@task(log_prints=True, retries=3, retry_delay_seconds=10)
def write_to_staging(entity: str, uri: str, load_date: str, incremental: bool):
    table_ref = f"{GCP_PROJECT_ID}.bronze.stg_{entity}"
    bronze_ref = f"{GCP_PROJECT_ID}.bronze.{entity}"


    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    
    try:
        bronze_table = client.get_table(bronze_ref)
        job_config.schema = [field for field in bronze_table.schema if field.name != "load_date"]
    except NotFound:
        job_config.autodetect = True
    
    load_job = client.load_table_from_uri(uri, table_ref, job_config=job_config)
    load_job.result()

    
    if incremental:
        query = f"""
            CREATE OR REPLACE TABLE `{table_ref}` AS
            SELECT * EXCEPT(row_num) FROM (
                SELECT *, '{load_date}' AS load_date, ROW_NUMBER() OVER (PARTITION BY id ORDER BY updated DESC) as row_num
                FROM `{table_ref}`
            ) WHERE row_num = 1
        """
    else:
        query = f"""
            CREATE OR REPLACE TABLE `{table_ref}` AS
            SELECT *, '{load_date}' AS load_date
            FROM `{table_ref}`
        """
    client.query(query).result()
    print(f"Loaded to staging: {entity} for {load_date}")


@task(log_prints=True)
def audit_staging(entity: str):
    table_ref = f"{GCP_PROJECT_ID}.bronze.stg_{entity}"

    row_count_test_query = f"""
    SELECT COUNT(*) row_count
    FROM `{table_ref}`
    """

    null_id_test_query = f"""
    SELECT COUNT(*) row_count
    FROM `{table_ref}`
    WHERE id IS NULL
    """

    row_count = client.query(row_count_test_query).result()
    row_count = list(row_count)[0].row_count
    if row_count > 0:
        print(f"Row count Test passed: {entity} staging has {row_count} rows")
    else:
        raise ValueError(f"Audit failed: {entity} staging table has 0 rows")

    null_id_count = client.query(null_id_test_query).result()
    null_id_count = list(null_id_count)[0].row_count
    if null_id_count == 0:
        print(f"No Null id's in {entity} staging table. ID test passed.")
    else:
        raise ValueError(f"Audit failed: {entity} has {null_id_count} null IDs")

@task(log_prints=True)
def publish_to_bronze(entity: str):
    bronze_stg_table = f"{GCP_PROJECT_ID}.bronze.stg_{entity}"
    bronze_table = f"{GCP_PROJECT_ID}.bronze.{entity}"

    try:
        client.get_table(bronze_table)
        # delete matching rows, then insert
        client.query(f"""
            DELETE FROM `{bronze_table}` T
            WHERE EXISTS (
                SELECT 1 FROM `{bronze_stg_table}` S
                WHERE S.id = T.id AND S.load_date = T.load_date
            )
        """).result()
        client.query(f"""
            INSERT INTO `{bronze_table}`
            SELECT * FROM `{bronze_stg_table}`
        """).result()
    except NotFound:
        client.query(f"CREATE TABLE `{bronze_table}` AS SELECT * FROM `{bronze_stg_table}`").result()
    
    print(f"Published {entity} to bronze")
    client.delete_table(bronze_stg_table)
    print(f"Dropped stg_{entity}")




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
            try:
                write_to_staging(entity, uri, load_date, incremental)
                audit_staging(entity)
                publish_to_bronze(entity)
            except Exception as e:
                stg_ref = f"{GCP_PROJECT_ID}.bronze.stg_{entity}"
                client.delete_table(stg_ref, not_found_ok=True)
                raise e
if __name__ == "__main__":
    load_to_bronze()