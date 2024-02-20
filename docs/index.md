# Welcome

For now, as Vintage pi TV is in active development, this documentation is
a placeholder.

## Configuration values

{% for name, description, optional in CONFIG_VALUES %}
* `{{ name }}` (optional {{ optional }})

{{ description }}
{% endfor %}
