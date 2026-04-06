{{ config(
    materialized='incremental',
    incremental_strategy='insert_overwrite',
    partition_by={'field': 'load_date', 'data_type': 'date'},
    cluster_by=['game_id']
) }}

select * from {{ ref('stg_fct_game_snapshots') }}
{% if is_incremental() %}
where load_date > (select max(load_date) from {{ this }})
{% endif %}