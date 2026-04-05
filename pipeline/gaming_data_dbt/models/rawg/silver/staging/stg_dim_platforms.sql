{{ config(materialized='table') }}

with latest_snapshot as (
    select
        id as platform_id,
        name,
        slug,
        games_count,
        image_background,
        year_start,
        year_end,
        description,
        row_number() over (partition by id order by load_date desc) as rn
    from {{ source('bronze', 'platforms') }}
)

select
    platform_id,
    name,
    slug,
    games_count,
    image_background,
    year_start,
    year_end,
    description
from latest_snapshot
where rn = 1
