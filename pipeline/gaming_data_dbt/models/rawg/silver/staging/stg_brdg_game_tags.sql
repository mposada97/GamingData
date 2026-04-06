{{ config(
    materialized='incremental',
    unique_key=['game_id', 'tag_id'],
    incremental_strategy='merge'
) }}

select
    g.game_id,
    tag.id as tag_id,
    g.load_date
from {{ ref('stg_dim_games') }} g,
unnest(g.tags) as tag
{% if is_incremental() %}
where g.load_date > (select max(load_date) from {{ this }})
{% endif %}
