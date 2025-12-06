"""
Tenant branding utilities and helpers.

This module provides utilities for generating and managing tenant branding,
including CSS generation, image processing, and asset management.
"""

import os
import hashlib
from io import BytesIO

try:
    from PIL import Image, ImageOps
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None
    ImageOps = None

# For compatibility with older PIL versions
if PIL_AVAILABLE and hasattr(Image, 'Resampling'):
    # Use newer resampling constants if available
    LANCZOS = Image.Resampling.LANCZOS
else:
    # Fallback to older constants
    LANCZOS = Image.LANCZOS if PIL_AVAILABLE and hasattr(Image, 'LANCZOS') else Image.ANTIALIAS if PIL_AVAILABLE else None

from django.conf import settings
from django.core.cache import cache
from django.templatetags.static import static
from django.utils.safestring import mark_safe
from django.http import HttpResponse
from .models import TenantSettings


def get_tenant_settings(tenant):
    """
    Get tenant settings with caching.
    
    Args:
        tenant: Tenant instance
        
    Returns:
        TenantSettings instance
    """
    cache_key = f'tenant_settings_{tenant.id}'
    cached_settings = cache.get(cache_key)
    
    if cached_settings is None:
        cached_settings = tenant.get_settings()
        cache.set(cache_key, cached_settings, timeout=300)  # Cache for 5 minutes
    
    return cached_settings


def generate_tenant_css(tenant_settings):
    """
    Generate CSS for tenant branding.
    
    Args:
        tenant_settings: TenantSettings instance
        
    Returns:
        CSS string with tenant-specific styles
    """
    css_vars = tenant_settings.get_theme_css_variables()
    css_lines = [':root {']
    
    # Add CSS custom properties
    for var_name, var_value in css_vars.items():
        css_lines.append(f'  {var_name}: {var_value};')
    
    css_lines.append('}')
    
    # Add custom CSS if provided
    if tenant_settings.custom_css:
        css_lines.append('')
        css_lines.append('/* Custom tenant CSS */')
        css_lines.append(tenant_settings.custom_css)
    
    # Add theme-specific styles
    css_lines.append('')
    css_lines.append('/* Tenant-specific theme styles */')
    
    # Generate theme-specific CSS based on colors
    colors = tenant_settings.get_brand_colors()
    
    # Button styles
    css_lines.append('.btn-primary {')
    css_lines.append(f'  background-color: {colors["primary"]} !important;')
    css_lines.append(f'  border-color: {colors["primary"]} !important;')
    css_lines.append('}')
    
    css_lines.append('.btn-secondary {')
    css_lines.append(f'  background-color: {colors["secondary"]} !important;')
    css_lines.append(f'  border-color: {colors["secondary"]} !important;')
    css_lines.append('}')
    
    css_lines.append('.btn-accent {')
    css_lines.append(f'  background-color: {colors["accent"]} !important;')
    css_lines.append(f'  border-color: {colors["accent"]} !important;')
    css_lines.append('}')
    
    # Link styles
    css_lines.append('a {')
    css_lines.append(f'  color: {colors["primary"]} !important;')
    css_lines.append('}')
    
    # Navbar styles
    css_lines.append('.navbar-brand {')
    css_lines.append(f'  color: {colors["primary"]} !important;')
    css_lines.append('}')
    
    css_lines.append('.navbar {')
    css_lines.append(f'  background-color: {colors["background"]} !important;')
    css_lines.append(f'  border-color: {colors["secondary"]} !important;')
    css_lines.append('}')
    
    # Form styles
    css_lines.append('.form-control:focus {')
    css_lines.append(f'  border-color: {colors["primary"]} !important;')
    css_lines.append(f'  box-shadow: 0 0 0 0.2rem {colors["primary"]}40 !important;')
    css_lines.append('}')
    
    # Font styles
    css_lines.append('body {')
    css_lines.append(f'  font-family: {tenant_settings.font_family} !important;')
    css_lines.append(f'  color: {colors["text"]} !important;')
    css_lines.append(f'  background-color: {colors["background"]} !important;')
    css_lines.append('}')
    
    css_lines.append('h1, h2, h3, h4, h5, h6 {')
    css_lines.append(f'  font-family: {tenant_settings.font_heading_family} !important;')
    css_lines.append('}')
    
    # Footer styles
    css_lines.append('.footer {')
    css_lines.append(f'  background-color: {colors["secondary"]} !important;')
    css_lines.append(f'  color: {colors["text"]} !important;')
    css_lines.append('}')
    
    return '\n'.join(css_lines)


def get_tenant_css_url(tenant):
    """
    Get URL for tenant-specific CSS file.
    
    Args:
        tenant: Tenant instance
        
    Returns:
        URL string for tenant CSS
    """
    settings = get_tenant_settings(tenant)
    cache_key = f'tenant_css_{tenant.id}_{settings.updated_at.timestamp()}'
    
    # Check if CSS is already cached
    cached_url = cache.get(cache_key)
    if cached_url:
        return cached_url
    
    # Generate CSS content
    css_content = generate_tenant_css(settings)
    
    # Create hash for filename
    css_hash = hashlib.md5(css_content.encode()).hexdigest()[:8]
    filename = f'tenant_{tenant.slug}_{css_hash}.css'
    
    # For now, return a dynamic URL that will be handled by a view
    # In production, this would be saved to a static file
    css_url = f'/static/tenant_css/{filename}'
    
    # Cache the URL
    cache.set(cache_key, css_url, timeout=3600)  # Cache for 1 hour
    
    return css_url


def process_logo(image_field, max_size=(300, 300), format='PNG'):
    """
    Process and optimize logo image.
    
    Args:
        image_field: ImageField instance
        max_size: Tuple of (width, height) for maximum size
        format: Output format (PNG, JPEG, etc.)
        
    Returns:
        Processed image file
    """
    if not image_field or not PIL_AVAILABLE:
        return None
    
    try:
        # Open image
        img = Image.open(image_field)
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        # Resize while maintaining aspect ratio
        img.thumbnail(max_size, LANCZOS)
        
        # Save to BytesIO
        output = BytesIO()
        img.save(output, format=format, optimize=True)
        output.seek(0)
        
        return output
        
    except Exception as e:
        # Log error and return None
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error processing logo: {e}")
        return None


def process_favicon(image_field, size=(32, 32)):
    """
    Process image for favicon.
    
    Args:
        image_field: ImageField instance
        size: Tuple of (width, height) for favicon size
        
    Returns:
        Processed favicon file
    """
    if not image_field or not PIL_AVAILABLE or not ImageOps:
        return None
    
    try:
        # Open image
        img = Image.open(image_field)
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        # Resize to favicon size
        img = ImageOps.fit(img, size, LANCZOS)
        
        # Save to BytesIO as ICO
        output = BytesIO()
        img.save(output, format='ICO', sizes=[size])
        output.seek(0)
        
        return output
        
    except Exception as e:
        # Log error and return None
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error processing favicon: {e}")
        return None


def get_tenant_favicon_url(tenant):
    """
    Get URL for tenant-specific favicon.
    
    Args:
        tenant: Tenant instance
        
    Returns:
        URL string for tenant favicon
    """
    settings = get_tenant_settings(tenant)
    
    if settings.favicon:
        return settings.favicon.url
    
    # Return default favicon
    return static('images/favicon.ico')


def get_tenant_logo_url(tenant, theme='light'):
    """
    Get URL for tenant-specific logo.
    
    Args:
        tenant: Tenant instance
        theme: Theme mode ('light' or 'dark')
        
    Returns:
        URL string for tenant logo
    """
    settings = get_tenant_settings(tenant)
    return settings.get_logo_url(theme)


def get_tenant_login_background_url(tenant):
    """
    Get URL for tenant login background image.
    
    Args:
        tenant: Tenant instance
        
    Returns:
        URL string for login background or None
    """
    settings = get_tenant_settings(tenant)
    return settings.get_login_background_url()


def get_tenant_branding_context(tenant):
    """
    Get branding context for templates.
    
    Args:
        tenant: Tenant instance
        
    Returns:
        Dictionary with branding context
    """
    settings = get_tenant_settings(tenant)
    
    return {
        'tenant': tenant,
        'settings': settings,
        'logo_url': get_tenant_logo_url(tenant),
        'logo_url_dark': get_tenant_logo_url(tenant, theme='dark'),
        'favicon_url': get_tenant_favicon_url(tenant),
        'login_background_url': get_tenant_login_background_url(tenant),
        'css_url': get_tenant_css_url(tenant),
        'company_info': settings.get_company_info(),
        'email_settings': settings.get_email_settings(),
        'brand_colors': settings.get_brand_colors(),
        'css_variables': settings.get_theme_css_variables(),
        'custom_css': settings.custom_css,
        'theme_mode': settings.theme_mode,
        'font_family': settings.font_family,
        'font_heading_family': settings.font_heading_family,
    }


def clear_tenant_branding_cache(tenant):
    """
    Clear branding cache for a tenant.
    
    Args:
        tenant: Tenant instance
    """
    # Clear settings cache
    cache.delete(f'tenant_settings_{tenant.id}')
    
    # Clear CSS cache
    settings = get_tenant_settings(tenant)
    cache_key = f'tenant_css_{tenant.id}_{settings.updated_at.timestamp()}'
    cache.delete(cache_key)
    
    # Clear other branding-related caches
    cache.delete(f'tenant_favicon_{tenant.id}')
    cache.delete(f'tenant_logo_{tenant.id}')
    cache.delete(f'tenant_logo_dark_{tenant.id}')
    cache.delete(f'tenant_login_bg_{tenant.id}')
    cache.delete(f'tenant_manifest_{tenant.id}')


def clear_branding_cache(tenant):
    """
    Alias for clear_tenant_branding_cache for backward compatibility.
    
    Args:
        tenant: Tenant instance
    """
    clear_tenant_branding_cache(tenant)


def validate_branding_image(image_file, max_size_mb=5, allowed_formats=None, max_width=None, max_height=None, square_only=False):
    """
    Validate uploaded branding image.
    
    Args:
        image_file: Uploaded image file
        max_size_mb: Maximum file size in MB
        allowed_formats: List of allowed image formats
        max_width: Maximum width in pixels
        max_height: Maximum height in pixels
        square_only: Whether image must be square
        
    Returns:
        None if valid, raises ValidationError if invalid
    """
    from django.core.exceptions import ValidationError
    
    if allowed_formats is None:
        allowed_formats = ['PNG', 'JPEG', 'JPG', 'GIF']
    
    # Check file size
    if image_file.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f"Image size must be less than {max_size_mb}MB")
    
    # Check file format
    if not PIL_AVAILABLE:
        raise ValidationError("Image processing not available")
    
    try:
        img = Image.open(image_file)
        if img.format not in allowed_formats:
            raise ValidationError(f"Image format must be one of: {', '.join(allowed_formats)}")
        
        # Check dimensions if specified
        width, height = img.size
        
        if max_width and width > max_width:
            raise ValidationError(f"Image width must be less than {max_width}px")
        
        if max_height and height > max_height:
            raise ValidationError(f"Image height must be less than {max_height}px")
        
        if square_only and width != height:
            raise ValidationError("Image must be square (equal width and height)")
            
    except Exception as e:
        if isinstance(e, ValidationError):
            raise e
        raise ValidationError("Invalid image file")


def generate_email_template_context(tenant):
    """
    Generate context for email templates.
    
    Args:
        tenant: Tenant instance
        
    Returns:
        Dictionary with email template context
    """
    settings = get_tenant_settings(tenant)
    company_info = settings.get_company_info()
    email_settings = settings.get_email_settings()
    
    return {
        'company_name': company_info['name'],
        'company_tagline': company_info['tagline'],
        'company_website': company_info['website'],
        'company_address': company_info['address'],
        'company_phone': company_info['phone'],
        'company_email': company_info['email'],
        'logo_url': get_tenant_logo_url(tenant),
        'from_name': email_settings['from_name'],
        'from_address': email_settings['from_address'],
        'reply_to': email_settings['reply_to'],
        'email_header': email_settings['header'],
        'email_footer': email_settings['footer'],
        'brand_colors': settings.get_brand_colors(),
    }


def generate_pdf_template_context(tenant):
    """
    Generate context for PDF templates.
    
    Args:
        tenant: Tenant instance
        
    Returns:
        Dictionary with PDF template context
    """
    settings = get_tenant_settings(tenant)
    company_info = settings.get_company_info()
    
    return {
        'company_name': company_info['name'],
        'company_tagline': company_info['tagline'],
        'company_address': company_info['address'],
        'company_phone': company_info['phone'],
        'company_email': company_info['email'],
        'company_website': company_info['website'],
        'logo_url': get_tenant_logo_url(tenant),
        'brand_colors': settings.get_brand_colors(),
        'font_family': settings.font_family,
        'font_heading_family': settings.font_heading_family,
    }


def apply_tenant_branding(request, context):
    """
    Apply tenant branding to template context.
    
    Args:
        request: HttpRequest instance
        context: Template context dictionary
        
    Returns:
        Updated context dictionary with branding
    """
    if hasattr(request, 'tenant') and request.tenant:
        branding_context = get_tenant_branding_context(request.tenant)
        context.update(branding_context)
    
    return context


def get_tenant_manifest_data(tenant):
    """
    Generate PWA manifest data for tenant.
    
    Args:
        tenant: Tenant instance
        
    Returns:
        Dictionary with PWA manifest data
    """
    settings = get_tenant_settings(tenant)
    company_info = settings.get_company_info()
    
    return {
        'name': company_info['name'],
        'short_name': company_info['name'][:20],
        'description': company_info.get('tagline', f'{company_info["name"]} Law Firm Management'),
        'start_url': f'/app/{tenant.slug}/',
        'display': 'standalone',
        'background_color': settings.background_color,
        'theme_color': settings.primary_color,
        'icons': [
            {
                'src': get_tenant_logo_url(tenant),
                'sizes': '192x192',
                'type': 'image/png'
            },
            {
                'src': get_tenant_logo_url(tenant),
                'sizes': '512x512',
                'type': 'image/png'
            }
        ]
    }