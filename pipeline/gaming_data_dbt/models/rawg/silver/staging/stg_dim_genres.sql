{{ config(materialized='table') }}

with latest_snapshot as (
    select
        id as genre_id,
        name,
        slug,
        games_count,
        image_background,
        row_number() over (partition by id order by load_date desc) as rn
    from {{ source('bronze', 'genres') }}
)

select
    genre_id,
    name,
    slug,
    games_count,
    image_background
from latest_snapshot
where rn = 1