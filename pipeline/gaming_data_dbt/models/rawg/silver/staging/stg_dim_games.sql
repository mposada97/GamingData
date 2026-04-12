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

with new_or_updated as (
    select *
    from {{ source('bronze', 'games') }}
    {% if is_incremental() %}
    where cast(load_date as date) > (select max(load_date) from {{ this }})
    {% endif %}
),

deduped as (
    select
        id as game_id,
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
        genres,
        platforms,
        parent_platforms,
        stores,
        tags,
        ratings as rating_distribution,
        cast(load_date as date) as load_date,
        row_number() over (partition by id order by updated desc) as rn
    from new_or_updated
)

select * except (rn)
from deduped
where rn = 1