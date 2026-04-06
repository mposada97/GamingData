{{ config(
    materialized='incremental',
    unique_key=['game_id', 'genre_id'],
    incremental_strategy='merge'
) }}

select
    g.game_id,
    genre.id as genre_id,
    g.load_date
from {{ ref('stg_dim_games') }} g,
unnest(g.genres) as genre
{% if is_incremental() %}
where g.load_date > (select max(load_date) from {{ this }})
{% endif %}