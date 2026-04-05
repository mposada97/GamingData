{{ config(materialized='table') }}

with latest_snapshot as (
    select
        id as tag_id,
        name,
        slug,
        games_count,
        image_background,
        language,
        row_number() over (partition by id order by load_date desc) as rn
    from {{ source('bronze', 'tags') }}
)

select
    tag_id,
    name,
    slug,
    games_count,
    image_background,
    language
from latest_snapshot
where rn = 1
