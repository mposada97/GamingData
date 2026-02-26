import os
import json
import requests
from datetime import datetime
from google.cloud import storage
from prefect import flow, task

RAWG_BASE_URL = "https://api.rawg.io/api"
RAWG_API_KEY = os.getenv("RAWG_API_KEY")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")

def fetch_all_pages(endpoint: str, params: dict[str, any] = {}) -> list[dict]:
    base_params = {"key": RAWG_API_KEY, "page_size": 40, "page": 1}
    if params:
        base_params.update(params)
    url = f"{RAWG_BASE_URL}/{endpoint}"
    results = []
    while url:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        results.extend(data.get("results", []))
        url = data.get("next")      # RAWG returns the next page URL directly
        params = {}  
    return results 