{{ config(
    materialized='incremental',
    incremental_strategy='insert_overwrite',
    partition_by={'field': 'load_date', 'data_type': 'date'},
    cluster_by=['game_id']
) }}

select
    id as game_id,
    cast(load_date as date) as load_date,
    rating,
    rating_top,
    ratings_count,
    reviews_count,
    reviews_text_count,
    metacritic,
    playtime,
    suggestions_count,
    community_rating,
    updated
from {{ source('bronze', 'games') }}
{% if is_incremental() %}
where cast(load_date as date) > (select max(load_date) from {{ this }})
{% endif %}