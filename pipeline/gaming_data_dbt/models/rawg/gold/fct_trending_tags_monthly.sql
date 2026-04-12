{{ config(materialized='table') }}

with base as (
    select
        date_trunc(g.released, month) as release_month,
        brdg.tag_id,
        dt.name as tag_name,
        g.game_id,
        g.rating,
        g.ratings_count
    from {{ ref('dim_games') }} g
    inner join {{ ref('brdg_game_tags') }} brdg on g.game_id = brdg.game_id
    inner join {{ ref('dim_tags') }} dt on brdg.tag_id = dt.tag_id
    where g.released is not null
),

aggregated as (
    select
        release_month,
        tag_id,
        tag_name,
        count(distinct game_id) as games_tagged,
        avg(rating) as avg_rating,
        sum(ratings_count) as total_ratings_count
    from base
    group by release_month,
        tag_id,
        tag_name
)

select
    release_month,
    tag_id,
    tag_name,
    games_tagged,
    avg_rating,
    total_ratings_count,
    row_number() over (partition by release_month order by games_tagged desc) as rank_in_month
from aggregated
qualify rank_in_month <= 50
order by release_month desc, rank_in_month asc