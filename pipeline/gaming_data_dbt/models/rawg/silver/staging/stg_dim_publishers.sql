{{ config(materialized='table') }}

with latest_snapshot as (
    select
        id as publisher_id,
        name,
        slug,
        games_count,
        image_background,
        description,
        row_number() over (partition by id order by load_date desc) as rn
    from {{ source('bronze', 'publishers') }}
)

select
    publisher_id,
    name,
    slug,
    games_count,
    image_background,
    description
from latest_snapshot
where rn = 1
