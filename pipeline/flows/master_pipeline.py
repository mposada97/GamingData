import subprocess
from pathlib import Path
from prefect import flow, task, get_run_logger

from extract_rawg import extract_rawg_flow
from load_to_bronze import load_to_bronze

DBT_PROJECT_DIR = "/code/gaming_data_dbt"


@task(retries=0)
def run_dbt_build(selector: str = None):
    logger = get_run_logger()
    cmd = ["dbt", "build", "--project-dir", DBT_PROJECT_DIR]
    if selector:
        cmd.extend(["-s", selector])
    logger.info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    logger.info(result.stdout)
    if result.returncode != 0:
        logger.error(result.stderr)
        raise RuntimeError(f"dbt build failed with exit code {result.returncode}")
    return result.stdout


@flow(name="gaming_data_pipeline")
def gaming_data_pipeline():
    logger = get_run_logger()

    logger.info("Step 1: Extract RAWG to GCS")
    extract_rawg_flow()

    logger.info("Step 2: Load GCS to bronze BigQuery")
    load_to_bronze()

    logger.info("Step 3: Build silver layer")
    run_dbt_build(selector="path:models/rawg/silver")

    logger.info("Step 4: Build gold layer")
    run_dbt_build(selector="path:models/rawg/gold")

    logger.info("Pipeline complete.")


if __name__ == "__main__":
    gaming_data_pipeline()