"""Views for tenant branding functionality."""

import os
import hashlib
from django.conf import settings
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.templatetags.static import static
from .models import Tenant
from .branding_utils import generate_tenant_css, get_tenant_settings


def tenant_css(request, tenant_slug):
    """
    Serve tenant-specific CSS.
    
    Args:
        request: HttpRequest instance
        tenant_slug: Slug of the tenant
        
    Returns:
        HttpResponse with CSS content
    """
    try:
        # Get tenant
        tenant = get_object_or_404(Tenant, slug=tenant_slug)
        
        # Get tenant settings
        tenant_settings = get_tenant_settings(tenant)
        
        # Generate cache key
        cache_key = f'tenant_css_{tenant.pk}_{tenant_settings.updated_at.timestamp()}'
        
        # Check if CSS is already cached
        cached_css = cache.get(cache_key)
        if cached_css:
            return HttpResponse(cached_css, content_type='text/css')
        
        # Generate CSS content
        css_content = generate_tenant_css(tenant_settings)
        
        # Cache the CSS
        cache.set(cache_key, css_content, timeout=3600)  # Cache for 1 hour
        
        # Return CSS response
        response = HttpResponse(css_content, content_type='text/css')
        response['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
        return response
        
    except Http404:
        raise
    except Exception as e:
        # Log error and return empty CSS
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating tenant CSS: {e}")
        return HttpResponse('', content_type='text/css')


def tenant_favicon(request, tenant_slug):
    """
    Serve tenant-specific favicon.
    
    Args:
        request: HttpRequest instance
        tenant_slug: Slug of the tenant
        
    Returns:
        HttpResponse with favicon content
    """
    try:
        # Get tenant
        tenant = get_object_or_404(Tenant, slug=tenant_slug)
        
        # Get tenant settings
        tenant_settings = get_tenant_settings(tenant)
        
        if tenant_settings.favicon:
            # Read favicon file
            with open(tenant_settings.favicon.path, 'rb') as f:
                favicon_data = f.read()
            
            # Return favicon response
            response = HttpResponse(favicon_data, content_type='image/x-icon')
            response['Cache-Control'] = 'public, max-age=86400'  # Cache for 24 hours
            return response
        
        # Return default favicon if tenant doesn't have one
        default_favicon_path = os.path.join(settings.STATIC_ROOT, 'images', 'favicon.ico')
        if os.path.exists(default_favicon_path):
            with open(default_favicon_path, 'rb') as f:
                favicon_data = f.read()
            response = HttpResponse(favicon_data, content_type='image/x-icon')
            response['Cache-Control'] = 'public, max-age=86400'  # Cache for 24 hours
            return response
        
        # Return empty response if no favicon found
        return HttpResponse('', content_type='image/x-icon')
        
    except Http404:
        raise
    except Exception as e:
        # Log error and return empty response
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error serving tenant favicon: {e}")
        return HttpResponse('', content_type='image/x-icon')


def tenant_logo(request, tenant_slug, theme='light'):
    """
    Serve tenant-specific logo.
    
    Args:
        request: HttpRequest instance
        tenant_slug: Slug of the tenant
        theme: Theme mode ('light' or 'dark')
        
    Returns:
        HttpResponse with logo content
    """
    try:
        # Get tenant
        tenant = get_object_or_404(Tenant, slug=tenant_slug)
        
        # Get tenant settings
        tenant_settings = get_tenant_settings(tenant)
        
        # Get appropriate logo based on theme
        logo_url = tenant_settings.get_logo_url(theme)
        
        if logo_url and logo_url != static('images/logo.png'):
            # Extract file path from URL
            if theme == 'dark' and tenant_settings.logo_dark:
                logo_path = tenant_settings.logo_dark.path
            else:
                logo_path = tenant_settings.logo.path
            
            # Read logo file
            with open(logo_path, 'rb') as f:
                logo_data = f.read()
            
            # Return logo response
            response = HttpResponse(logo_data, content_type='image/png')
            response['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
            return response
        
        # Return default logo if tenant doesn't have one
        return HttpResponse('', content_type='image/png')
        
    except Http404:
        raise
    except Exception as e:
        # Log error and return empty response
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error serving tenant logo: {e}")
        return HttpResponse('', content_type='image/png')


def tenant_login_background(request, tenant_slug):
    """
    Serve tenant-specific login background image.
    
    Args:
        request: HttpRequest instance
        tenant_slug: Slug of the tenant
        
    Returns:
        HttpResponse with background image content
    """
    try:
        # Get tenant
        tenant = get_object_or_404(Tenant, slug=tenant_slug)
        
        # Get tenant settings
        tenant_settings = get_tenant_settings(tenant)
        
        if tenant_settings.login_background_image:
            # Read background image file
            with open(tenant_settings.login_background_image.path, 'rb') as f:
                bg_data = f.read()
            
            # Return background image response
            response = HttpResponse(bg_data, content_type='image/jpeg')
            response['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
            return response
        
        # Return empty response if no background image found
        return HttpResponse('', content_type='image/jpeg')
        
    except Http404:
        raise
    except Exception as e:
        # Log error and return empty response
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error serving tenant login background: {e}")
        return HttpResponse('', content_type='image/jpeg')


def tenant_manifest(request, tenant_slug):
    """
    Serve tenant-specific PWA manifest.
    
    Args:
        request: HttpRequest instance
        tenant_slug: Slug of the tenant
        
    Returns:
        HttpResponse with PWA manifest JSON
    """
    try:
        from .branding_utils import get_tenant_manifest_data
        import json
        
        # Get tenant
        tenant = get_object_or_404(Tenant, slug=tenant_slug)
        
        # Generate manifest data
        manifest_data = get_tenant_manifest_data(tenant)
        
        # Return manifest response
        response = HttpResponse(
            json.dumps(manifest_data, indent=2),
            content_type='application/manifest+json'
        )
        response['Cache-Control'] = 'public, max-age=3600'  # Cache for 1 hour
        return response
        
    except Http404:
        raise
    except Exception as e:
        # Log error and return empty response
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error generating tenant manifest: {e}")
        return HttpResponse('{}', content_type='application/manifest+json')