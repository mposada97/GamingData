import os
import json
import requests
from datetime import datetime, timedelta, timezone
from google.cloud import storage
from prefect import flow, task
from dateutil.relativedelta import relativedelta
import time


RAWG_BASE_URL = "https://api.rawg.io/api"
RAWG_API_KEY = os.getenv("RAWG_API_KEY")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")
STATE_BLOB_PATH = "raw/state/last_run.json"
BACKFILL_START = "2020-01-01" #"1999-01-01"


# ── API client (used to get data from any rawg endpoint) ────────────────────────────────────────────────────────────────
def fetch_all_pages(endpoint: str, params: dict[str, any] = {}) -> list[dict]:
    base_params = {"key": RAWG_API_KEY, "page_size": 250, "page": 1}
    results = []
    if params:
        base_params.update(params)

    url = f"{RAWG_BASE_URL}/{endpoint}"

    while url:
        for attempt in range(3):
            try:
                response = requests.get(url, params=base_params)
                if response.status_code in (502, 503, 520): #catch pagination errors and retry call
                    print(f"Server error {response.status_code}, retrying in 10s... ({attempt + 1}/3)")
                    time.sleep(10)
                    continue
                break
            except requests.exceptions.SSLError:
                print(f"SSL error, retrying in 10s... ({attempt + 1}/3)")
                time.sleep(10)
                continue
        if response.status_code == 404 and len(results) > 0:
            print(f"Hit pagination limit at {len(results)} results — stopping.")
            break
        response.raise_for_status()
        data = response.json()
        results.extend(data.get("results", []))
        url = data.get("next")
        base_params = {}
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

@task(log_prints=True)
def fetch_games(updated_after: str) -> list[dict]:
    """
    Core fact table source. Fetched incrementally — only games updated
    since the last successful run. updated_before is always tomorrow to
    avoid missing records updated late in the day due to timezone drift.
    Release date is preserved as a field and used later in dbt for analysis.
    """

    #is backfill is added because with updated date we hit incremental limits easily even in monthly chunks
    # updated date is used as param after inital load
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    is_backfill = updated_after == BACKFILL_START

    if is_backfill:
        print(f"Backfill mode — fetching all games by release date")
        filter_key = "dates"
        start = datetime.strptime(BACKFILL_START, "%Y-%m-%d")
    else:
        print(f"Incremental mode — fetching games updated since {updated_after}")
        filter_key = "updated"
        start = datetime.strptime(updated_after, "%Y-%m-%d")

    end = datetime.strptime(tomorrow, "%Y-%m-%d")


    #build a list of tuples with start and end date, a single call cant handle all data, api is capped at 10k rows
    chunks = []
    current = start
    while current < end:
        chunk_end = (current + relativedelta(months=1)) - timedelta(days=1)
        chunks.append((current.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")))
        current = current + relativedelta(months=1)

    total = 0
    for chunk_start, chunk_end in chunks:
        print(f"  Chunk: {chunk_start} → {chunk_end}")
        games = fetch_all_pages(
            "games",
            params={
                "ordering": "-released" if is_backfill else "-updated",
                filter_key: f"{chunk_start},{chunk_end}",
            }
        )
        print(f"  Got {len(games)} games")
        if games:
            upload_to_gcs(games, "games", incremental=True)
            total += len(games)

    print(f"Fetched {total} games")
    return None


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
      - Incremental (games): raw/games/updated_date=YYYY-MM-DD/games_timestamp.ndjson
      - Snapshot (lookups):  raw/genres/snapshot_date=YYYY-MM-DD/genres.ndjson

    
    """
    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET_NAME)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    partition_key = "run_date" if incremental else "snapshot_date"
    if incremental:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
        blob_path = f"raw/{entity}/{partition_key}={date_str}/{entity}_{timestamp}.ndjson"
    else:
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
    #upload_to_gcs(games, "games", incremental=True) this is being done by chunks in fetch games

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




