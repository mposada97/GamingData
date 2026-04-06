{{ config(
    materialized='incremental',
    unique_key=['game_id', 'tag_id'],
    incremental_strategy='merge'
) }}

select * from {{ ref('stg_brdg_game_tags') }}
{% if is_incremental() %}
where load_date > (select max(load_date) from {{ this }})
{% endif %}
