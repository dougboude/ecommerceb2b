from django import template

from marketplace.constants import KM_PER_MILE

register = template.Library()


@register.filter
def km_to_miles(value):
    """Convert a km value to miles, rounded to nearest integer."""
    if value is None:
        return None
    return round(value / KM_PER_MILE)
