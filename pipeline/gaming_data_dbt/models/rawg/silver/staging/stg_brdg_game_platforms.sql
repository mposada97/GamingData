{{ config(
    materialized='incremental',
    unique_key=['game_id', 'platform_id'],
    incremental_strategy='merge'
) }}

select
    g.game_id,
    p.platform.id as platform_id,
    g.load_date
from {{ ref('stg_dim_games') }} g,
unnest(g.platforms) as p
{% if is_incremental() %}
where g.load_date > (select max(load_date) from {{ this }})
{% endif %}
