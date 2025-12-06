from django import template
from ..models import Client

register = template.Library()


@register.simple_tag
def get_client_count(tenant):
    """
    Return the total number of active clients for a given tenant.
    """
    return Client.objects.active_for_tenant(tenant).count()


@register.simple_tag
def get_recent_clients(tenant, limit=5):
    """
    Return the most recent clients for a given tenant.
    """
    return Client.objects.active_for_tenant(tenant).order_by('-created_at')[:limit]


@register.simple_tag
def get_total_client_count(tenant):
    """
    Return the total number of clients (including deleted) for a given tenant.
    """
    return Client.objects.for_tenant(tenant).count()


@register.simple_tag
def get_deleted_client_count(tenant):
    """
    Return the number of deleted clients for a given tenant.
    """
    return Client.objects.for_tenant(tenant).filter(deleted_at__isnull=False).count()