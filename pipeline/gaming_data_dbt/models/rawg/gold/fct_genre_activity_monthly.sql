{{ config(materialized='table') }}

with latest_in_month as (
    select
        game_id,
        date_trunc(load_date, month) as month_start,
        max(load_date) as latest_load_date
    from {{ ref('fct_game_snapshots') }}
    group by 1, 2
),

genre_monthly as (
    select
        lm.month_start,
        g.genre_id,
        genres.name as genre_name,
        count(distinct s.game_id) as games_with_activity,
        avg(s.rating) as avg_rating,
        avg(s.metacritic) as avg_metacritic,
        sum(s.ratings_count) as total_ratings_count
    from latest_in_month lm
    inner join {{ ref('fct_game_snapshots') }} s
        on s.game_id = lm.game_id
        and s.load_date = lm.latest_load_date
    inner join {{ ref('brdg_game_genres') }} g
        on s.game_id = g.game_id
    inner join {{ ref('dim_genres') }} genres
        on genres.genre_id = g.genre_id
    group by 1, 2, 3
)

select
    month_start,
    genre_id,
    genre_name,
    games_with_activity,
    avg_rating,
    avg_metacritic,
    total_ratings_count,
    sum(games_with_activity) over (partition by month_start) as total_games_that_month,
    round(
        100.0 * games_with_activity / sum(games_with_activity) over (partition by month_start),
        2
    ) as activity_share_pct,
    rank() over (partition by month_start order by games_with_activity desc) as activity_rank,
    games_with_activity - lag(games_with_activity) over (
        partition by genre_id order by month_start
    ) as activity_change_vs_prev_month
from genre_monthly
order by month_start desc, activity_rank