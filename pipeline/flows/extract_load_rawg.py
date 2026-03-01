import os
import json
import requests
from datetime import datetime, timedelta, timezone
from google.cloud import storage
from prefect import flow, task

RAWG_BASE_URL = "https://api.rawg.io/api"
RAWG_API_KEY = os.getenv("RAWG_API_KEY")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
STATE_BLOB_PATH = "raw/state/last_run.json"
BACKFILL_START = "1900-01-01"


# ── API client (used to get data from any rawg endpoint) ────────────────────────────────────────────────────────────────
def fetch_all_pages(endpoint: str, params: dict[str, any] = {}) -> list[dict]:
    """Generic paginated fetcher. Works for any RAWG endpoint."""
    base_params = {"key": RAWG_API_KEY, "page_size": 40, "page": 1}
    results = []
    if params:
        base_params.update(params)

    url = f"{RAWG_BASE_URL}/{endpoint}"

    while url:
        response = requests.get(url, params=base_params)
        response.raise_for_status()
        data = response.json()
        results.extend(data.get("results", []))
        url = data.get("next")      # RAWG returns the next page URL directly
        params = {}  
    return results 

# ── state management ──────────────────────────────────────────────────────────
# This is used to track the last successful run date so we can resume from the last successful run.
@task(log_prints=True)
def read_last_run_date() -> str:
    """
    Reads the last successful run date from GCS state file.
    If the file doesn't exist (first ever run), falls back to BACKFILL_START
    so the full historical dataset gets pulled.
    """
    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(STATE_BLOB_PATH)

    if not blob.exists():
        print(f"No state file found — defaulting to full backfill from {BACKFILL_START}")
        return BACKFILL_START

    state = json.loads(blob.download_as_text())
    last_run = state["last_successful_run"]
    print(f"Last successful run was: {last_run}")
    return last_run


@task(log_prints=True)
def write_last_run_date(run_date: str) -> None:
    """
    Overwrites the state file in GCS with today's date.
    Only called at the end of a successful flow run.
    """
    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(STATE_BLOB_PATH)

    state = {"last_successful_run": run_date}
    blob.upload_from_string(json.dumps(state), content_type="application/json")
    print(f"State updated — last successful run set to: {run_date}")

# ── fetch tasks ───────────────────────────────────────────────────────────────

@task(log_prints=True, retries=3, retry_delay_seconds=10)
def fetch_games(updated_after: str) -> list[dict]:
    """
    Core fact table source. Fetched incrementally — only games updated
    since the last successful run. updated_before is always tomorrow to
    avoid missing records updated late in the day due to timezone drift.
    Release date is preserved as a field and used later in dbt for analysis.
    """
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"Fetching games updated between {updated_after} and {tomorrow}...")
    games = fetch_all_pages(
        "games",
        params={
            "ordering": "-updated",
            "updated": f"{updated_after},{tomorrow}",
        }
    )
    print(f"Fetched {len(games)} games")
    return games


@task(log_prints=True, retries=3, retry_delay_seconds=10)
def fetch_genres() -> list[dict]:
    """Lookup table. Links games to genres for genre-level trend analysis."""
    print("Fetching genres...")
    genres = fetch_all_pages("genres")
    print(f"Fetched {len(genres)} genres")
    return genres


@task(log_prints=True, retries=3, retry_delay_seconds=10)
def fetch_platforms() -> list[dict]:
    """Lookup table. Tells you where games are being played."""
    print("Fetching platforms...")
    platforms = fetch_all_pages("platforms")
    print(f"Fetched {len(platforms)} platforms")
    return platforms


@task(log_prints=True, retries=3, retry_delay_seconds=10)
def fetch_publishers() -> list[dict]:
    """Lookup table. Enables publisher-level analysis of portfolio momentum."""
    print("Fetching publishers...")
    publishers = fetch_all_pages("publishers")
    print(f"Fetched {len(publishers)} publishers")
    return publishers


@task(log_prints=True, retries=3, retry_delay_seconds=10)
def fetch_tags() -> list[dict]:
    """
    Lookup table. Tags are richer than genres for clustering games by theme
    (e.g. 'open-world', 'roguelike', 'co-op') — useful for spotting
    rising trends before they show up in genre-level data.
    """
    print("Fetching tags...")
    tags = fetch_all_pages("tags")
    print(f"Fetched {len(tags)} tags")
    return tags

# ── upload task ───────────────────────────────────────────────────────────────

@task(log_prints=True, retries=3, retry_delay_seconds=10)
def upload_to_gcs(data: list[dict], entity: str, incremental: bool = False) -> None:
    """
    Uploads a list of records as newline-delimited JSON to GCS.

    Two path patterns:
      - Incremental (games): raw/games/updated_date=YYYY-MM-DD/games.ndjson
      - Snapshot (lookups):  raw/genres/snapshot_date=YYYY-MM-DD/genres.ndjson

    Nothing ever gets overwritten — each run lands in its own dated folder.
    """
    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET_NAME)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    partition_key = "updated_date" if incremental else "snapshot_date"
    blob_path = f"raw/{entity}/{partition_key}={date_str}/{entity}.ndjson"

    ndjson = "\n".join(json.dumps(record) for record in data)
    blob = bucket.blob(blob_path)
    blob.upload_from_string(ndjson, content_type="application/json")

    print(f"Uploaded {len(data)} records to gs://{GCS_BUCKET_NAME}/{blob_path}")

# ── main flow ─────────────────────────────────────────────────────────────────

@flow(name="extract_rawg")
def extract_rawg() -> None:
    """
    Extracts all reference and fact data from RAWG API and lands it
    as raw NDJSON files in GCS. This is the bronze landing step —
    no transformations, faithful copy of the API response.

    Games are fetched incrementally based on the last successful run date
    stored in GCS state. If no state exists, a full backfill runs from
    BACKFILL_START. Lookup tables are fully snapshotted every run.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # read state — determines how far back to fetch games
    updated_after = read_last_run_date()

    # incremental — only games changed since last run
    games = fetch_games(updated_after)
    upload_to_gcs(games, "games", incremental=True)

    # full snapshots — small lookup tables, always pull everything
    genres = fetch_genres()
    platforms = fetch_platforms()
    publishers = fetch_publishers()
    tags = fetch_tags()

    upload_to_gcs(genres, "genres")
    upload_to_gcs(platforms, "platforms")
    upload_to_gcs(publishers, "publishers")
    upload_to_gcs(tags, "tags")

    # only write state after everything succeeded
    write_last_run_date(today)


if __name__ == "__main__":
    extract_rawg()




