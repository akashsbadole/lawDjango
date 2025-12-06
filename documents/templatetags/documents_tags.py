from django import template
from ..models import Document

register = template.Library()


@register.simple_tag
def get_document_count(tenant):
    """
    Get the total number of documents for a tenant.
    """
    return Document.objects.for_tenant(tenant).count()


@register.simple_tag
def get_recent_documents(tenant, limit=5):
    """
    Get recent documents for a tenant.
    """
    return Document.objects.for_tenant(tenant).order_by('-created_at')[:limit]


@register.simple_tag
def get_storage_used(tenant):
    """
    Get storage used by a tenant in MB.
    """
    storage_bytes = Document.objects.get_storage_usage(tenant)
    return round(storage_bytes / (1024 * 1024), 2)