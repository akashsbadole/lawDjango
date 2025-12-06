"""
Utility functions for multi-tenant application.

This module provides utility functions for tenant management,
including tenant detection, context management, and helper functions.
"""

from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from .models import Tenant


def get_current_tenant(request=None):
    """
    Get the current tenant from the request.
    
    Args:
        request: The HTTP request object (optional)
        
    Returns:
        The current tenant instance or None if not found
    """
    if request is None:
        return None
    
    # Try to get tenant from request attribute
    tenant = getattr(request, 'tenant', None)
    
    # If not found, try to detect from URL
    if not tenant and hasattr(request, 'path'):
        tenant = detect_tenant_from_path(request.path)
    
    # If still not found, try to detect from headers
    if not tenant and hasattr(request, 'META'):
        tenant = detect_tenant_from_headers(request.META)
    
    # If still not found, try to detect from subdomain
    if not tenant and hasattr(request, 'get_host'):
        tenant = detect_tenant_from_subdomain(request.get_host())
    
    return tenant


def detect_tenant_from_path(path):
    """
    Detect tenant from URL path.
    
    Args:
        path: The URL path
        
    Returns:
        The tenant instance or None if not found
    """
    if not path:
        return None
    
    # Get the tenant detection method
    detection_method = getattr(settings, 'TENANT_DETECTION_METHOD', 'path')
    
    if detection_method != 'path':
        return None
    
    # Get the URL prefix
    url_prefix = getattr(settings, 'TENANT_URL_PREFIX', 'app')
    
    # Split the path
    path_parts = path.strip('/').split('/')
    
    # Check if the path starts with the URL prefix
    if len(path_parts) < 2 or path_parts[0] != url_prefix:
        return None
    
    # Get the tenant slug
    tenant_slug = path_parts[1]
    
    if not tenant_slug:
        return None
    
    try:
        # Try to get the tenant
        return Tenant.objects.get(slug=tenant_slug, is_active=True)
    except Tenant.DoesNotExist:
        return None


def detect_tenant_from_headers(meta):
    """
    Detect tenant from HTTP headers.
    
    Args:
        meta: The request META dictionary
        
    Returns:
        The tenant instance or None if not found
    """
    if not meta:
        return None
    
    # Get the tenant detection method
    detection_method = getattr(settings, 'TENANT_DETECTION_METHOD', 'path')
    
    if detection_method != 'header':
        return None
    
    # Get the header name
    header_name = getattr(settings, 'TENANT_HEADER_NAME', 'X-Tenant-ID')
    
    # Get the tenant slug from header
    tenant_slug = meta.get(f'HTTP_{header_name.upper().replace("-", "_")}')
    
    if not tenant_slug:
        return None
    
    try:
        # Try to get the tenant
        return Tenant.objects.get(slug=tenant_slug, is_active=True)
    except Tenant.DoesNotExist:
        return None


def detect_tenant_from_subdomain(host):
    """
    Detect tenant from subdomain.
    
    Args:
        host: The HTTP host
        
    Returns:
        The tenant instance or None if not found
    """
    if not host:
        return None
    
    # Get the tenant detection method
    detection_method = getattr(settings, 'TENANT_DETECTION_METHOD', 'path')
    
    if detection_method != 'subdomain':
        return None
    
    # Get the base domain
    base_domain = getattr(settings, 'TENANT_SUBDOMAIN_DOMAIN', '')
    
    if not base_domain:
        return None
    
    # Extract the subdomain
    if '.' not in host:
        return None
    
    subdomain = host.split('.')[0]
    
    if not subdomain:
        return None
    
    try:
        # Try to get the tenant
        return Tenant.objects.get(slug=subdomain, is_active=True)
    except Tenant.DoesNotExist:
        return None


def set_current_tenant(request, tenant):
    """
    Set the current tenant on the request.
    
    Args:
        request: The HTTP request object
        tenant: The tenant instance
    """
    request.tenant = tenant
    
    # Update logging context
    try:
        from .logging import set_current_tenant
        set_current_tenant(tenant)
    except ImportError:
        pass
    
    # Update storage backends
    try:
        from .storage import TenantMediaStorage, TenantStaticStorage
        
        # Update media storage if it exists
        if hasattr(request, '_tenant_media_storage'):
            request._tenant_media_storage.set_tenant(tenant)
        
        # Update static storage if it exists
        if hasattr(request, '_tenant_static_storage'):
            request._tenant_static_storage.set_tenant(tenant)
    except ImportError:
        pass
    
    # Update template loaders
    try:
        from .template_loaders import TenantTemplateLoader, TenantAppDirectoriesLoader, HybridTenantLoader
        
        # Update template loaders if they exist
        if hasattr(request, '_template_loaders'):
            for loader in request._template_loaders:
                if hasattr(loader, 'set_tenant'):
                    loader.set_tenant(tenant)
    except ImportError:
        pass


def get_tenant_cache_key(key, tenant=None):
    """
    Get a tenant-specific cache key.
    
    Args:
        key: The base cache key
        tenant: The tenant instance (optional)
        
    Returns:
        The tenant-specific cache key
    """
    if not tenant:
        return key
    
    # Get the cache key prefix
    cache_prefix = getattr(settings, 'TENANT_CACHE_PREFIX', 'tenant')
    
    # Get the cache separator
    separator = getattr(settings, 'TENANT_CACHE_SEPARATOR', '_')
    
    # Get the cache version
    version = getattr(settings, 'TENANT_CACHE_VERSION', 1)
    
    # Build the cache key
    return f"{cache_prefix}{separator}{tenant.slug}{separator}{key}{separator}{version}"


def get_tenant_media_path(path, tenant=None):
    """
    Get a tenant-specific media path.
    
    Args:
        path: The base media path
        tenant: The tenant instance (optional)
        
    Returns:
        The tenant-specific media path
    """
    if not tenant:
        return path
    
    # Get the tenant media URL
    tenant_media_url = getattr(settings, 'TENANT_MEDIA_URL', '/media/')
    
    # Build the tenant-specific path
    return f"{tenant_media_url}{tenant.slug}/{path.lstrip('/')}"


def get_tenant_static_path(path, tenant=None):
    """
    Get a tenant-specific static path.
    
    Args:
        path: The base static path
        tenant: The tenant instance (optional)
        
    Returns:
        The tenant-specific static path
    """
    if not tenant:
        return path
    
    # Get the tenant static URL
    tenant_static_url = getattr(settings, 'TENANT_STATIC_URL', '/static/')
    
    # Build the tenant-specific path
    return f"{tenant_static_url}{tenant.slug}/{path.lstrip('/')}"


def get_tenant_url(url, tenant=None):
    """
    Get a tenant-specific URL.
    
    Args:
        url: The base URL
        tenant: The tenant instance (optional)
        
    Returns:
        The tenant-specific URL
    """
    if not tenant:
        return url
    
    # Get the URL prefix
    url_prefix = getattr(settings, 'TENANT_URL_PREFIX', 'app')
    
    # Check if the URL is absolute
    if url.startswith('/'):
        # Absolute URL
        return f"/{url_prefix}/{tenant.slug}{url}"
    else:
        # Relative URL
        return f"{url_prefix}/{tenant.slug}/{url}"


def validate_tenant_access(request, tenant=None):
    """
    Validate that the current user has access to the tenant.
    
    Args:
        request: The HTTP request object
        tenant: The tenant instance (optional)
        
    Returns:
        True if access is valid, False otherwise
        
    Raises:
        Http404: If access is invalid
    """
    # Get the current tenant
    if not tenant:
        tenant = get_current_tenant(request)
    
    if not tenant:
        raise Http404("Tenant not found")
    
    # Check if the tenant is active
    if not tenant.is_active or tenant.status != 'active':
        raise Http404("Tenant is not active")
    
    # Check if the tenant is suspended
    if tenant.status == 'suspended':
        raise Http404("Tenant is suspended")
    
    # Check if the tenant's trial has expired
    if tenant.status == 'trial_expired':
        raise Http404("Tenant's trial has expired")
    
    # Check if the tenant is deleted
    if tenant.status == 'deleted':
        raise Http404("Tenant has been deleted")
    
    # Check if the user has access to the tenant
    if request.user.is_authenticated:
        if hasattr(request.user, 'tenant') and request.user.tenant != tenant:
            raise Http404("You do not have access to this tenant")
    
    return True


def get_tenant_by_slug(slug):
    """
    Get a tenant by slug.
    
    Args:
        slug: The tenant slug
        
    Returns:
        The tenant instance or None if not found
    """
    try:
        return Tenant.objects.get(slug=slug, is_active=True)
    except Tenant.DoesNotExist:
        return None


def get_default_tenant():
    """
    Get the default tenant.
    
    Returns:
        The default tenant instance or None if not found
    """
    # Get the default tenant slug
    default_slug = getattr(settings, 'DEFAULT_TENANT_SLUG', 'default')
    
    return get_tenant_by_slug(default_slug)


def is_tenant_model(model):
    """
    Check if a model is tenant-aware.
    
    Args:
        model: The model class
        
    Returns:
        True if the model is tenant-aware, False otherwise
    """
    return hasattr(model, '_tenant_aware') and getattr(model, '_tenant_aware', False)


def get_tenant_field_name(model):
    """
    Get the tenant field name for a model.
    
    Args:
        model: The model class
        
    Returns:
        The tenant field name or None if not found
    """
    if not is_tenant_model(model):
        return None
    
    # Find the tenant field
    for field in model._meta.get_fields():
        if field.name == 'tenant':
            return field.name
    
    return None


def get_shared_models():
    """
    Get the list of shared models.
    
    Returns:
        A list of shared model names
    """
    shared_models = getattr(settings, 'TENANT_SHARED_MODELS', [])
    
    # Convert to list if it's a string
    if isinstance(shared_models, str):
        shared_models = [model.strip() for model in shared_models.split(',')]
    
    return shared_models


def is_shared_model(model):
    """
    Check if a model is shared across tenants.
    
    Args:
        model: The model class
        
    Returns:
        True if the model is shared, False otherwise
    """
    shared_models = get_shared_models()
    model_name = f"{model._meta.app_label}.{model._meta.model_name}"
    
    return model_name in shared_models


def get_tenant_choices():
    """
    Get a list of tenant choices for forms.
    
    Returns:
        A list of (slug, name) tuples
    """
    return [
        (tenant.slug, tenant.name)
        for tenant in Tenant.objects.filter(is_active=True, status='active').order_by('name')
    ]


def get_tenant_plan_choices():
    """
    Get a list of tenant plan choices for forms.
    
    Returns:
        A list of (value, label) tuples
    """
    return Tenant.PLAN_CHOICES


def get_tenant_status_choices():
    """
    Get a list of tenant status choices for forms.
    
    Returns:
        A list of (value, label) tuples
    """
    return Tenant.STATUS_CHOICES