{{ config(materialized='table') }}

with base as (
    select
        date_trunc(g.released, month) as release_month,
        brdg.platform_id,
        dp.name as platform_name,
        g.game_id,
        g.rating,
        g.metacritic,
        g.ratings_count
    from {{ ref('dim_games') }} g
    inner join {{ ref('brdg_game_platforms') }} brdg on g.game_id = brdg.game_id
    inner join {{ ref('dim_platforms') }} dp on brdg.platform_id = dp.platform_id
    where g.released is not null
),

aggregated as (
    select
        release_month,
        platform_id,
        platform_name,
        count(distinct game_id) as games_released,
        avg(rating) as avg_rating,
        avg(metacritic) as avg_metacritic,
        sum(ratings_count) as total_ratings_count
    from base
    group by release_month,
        platform_id,
        platform_name
)

select
    release_month,
    platform_id,
    platform_name,
    games_released,
    avg_rating,
    avg_metacritic,
    total_ratings_count,
    round(100.0 * games_released / sum(games_released) over (partition by release_month), 2) as share_of_month_pct,
    rank() over (partition by release_month order by games_released desc) as rank_in_month,
    games_released - lag(games_released) over (partition by platform_id order by release_month) as releases_change_vs_prev_month
from aggregated
order by release_month desc, rank_in_month