-- Lake Compute doesn't run hooks or apply grants, so this can't move as is.
{{ config(post_hook="select 1 as audited", grants={'select': ['reporter']}) }}

select * from {{ ref('orders') }}
