-- This model uses .meta_get() on a plain dictionary
-- Only config objects have meta_get(); plain dicts should use .get()
-- This triggers dbt1501: "unknown method: map has no method named meta_get"

{% set meta_config = config.get('meta', {}) %}
{% set owner = meta_config.meta_get('owner', 'unknown') %}

select
  1 as id,
  '{{ owner }}' as owner
