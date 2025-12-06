from django import template

register = template.Library()

@register.filter
def div(value, arg):
    """
    Divides the value by the arg.
    """
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def mul(value, arg):
    """
    Multiplies the value by the arg.
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0