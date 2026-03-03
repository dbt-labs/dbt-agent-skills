-- This model uses the truncate() filter which works in dbt-core but not in Fusion
-- Error: dbt1501: Failed to render SQL too many arguments

{% set my_string = 'this_is_a_long_column_name_that_exceeds_sixty_four_characters_and_should_be_truncated' %}

select 1 as {{ my_string | truncate(64, end='') }}
