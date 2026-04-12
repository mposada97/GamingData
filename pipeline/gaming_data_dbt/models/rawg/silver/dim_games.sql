{{ config(
    materialized='incremental',
    unique_key='game_id',
    incremental_strategy='merge',
    partition_by={
        'field': 'released',
        'data_type': 'date',
        'granularity': 'month'
    },
    cluster_by=['game_id']
) }}

select
    game_id,
    name,
    slug,
    released,
    tba,
    rating,
    rating_top,
    ratings_count,
    reviews_count,
    reviews_text_count,
    metacritic,
    playtime,
    suggestions_count,
    community_rating,
    updated,
    background_image,
    load_date
from {{ ref('stg_dim_games') }}
{% if is_incremental() %}
where load_date > (select max(load_date) from {{ this }})
{% endif %}