{{ config(materialized='table') }}

select * from {{ ref('stg_dim_genres') }}