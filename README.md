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

(Check out the image in the introduction)

The pipeline runs as a single Prefect flow with four steps:

1. **Extract**: Hits the RAWG API with pagination and monthly chunking, uploads raw NDJSON files to GCS. Games are fetched incrementally using an updated-date watermark stored in a state file on GCS. Lookups are fully snapshotted. This makes GCS a safety net, if the logic changes or we want to build any new tables, the historical raw data lives here.
2. **Load to Bronze (WAP)**: Loads NDJSON from GCS into staging tables in BigQuery, runs audits (row count, null checks, schema validation), and promotes to final bronze tables only if checks pass, staging tables are deleted in this step after writing to bronze. If checks fail, staging is dropped and bronze is untouched. Game table is written incrementally, other tables are overwritten.
3. **dbt Silver**: Builds dimension tables, bridge tables, and a periodic snapshot fact table. Staging models (`stg_*`) do the real transformation work (deduplication, type casting, unnesting arrays). Tests run on staging models, and final tables only build if upstream tests pass. Game fact and dim tables, and all the bridge tables are written incrementally, other dim tables are overwritten. 
4. **dbt Gold**: Builds analytical tables for the dashboard layer. Release trends by genre, release trends by platform, trending tags. At this moment tables are overwritten in every run, incremental load was explored but the latest months data look at the previous month to compute changes (using the LAG function in sql), insert overwrite wouldn't allow this in dbt.

# Data Modeling

## Silver Layer

Silver is a dimensional model centered on `dim_games` with bridge tables connecting games to genres, platforms, and tags. There is also a periodic snapshot fact table (`fct_game_snapshots`) that preserves the historical state of game metrics across load dates.

<img width="1880" height="1944" alt="image" src="https://github.com/user-attachments/assets/dfecfaf4-271f-414f-9e5e-83fe4e7f8637" />


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

<details>
<summary>Full pipeline run output (click to expand)</summary>

20:31:37.811 | INFO    | prefect - Starting temporary server on http://127.0.0.1:8400
See https://docs.prefect.io/v3/concepts/server#how-to-guides for more information on running a dedicated Prefect server.
20:31:40.900 | INFO    | Flow run 'real-poodle' - Beginning flow run 'real-poodle' for flow 'gaming_data_pipeline'
20:31:40.903 | INFO    | Flow run 'real-poodle' - Step 1: Extract RAWG to GCS
20:31:40.950 | INFO    | Flow run 'sassy-catfish' - Beginning subflow run 'sassy-catfish' for flow 'extract_rawg'
20:31:41.664 | INFO    | Task run 'read_last_run_date-b11' - Last successful run was: 2026-04-13
20:31:41.668 | INFO    | Task run 'read_last_run_date-b11' - Finished in state Completed()
20:31:41.673 | INFO    | Task run 'fetch_games-270' - Incremental mode — fetching games updated since 2026-04-13
20:31:41.675 | INFO    | Task run 'fetch_games-270' -   Chunk: 2026-04-13 → 2026-05-12
20:32:20.454 | INFO    | Task run 'fetch_games-270' -   Got 1556 games
20:32:25.255 | INFO    | Task run 'upload_to_gcs-198' - Uploaded 1556 records to gs://gamingdata-487900-bucket/raw/games/run_date=2026-04-19/games_2026-04-19T203222.ndjson
20:32:25.261 | INFO    | Task run 'upload_to_gcs-198' - Finished in state Completed()
20:32:25.263 | INFO    | Task run 'fetch_games-270' - Fetched 1556 games
20:32:25.265 | INFO    | Task run 'fetch_games-270' - Finished in state Completed()
20:32:25.283 | INFO    | Task run 'fetch_genres-8d1' - Fetching genres...
20:32:32.220 | INFO    | Task run 'fetch_genres-8d1' - Fetched 19 genres
20:32:32.224 | INFO    | Task run 'fetch_genres-8d1' - Finished in state Completed()
20:32:32.228 | INFO    | Task run 'fetch_platforms-fc2' - Fetching platforms...
20:32:34.707 | INFO    | Task run 'fetch_platforms-fc2' - Fetched 51 platforms
20:32:34.711 | INFO    | Task run 'fetch_platforms-fc2' - Finished in state Completed()
20:32:34.714 | INFO    | Task run 'fetch_publishers-aa2' - Fetching publishers...
21:06:08.365 | INFO    | Task run 'fetch_publishers-aa2' - Fetched 90267 publishers
21:06:08.489 | INFO    | Task run 'fetch_publishers-aa2' - Finished in state Completed()
21:06:08.491 | INFO    | Task run 'fetch_tags-f09' - Fetching tags...
21:09:51.148 | INFO    | Task run 'fetch_tags-f09' - Fetched 9727 tags
21:09:51.186 | INFO    | Task run 'fetch_tags-f09' - Finished in state Completed()
21:09:51.832 | INFO    | Task run 'upload_to_gcs-0c0' - Uploaded 19 records to gs://gamingdata-487900-bucket/raw/genres/snapshot_date=2026-04-19/genres.ndjson
21:09:51.837 | INFO    | Task run 'upload_to_gcs-0c0' - Finished in state Completed()
21:09:52.511 | INFO    | Task run 'upload_to_gcs-eb4' - Uploaded 51 records to gs://gamingdata-487900-bucket/raw/platforms/snapshot_date=2026-04-19/platforms.ndjson
21:09:52.515 | INFO    | Task run 'upload_to_gcs-eb4' - Finished in state Completed()
21:10:11.167 | INFO    | Task run 'upload_to_gcs-b14' - Uploaded 90267 records to gs://gamingdata-487900-bucket/raw/publishers/snapshot_date=2026-04-19/publishers.ndjson
21:10:11.174 | INFO    | Task run 'upload_to_gcs-b14' - Finished in state Completed()
21:10:14.637 | INFO    | Task run 'upload_to_gcs-377' - Uploaded 9727 records to gs://gamingdata-487900-bucket/raw/tags/snapshot_date=2026-04-19/tags.ndjson
21:10:14.641 | INFO    | Task run 'upload_to_gcs-377' - Finished in state Completed()
21:10:15.552 | INFO    | Task run 'write_last_run_date-969' - State updated — last successful run set to: 2026-04-19
21:10:15.558 | INFO    | Task run 'write_last_run_date-969' - Finished in state Completed()
21:10:15.636 | INFO    | Flow run 'sassy-catfish' - Finished in state Completed()
21:10:15.637 | INFO    | Flow run 'real-poodle' - Step 2: Load GCS to bronze BigQuery
21:10:15.665 | INFO    | Flow run 'helpful-crane' - Beginning subflow run 'helpful-crane' for flow 'load_to_bronze'
21:10:25.418 | INFO    | Task run 'write_to_staging-51b' - Loaded to staging: games for 2026-04-13
21:10:25.423 | INFO    | Task run 'write_to_staging-51b' - Finished in state Completed()
21:10:26.610 | INFO    | Task run 'audit_staging-64b' - Row count Test passed: games staging has 3248 rows
21:10:27.811 | INFO    | Task run 'audit_staging-64b' - No Null id's in games staging table. ID test passed.
21:10:27.816 | INFO    | Task run 'audit_staging-64b' - Finished in state Completed()
21:10:35.930 | INFO    | Task run 'publish_to_bronze-0a3' - Published games to bronze
21:10:36.084 | INFO    | Task run 'publish_to_bronze-0a3' - Dropped stg_games
21:10:36.088 | INFO    | Task run 'publish_to_bronze-0a3' - Finished in state Completed()
21:11:01.103 | INFO    | Task run 'write_to_staging-f12' - Loaded to staging: games for 2026-04-19
21:11:01.108 | INFO    | Task run 'write_to_staging-f12' - Finished in state Completed()
21:11:02.175 | INFO    | Task run 'audit_staging-b8d' - Row count Test passed: games staging has 1556 rows
21:11:03.441 | INFO    | Task run 'audit_staging-b8d' - No Null id's in games staging table. ID test passed.
21:11:03.445 | INFO    | Task run 'audit_staging-b8d' - Finished in state Completed()
21:11:09.590 | INFO    | Task run 'publish_to_bronze-e94' - Published games to bronze
21:11:09.826 | INFO    | Task run 'publish_to_bronze-e94' - Dropped stg_games
21:11:09.831 | INFO    | Task run 'publish_to_bronze-e94' - Finished in state Completed()
21:11:22.392 | INFO    | Task run 'write_to_staging-300' - Loaded to staging: genres for 2026-04-19
21:11:22.396 | INFO    | Task run 'write_to_staging-300' - Finished in state Completed()
21:11:23.346 | INFO    | Task run 'audit_staging-ff3' - Row count Test passed: genres staging has 19 rows
21:11:24.462 | INFO    | Task run 'audit_staging-ff3' - No Null id's in genres staging table. ID test passed.
21:11:24.466 | INFO    | Task run 'audit_staging-ff3' - Finished in state Completed()
21:11:32.573 | INFO    | Task run 'publish_to_bronze-82b' - Published genres to bronze
21:11:32.740 | INFO    | Task run 'publish_to_bronze-82b' - Dropped stg_genres
21:11:32.745 | INFO    | Task run 'publish_to_bronze-82b' - Finished in state Completed()
21:11:39.668 | INFO    | Task run 'write_to_staging-b88' - Loaded to staging: platforms for 2026-04-19
21:11:39.672 | INFO    | Task run 'write_to_staging-b88' - Finished in state Completed()
21:11:40.825 | INFO    | Task run 'audit_staging-9b9' - Row count Test passed: platforms staging has 51 rows
21:11:41.747 | INFO    | Task run 'audit_staging-9b9' - No Null id's in platforms staging table. ID test passed.
21:11:41.752 | INFO    | Task run 'audit_staging-9b9' - Finished in state Completed()
21:11:47.005 | INFO    | Task run 'publish_to_bronze-273' - Published platforms to bronze
21:11:47.309 | INFO    | Task run 'publish_to_bronze-273' - Dropped stg_platforms
21:11:47.313 | INFO    | Task run 'publish_to_bronze-273' - Finished in state Completed()
21:11:59.808 | INFO    | Task run 'write_to_staging-733' - Loaded to staging: publishers for 2026-04-19
21:11:59.814 | INFO    | Task run 'write_to_staging-733' - Finished in state Completed()
21:12:00.789 | INFO    | Task run 'audit_staging-908' - Row count Test passed: publishers staging has 90267 rows
21:12:01.897 | INFO    | Task run 'audit_staging-908' - No Null id's in publishers staging table. ID test passed.
21:12:01.902 | INFO    | Task run 'audit_staging-908' - Finished in state Completed()
21:12:09.591 | INFO    | Task run 'publish_to_bronze-dae' - Published publishers to bronze
21:12:09.727 | INFO    | Task run 'publish_to_bronze-dae' - Dropped stg_publishers
21:12:09.730 | INFO    | Task run 'publish_to_bronze-dae' - Finished in state Completed()
21:12:15.993 | INFO    | Task run 'write_to_staging-786' - Loaded to staging: tags for 2026-04-19
21:12:15.997 | INFO    | Task run 'write_to_staging-786' - Finished in state Completed()
21:12:17.093 | INFO    | Task run 'audit_staging-cf8' - Row count Test passed: tags staging has 9727 rows
21:12:17.966 | INFO    | Task run 'audit_staging-cf8' - No Null id's in tags staging table. ID test passed.
21:12:17.971 | INFO    | Task run 'audit_staging-cf8' - Finished in state Completed()
21:12:23.306 | INFO    | Task run 'publish_to_bronze-720' - Published tags to bronze
21:12:23.491 | INFO    | Task run 'publish_to_bronze-720' - Dropped stg_tags
21:12:23.497 | INFO    | Task run 'publish_to_bronze-720' - Finished in state Completed()
21:12:23.531 | INFO    | Flow run 'helpful-crane' - Finished in state Completed()
21:12:23.532 | INFO    | Flow run 'real-poodle' - Step 3: Build silver layer
21:12:23.534 | INFO    | Task run 'run_dbt_build-2ea' - Running: dbt build --project-dir /code/gaming_data_dbt -s path:models/rawg/silver
21:13:49.266 | INFO    | Task run 'run_dbt_build-2ea' - 21:12:24  Running with dbt=1.11.6
21:12:29  Registered adapter: bigquery=1.11.0
21:12:30  Found 20 models, 43 data tests, 5 sources, 539 macros
21:12:30  
21:12:30  Concurrency: 4 threads (target='dev')
21:12:30  
21:12:31  1 of 51 START sql incremental model silver.stg_dim_games ....................... [RUN]
21:12:31  2 of 51 START sql table model silver.stg_dim_genres ............................ [RUN]
21:12:31  3 of 51 START sql table model silver.stg_dim_platforms ......................... [RUN]
21:12:31  4 of 51 START sql table model silver.stg_dim_tags .............................. [RUN]
21:12:34  4 of 51 OK created sql table model silver.stg_dim_tags ......................... [CREATE TABLE (9.5k rows, 3.8 MiB processed) in 3.32s]
21:12:34  3 of 51 OK created sql table model silver.stg_dim_platforms .................... [CREATE TABLE (51.0 rows, 19.2 KiB processed) in 3.33s]
21:12:34  5 of 51 START sql incremental model silver.stg_fct_game_snapshots .............. [RUN]
21:12:34  6 of 51 START test not_null_stg_dim_tags_name .................................. [RUN]
21:12:34  2 of 51 OK created sql table model silver.stg_dim_genres ....................... [CREATE TABLE (19.0 rows, 7.0 KiB processed) in 3.56s]
21:12:34  7 of 51 START test not_null_stg_dim_tags_slug .................................. [RUN]
21:12:36  6 of 51 PASS not_null_stg_dim_tags_name ........................................ [PASS in 1.62s]
21:12:36  8 of 51 START test not_null_stg_dim_tags_tag_id ................................ [RUN]
21:12:36  7 of 51 PASS not_null_stg_dim_tags_slug ........................................ [PASS in 1.47s]
21:12:36  9 of 51 START test unique_stg_dim_tags_tag_id .................................. [RUN]
21:12:38  9 of 51 PASS unique_stg_dim_tags_tag_id ........................................ [PASS in 1.53s]
21:12:38  10 of 51 START test not_null_stg_dim_platforms_name ............................ [RUN]
21:12:38  8 of 51 PASS not_null_stg_dim_tags_tag_id ...................................... [PASS in 1.97s]
21:12:38  11 of 51 START test not_null_stg_dim_platforms_platform_id ..................... [RUN]
21:12:39  10 of 51 PASS not_null_stg_dim_platforms_name .................................. [PASS in 1.37s]
21:12:39  12 of 51 START test not_null_stg_dim_platforms_slug ............................ [RUN]
21:12:40  11 of 51 PASS not_null_stg_dim_platforms_platform_id ........................... [PASS in 1.67s]
21:12:40  13 of 51 START test unique_stg_dim_platforms_platform_id ....................... [RUN]
21:12:41  12 of 51 PASS not_null_stg_dim_platforms_slug .................................. [PASS in 1.66s]
21:12:41  14 of 51 START test not_null_stg_dim_genres_genre_id ........................... [RUN]
21:12:41  13 of 51 PASS unique_stg_dim_platforms_platform_id ............................. [PASS in 1.46s]
21:12:41  15 of 51 START test not_null_stg_dim_genres_name ............................... [RUN]
21:12:42  14 of 51 PASS not_null_stg_dim_genres_genre_id ................................. [PASS in 1.58s]
21:12:42  16 of 51 START test not_null_stg_dim_genres_slug ............................... [RUN]
21:12:42  15 of 51 PASS not_null_stg_dim_genres_name ..................................... [PASS in 1.45s]
21:12:42  17 of 51 START test unique_stg_dim_genres_genre_id ............................. [RUN]
21:12:44  16 of 51 PASS not_null_stg_dim_genres_slug ..................................... [PASS in 1.47s]
21:12:44  18 of 51 START sql table model silver.dim_tags ................................. [RUN]
21:12:44  17 of 51 PASS unique_stg_dim_genres_genre_id ................................... [PASS in 1.47s]
21:12:44  19 of 51 START sql table model silver.dim_platforms ............................ [RUN]
21:12:47  18 of 51 OK created sql table model silver.dim_tags ............................ [CREATE TABLE (9.5k rows, 1.1 MiB processed) in 3.09s]
21:12:47  20 of 51 START sql table model silver.dim_genres ............................... [RUN]
21:12:47  19 of 51 OK created sql table model silver.dim_platforms ....................... [CREATE TABLE (51.0 rows, 5.8 KiB processed) in 2.89s]
21:12:49  5 of 51 OK created sql incremental model silver.stg_fct_game_snapshots ......... [SCRIPT (71.6 MiB processed) in 15.04s]
21:12:49  21 of 51 START test not_null_stg_fct_game_snapshots_game_id .................... [RUN]
21:12:49  22 of 51 START test not_null_stg_fct_game_snapshots_load_date .................. [RUN]
21:12:50  20 of 51 OK created sql table model silver.dim_genres .......................... [CREATE TABLE (19.0 rows, 2.1 KiB processed) in 2.95s]
21:12:51  21 of 51 PASS not_null_stg_fct_game_snapshots_game_id .......................... [PASS in 1.48s]
21:12:51  22 of 51 PASS not_null_stg_fct_game_snapshots_load_date ........................ [PASS in 1.49s]
21:12:51  23 of 51 START sql incremental model silver.fct_game_snapshots ................. [RUN]
21:12:59  23 of 51 OK created sql incremental model silver.fct_game_snapshots ............ [SCRIPT (6.0 MiB processed) in 8.18s]
21:13:24  1 of 51 OK created sql incremental model silver.stg_dim_games .................. [MERGE (1.6k rows, 1.6 GiB processed) in 52.74s]
21:13:24  24 of 51 START test not_null_stg_dim_games_game_id ............................. [RUN]
21:13:24  25 of 51 START test not_null_stg_dim_games_load_date ........................... [RUN]
21:13:24  26 of 51 START test not_null_stg_dim_games_name ................................ [RUN]
21:13:24  27 of 51 START test not_null_stg_dim_games_slug ................................ [RUN]
21:13:26  27 of 51 PASS not_null_stg_dim_games_slug ...................................... [PASS in 1.95s]
21:13:26  28 of 51 START test not_null_stg_dim_games_updated ............................. [RUN]
21:13:26  26 of 51 PASS not_null_stg_dim_games_name ...................................... [PASS in 2.07s]
21:13:26  29 of 51 START test unique_stg_dim_games_game_id ............................... [RUN]
21:13:26  25 of 51 PASS not_null_stg_dim_games_load_date ................................. [PASS in 2.12s]
21:13:26  24 of 51 PASS not_null_stg_dim_games_game_id ................................... [PASS in 2.14s]
21:13:28  28 of 51 PASS not_null_stg_dim_games_updated ................................... [PASS in 1.88s]
21:13:28  29 of 51 PASS unique_stg_dim_games_game_id ..................................... [PASS in 1.83s]
21:13:28  30 of 51 START sql incremental model silver.dim_games .......................... [RUN]
21:13:28  31 of 51 START sql incremental model silver.stg_brdg_game_genres ............... [RUN]
21:13:28  32 of 51 START sql incremental model silver.stg_brdg_game_platforms ............ [RUN]
21:13:28  33 of 51 START sql incremental model silver.stg_brdg_game_tags ................. [RUN]
21:13:33  31 of 51 OK created sql incremental model silver.stg_brdg_game_genres .......... [MERGE (3.1k rows, 36.1 MiB processed) in 5.63s]
21:13:33  34 of 51 START test not_null_stg_brdg_game_genres_game_id ...................... [RUN]
21:13:34  33 of 51 OK created sql incremental model silver.stg_brdg_game_tags ............ [MERGE (28.2k rows, 160.5 MiB processed) in 6.54s]
21:13:34  35 of 51 START test not_null_stg_brdg_game_genres_genre_id ..................... [RUN]
21:13:35  34 of 51 PASS not_null_stg_brdg_game_genres_game_id ............................ [PASS in 1.37s]
21:13:35  36 of 51 START test not_null_stg_brdg_game_genres_load_date .................... [RUN]
21:13:36  32 of 51 OK created sql incremental model silver.stg_brdg_game_platforms ....... [MERGE (4.6k rows, 38.5 MiB processed) in 7.95s]
21:13:36  37 of 51 START test not_null_stg_brdg_game_tags_game_id ........................ [RUN]
21:13:36  35 of 51 PASS not_null_stg_brdg_game_genres_genre_id ........................... [PASS in 1.53s]
21:13:36  38 of 51 START test not_null_stg_brdg_game_tags_load_date ...................... [RUN]
21:13:36  36 of 51 PASS not_null_stg_brdg_game_genres_load_date .......................... [PASS in 1.41s]
21:13:36  39 of 51 START test not_null_stg_brdg_game_tags_tag_id ......................... [RUN]
21:13:37  38 of 51 PASS not_null_stg_brdg_game_tags_load_date ............................ [PASS in 1.60s]
21:13:37  40 of 51 START test not_null_stg_brdg_game_platforms_game_id ................... [RUN]
21:13:38  39 of 51 PASS not_null_stg_brdg_game_tags_tag_id ............................... [PASS in 1.51s]
21:13:38  41 of 51 START test not_null_stg_brdg_game_platforms_load_date ................. [RUN]
21:13:38  37 of 51 PASS not_null_stg_brdg_game_tags_game_id .............................. [PASS in 2.02s]
21:13:38  42 of 51 START test not_null_stg_brdg_game_platforms_platform_id ............... [RUN]
21:13:39  40 of 51 PASS not_null_stg_brdg_game_platforms_game_id ......................... [PASS in 1.47s]
21:13:39  43 of 51 START sql incremental model silver.brdg_game_genres ................... [RUN]
21:13:39  42 of 51 PASS not_null_stg_brdg_game_platforms_platform_id ..................... [PASS in 1.52s]
21:13:39  44 of 51 START sql incremental model silver.brdg_game_tags ..................... [RUN]
21:13:40  41 of 51 PASS not_null_stg_brdg_game_platforms_load_date ....................... [PASS in 2.19s]
21:13:40  45 of 51 START sql incremental model silver.brdg_game_platforms ................ [RUN]
21:13:41  30 of 51 OK created sql incremental model silver.dim_games ..................... [MERGE (1.6k rows, 294.3 MiB processed) in 13.17s]
21:13:41  46 of 51 START test relationships_fct_game_snapshots_game_id__game_id__ref_dim_games_  [RUN]
21:13:43  46 of 51 PASS relationships_fct_game_snapshots_game_id__game_id__ref_dim_games_  [PASS in 2.50s]
21:13:44  43 of 51 OK created sql incremental model silver.brdg_game_genres .............. [MERGE (3.1k rows, 41.6 MiB processed) in 5.46s]
21:13:44  47 of 51 START test relationships_brdg_game_genres_game_id__game_id__ref_dim_games_  [RUN]
21:13:44  48 of 51 START test relationships_brdg_game_genres_genre_id__genre_id__ref_dim_genres_  [RUN]
21:13:45  45 of 51 OK created sql incremental model silver.brdg_game_platforms ........... [MERGE (4.6k rows, 45.5 MiB processed) in 4.83s]
21:13:45  44 of 51 OK created sql incremental model silver.brdg_game_tags ................ [MERGE (28.2k rows, 234.9 MiB processed) in 5.44s]
21:13:45  49 of 51 START test relationships_brdg_game_platforms_game_id__game_id__ref_dim_games_  [RUN]
21:13:45  50 of 51 START test relationships_brdg_game_platforms_platform_id__platform_id__ref_dim_platforms_  [RUN]
21:13:46  48 of 51 PASS relationships_brdg_game_genres_genre_id__genre_id__ref_dim_genres_  [PASS in 1.56s]
21:13:46  51 of 51 START test relationships_brdg_game_tags_game_id__game_id__ref_dim_games_  [RUN]
21:13:46  50 of 51 PASS relationships_brdg_game_platforms_platform_id__platform_id__ref_dim_platforms_  [PASS in 1.24s]
21:13:46  47 of 51 PASS relationships_brdg_game_genres_game_id__game_id__ref_dim_games_ .. [PASS in 2.17s]
21:13:46  49 of 51 PASS relationships_brdg_game_platforms_game_id__game_id__ref_dim_games_  [PASS in 1.86s]
21:13:48  51 of 51 PASS relationships_brdg_game_tags_game_id__game_id__ref_dim_games_ .... [PASS in 2.01s]
21:13:48  
21:13:48  Finished running 10 incremental models, 6 table models, 35 data tests in 0 hours 1 minutes and 18.25 seconds (78.25s).
21:13:48  
21:13:48  Completed successfully
21:13:48  
21:13:48  Done. PASS=51 WARN=0 ERROR=0 SKIP=0 NO-OP=0 TOTAL=51

</details>

The master pipeline is a single Prefect flow (`flows/master_pipeline.py`) that chains extract, load, silver, and gold in sequence (above you can see the logs for a full run, I will add a DAG screnshot when uploaded to prefect cloud). If any step fails, subsequent steps don't run. dbt is invoked via subprocess from within the flow, and `dbt build` runs models and tests together so that test failures block downstream models.

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

Building this project forced me to think through a lot of decisions that I hadn't dealt with before. The biggest one was deciding not to use SCD2 for the games dimension. My first instinct was to implement it because thats what you learn in every data modeling course, but when I thought about what it would actually do to the bridge tables (surrogate keys everywhere, every join becomes more complex, every query needs an is_current filter) I realized it was adding complexity without solving a real problem. Instead I kept dim_games as current-state and added fct_game_snapshots as a periodic snapshot fact table to capture historical metrics. Same outcome, cleaner model, no surrogate key confusion.

The WAP pattern was another big one. In my previous project I wrote in the README that I should have used it and would implement it next time. I actually did it here. Bronze uses a proper Write-Audit-Publish flow with staging tables that get promoted only if checks pass. For silver I used dbt's DAG to enforce the same idea, staging models carry the tests and final tables only build if upstream tests pass. Its not a perfect WAP implementation since the stg tables persist, but it achieves the same goal of keeping bad data out of the tables that analysts query.

I also learned a lot about incremental modeling in dbt, specifically the difference between merge and insert_overwrite strategies. Merge works for mutable entity rows where you want to update a specific game by its ID. Insert_overwrite works for time-partitioned facts where each partition is a complete unit and you want to replace it cleanly. I tried to make the gold tables incremental too but ran into the issue that window functions like LAG need the previous partition in the same batch to compute month-over-month changes, which insert_overwrite doesnt give you. For small aggregation tables full refresh was the right call.

The data source itself was a learning experience. RAWG is community-sourced which means recent releases are underrepresented and metrics like Metacritic scores are sparse for anything in the last year or two. This made me realize that for the business case to really work (telling executives where attention is right now) you cant rely on a single historical catalog.

One of the hardest things was making the pipeline idempotent. I spent a lot of time trying to guarantee that every layer would produce the same result no matter when or how many times you run it. I eventually realized that what matters most is idempotency in silver and gold since those are the layers exposed to analysts and BI tools. Bronze handles this through WAP and upsert semantics, and the raw landing zone in GCS is append-only by design so historical data is never lost. The extract itself is cursor-based (game pulls are based on a last state date that I store) and not perfectly replayable, but that's fine because the downstream layers are built to handle whatever lands in bronze.

### Next steps

- **Twitch integration**: Adding Twitch as a real-time data source is the natural next step. RAWG tells you where attention has been, Twitch tells you where it is right now. Stream sessions, viewer counts, and chat activity would feed into a fct_stream_sessions fact table that joins to the same dim_games through the existing bridges. This is already planned in the project structure with room for a models/twitch/ folder alongside models/rawg/.
- **Explore a different primary source**: RAWG's recency gap is a real limitation. Steam's API or IGDB might provide more complete coverage of recent releases and player activity. The pipeline architecture wouldnt change much, just the extract layer and the bronze schema.
- **Cloud Run deployment**: The pipeline runs end to end in Docker locally but hasnt been deployed to Cloud Run yet. The Dockerfile, Terraform, and Prefect flow are all ready for it, its just a matter of pushing the image to Artifact Registry and configuring the work pool.
- **Scheduling**: Once deployed, the pipeline would run weekly on Monday mornings via a Prefect cron schedule. The incremental extract and load steps make this efficient since only new data gets processed each run.
