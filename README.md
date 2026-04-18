# GamingData: Where's the Attention?

The idea behind this project is to build an end-to-end data pipeline that tracks where player attention is going in the gaming industry. The target audience is gaming company executives who want to understand which genres, platforms, and themes are gaining traction before they peak. The pipeline ingests data from the RAWG video game database API, processes it through a medallion architecture (bronze, silver, gold), and surfaces the results in a Looker Studio dashboard.

<img width="2200" height="1440" alt="image" src="https://github.com/user-attachments/assets/391463b2-befe-4f68-96b2-a78d45bfa836" />


# Scope and Business Case

The gaming industry produces thousands of releases every year across dozens of platforms and genres. Executives making decisions about what to fund, what to acquire, or where to position their portfolio need to see the landscape clearly. This project answers three questions:

- Where is the supply going? Which genres and platforms are getting more releases over time, and which are losing share.
- What themes are trending? Which gameplay mechanics, aesthetics, and tags are showing up most in recent releases.
- Where is player attention concentrated? Which genres are seeing the most update activity and engagement from the RAWG community.

The data comes from the RAWG API which provides a catalog of 745K+ games with metadata like genres, platforms, tags, ratings, and release dates. The extract is incremental, pulling games that have been updated since the last run. Lookup tables (genres, platforms, tags) are fully snapshotted every run.

Twitch streaming data is planned as a second source to complement RAWG's historical catalog with real-time viewer attention, but that is not included in this version of the project.

It is also important to mention that the dashboard included in the project is just a sample of what can be built with the tables generated in the gold layer, silver and gold layers are designed to be queried by analysts to answer more questions relevant to the business case.

### Known limitations

- RAWG is community-sourced, so recent releases (2025-2026) are underrepresented because games take time to be cataloged.
- Metacritic scores are sparse for recent releases because critic reviews take time to accumulate.
- The tags lookup table from RAWG is incomplete, many tags that appear on games don't exist in the tags endpoint. This is documented and handled in the schema tests.
- Publisher data couldn't be connected to games because the RAWG list endpoint doesn't embed publishers on game records. The publisher dimension exists in bronze but has no bridge table, so it wasn't used in silver or gold.

# Data Stack

- **Cloud**: GCP (BigQuery, GCS)
- **Orchestration**: Prefect
- **Transformations and tests**: dbt (dbt-bigquery)
- **Containerization**: Docker / OrbStack
- **Package management**: uv
- **Infrastructure**: Terraform
- **Data visualization**: Looker Studio
- **Language**: Python 3.12

# Architecture

<!-- TODO: Add architecture diagram image here showing: RAWG API → Extract (Python) → GCS (raw NDJSON) → Load with WAP (Python) → Bronze (BigQuery) → dbt silver → dbt gold → Looker Studio. Prefect orchestrates the whole thing. -->

The pipeline runs as a single Prefect flow with four steps:

1. **Extract**: Hits the RAWG API with pagination and monthly chunking, uploads raw NDJSON files to GCS. Games are fetched incrementally using an updated-date watermark stored in a state file on GCS. Lookups are fully snapshotted. This makes GCS a safety net, if the logic changes or we want to build any new tables, the historical raw data lives here.
2. **Load to Bronze (WAP)**: Loads NDJSON from GCS into staging tables in BigQuery, runs audits (row count, null checks, schema validation), and promotes to final bronze tables only if checks pass, staging tables are deleted in this step after writing to bronze. If checks fail, staging is dropped and bronze is untouched. Game table is written incrementally, other tables are overwritten.
3. **dbt Silver**: Builds dimension tables, bridge tables, and a periodic snapshot fact table. Staging models (`stg_*`) do the real transformation work (deduplication, type casting, unnesting arrays). Tests run on staging models, and final tables only build if upstream tests pass. Game fact and dim tables, and all the bridge tables are written incrementally, other dim tables are overwritten. 
4. **dbt Gold**: Builds analytical tables for the dashboard layer. Release trends by genre, release trends by platform, trending tags. At this moment tables are overwritten in every run, incremental load was explored but the latest months data look at the previous month to compute changes (using the LAG function in sql), insert overwrite wouldn't allow this in dbt.

# Data Modeling

## Silver Layer

Silver is a dimensional model centered on `dim_games` with bridge tables connecting games to genres, platforms, and tags. There is also a periodic snapshot fact table (`fct_game_snapshots`) that preserves the historical state of game metrics across load dates.

<!-- TODO: Add the silver ERD image here -->

### Dimensions

| Table | Grain | Source |
|---|---|---|
| dim_games | One row per game, current state | bronze.games, deduplicated by latest `updated` timestamp |
| dim_genres | One row per genre | bronze.genres, latest snapshot |
| dim_platforms | One row per platform | bronze.platforms, latest snapshot |
| dim_tags | One row per tag | bronze.tags, latest snapshot |

### Bridge Tables

| Table | Grain | Notes |
|---|---|---|
| brdg_game_genres | One row per (game, genre) | Unnested from dim_games |
| brdg_game_platforms | One row per (game, platform) | Unnested from dim_games |
| brdg_game_tags | One row per (game, tag) | Unnested from dim_games. No relationship test on tag_id because the tags lookup is incomplete. |

### Fact Table

| Table | Grain | Notes |
|---|---|---|
| fct_game_snapshots | One row per (game, load_date) | Periodic activity fact. Contains game metrics as of each load date. Only games with RAWG updates appear, this is not a full state snapshot of all games. |

## Gold Layer

| Table | Description |
|---|---|
| fct_releases_by_genre_monthly | Release volume, average rating, and share of monthly releases by genre. Includes month-over-month change and rank. |
| fct_releases_by_platform_monthly | Same structure as genre trends but grouped by platform. |
| fct_trending_tags_monthly | Top 50 tags per month by game count in new releases. Captures thematic and mechanical shifts. |
| fct_genre_activity_monthly | Genre activity per month based on RAWG update activity (load_date grain). Measures where community engagement is concentrated. |

# The Pipeline

<!-- TODO: Add a screenshot of the Prefect flow run or the master pipeline DAG here -->

The master pipeline is a single Prefect flow (`flows/master_pipeline.py`) that chains extract, load, silver, and gold in sequence. If any step fails, subsequent steps don't run. dbt is invoked via subprocess from within the flow, and `dbt build` runs models and tests together so that test failures block downstream models.

# Data Visualization

<img width="900" height="675" alt="image" src="https://github.com/user-attachments/assets/ac5c77e5-05ad-4f22-85f5-5c217a306954" />


[View the live dashboard](https://datastudio.google.com/reporting/202fe8f9-f845-42ef-8903-a103b462345f)

- The top chart shows a clear drop in cataloged releases starting around mid-2023. This is not necessarily a real decline in games being made, RAWG is community-sourced and recent releases take time to appear in the database. The further out you go the less complete the picture is.
- Metacritic ratings converge and flatten after 2024 because fewer recent games have enough critic reviews to produce a score. The data is most reliable in the 2021-2023 range.
- For executives looking at current trends, RAWG alone is not enough. The historical catalog is solid but the recency gap means you need a complementary real-time source like Twitch viewership or Steam player counts to get a full picture of where attention is right now. This is the motivation behind adding Twitch as a second data source in a future version.

# How to Run

### Prerequisites

- Python 3.12
- Docker / Docker Compose
- A GCP project with BigQuery and GCS enabled
- A RAWG API key (free at https://rawg.io/apidocs)
- uv installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Setup

1. Clone the repo:
```bash
git clone https://github.com/mposada97/GamingData.git
cd GamingData/pipeline
```

2. Create your `.env` file in `pipeline/` with the following variables:
```
RAWG_API_KEY=your_key_here
GCP_PROJECT_ID=your_project_id
GCS_BUCKET_NAME=your_bucket
BRONZE_DATASET=bronze
SILVER_DATASET=silver
GOLD_DATASET=gold
DBT_GOOGLE_CREDENTIALS=/code/keys/gcp_dbt.json
```

3. Add your GCP service account key JSONs to `pipeline/keys/`. You need two: one for orchestration (`gcp_prefect.json`) and one for dbt (`gcp_dbt.json`). Add `keys/` to `.gitignore`.

4. Build and run:
```bash
docker compose build
docker compose run pipeline bash
```

5. Run the full pipeline from inside the container:
```bash
python flows/master_pipeline.py
```

6. Or run dbt independently:
```bash
cd gaming_data_dbt
dbt build
```

### Terraform

Infrastructure is managed with Terraform. To provision:
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

This creates the GCS bucket, BigQuery datasets, Artifact Registry repository, and IAM bindings for the service accounts.

# Learnings and Next Steps

<!-- TODO: Write this section yourself. Some topics to cover:
- WAP pattern: you mentioned learning about it in your chess project README and wanting to use it in future projects. You actually implemented it here in bronze and used a test-gated DAG pattern in silver.
- The decision not to use SCD2 and why current-state dims + a snapshot fact table was the better call.
- Incremental modeling decisions: where you used merge vs insert_overwrite and why.
- What you would do differently (maybe the extract strategy, or adding Twitch sooner).
- Twitch integration as the next phase.
- Cloud Run deployment as the next infrastructure step.
-->
