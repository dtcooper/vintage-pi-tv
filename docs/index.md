# Welcome

For now, this documentation is just a placeholder.

## Configuration values

{% for name, description, optional in CONFIG_VALUES %}
* `{{ name }}` (optional {{ optional }})

{{ description }}
{% endfor %}
