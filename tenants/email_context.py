"""
Email context utilities for multi-tenant application.

This module provides utilities for generating tenant-specific
email context, ensuring proper branding and personalization.
"""

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import translation
from .branding_utils import get_tenant_branding_context


def get_tenant_email_context(tenant):
    """
    Get email context for a specific tenant.
    
    Args:
        tenant: The tenant instance
        
    Returns:
        A dictionary with tenant-specific email context
    """
    # Get tenant branding context
    branding_context = get_tenant_branding_context(tenant)
    
    # Get tenant settings
    tenant_settings = tenant.get_settings()
    
    # Build email context
    context = {
        # Basic tenant information
        'tenant': tenant,
        'tenant_name': tenant.name,
        'tenant_slug': tenant.slug,
        'tenant_plan': tenant.plan,
        'tenant_status': tenant.status,
        
        # Company information
        'company_name': tenant_settings.get_company_name(),
        'company_tagline': tenant_settings.company_tagline,
        'company_website': tenant_settings.company_website,
        'company_address': tenant_settings.company_address,
        'company_phone': tenant_settings.company_phone,
        'company_email': tenant_settings.company_email,
        
        # Email settings
        'email_from_name': tenant_settings.get_email_from_name(),
        'email_from_address': tenant_settings.get_email_from_address(),
        'email_reply_to': tenant_settings.get_email_reply_to(),
        'email_header': tenant_settings.email_header,
        'email_footer': tenant_settings.email_footer,
        
        # Branding
        'logo_url': branding_context.get('logo_url'),
        'favicon_url': branding_context.get('favicon_url'),
        'brand_colors': branding_context.get('brand_colors'),
        'css_variables': branding_context.get('css_variables'),
        
        # URLs
        'tenant_url': f"/app/{tenant.slug}/",
        'login_url': f"/app/{tenant.slug}/login/",
        'dashboard_url': f"/app/{tenant.slug}/",
        'settings_url': f"/app/{tenant.slug}/settings/",
        
        # Application URLs
        'support_url': getattr(settings, 'SUPPORT_URL', '#'),
        'privacy_url': getattr(settings, 'PRIVACY_URL', '#'),
        'terms_url': getattr(settings, 'TERMS_URL', '#'),
        'unsubscribe_url': f"/app/{tenant.slug}/unsubscribe/",
        
        # Configuration
        'site_name': getattr(settings, 'SITE_NAME', 'Law Firm Management'),
        'site_url': getattr(settings, 'SITE_URL', ''),
        'contact_email': getattr(settings, 'CONTACT_EMAIL', 'support@lawfirm.com'),
    }
    
    return context


def render_tenant_email(template_name, context, tenant=None, language=None):
    """
    Render an email template with tenant context.
    
    Args:
        template_name: The name of the email template
        context: The context dictionary for the template
        tenant: The tenant instance (optional)
        language: The language code (optional)
        
    Returns:
        The rendered email content
    """
    # Activate the specified language if provided
    if language:
        translation.activate(language)
    
    # Add tenant context if tenant is provided
    if tenant:
        tenant_context = get_tenant_email_context(tenant)
        context.update(tenant_context)
    
    # Render the template
    return render_to_string(template_name, context)


def get_tenant_email_headers(tenant):
    """
    Get email headers for a specific tenant.
    
    Args:
        tenant: The tenant instance
        
    Returns:
        A dictionary with tenant-specific email headers
    """
    # Get tenant settings
    tenant_settings = tenant.get_settings()
    
    # Build email headers
    headers = {
        'X-Tenant-ID': tenant.slug,
        'X-Tenant-Name': tenant.name,
        'X-Tenant-Plan': tenant.plan,
    }
    
    # Add custom headers if configured
    if hasattr(settings, 'TENANT_EMAIL_HEADERS'):
        headers.update(settings.TENANT_EMAIL_HEADERS)
    
    # Add reply-to header if configured
    reply_to = tenant_settings.get_email_reply_to()
    if reply_to:
        headers['Reply-To'] = reply_to
    
    return headers


def get_tenant_email_from_address(tenant):
    """
    Get the from address for tenant emails.
    
    Args:
        tenant: The tenant instance
        
    Returns:
        The from email address
    """
    # Get tenant settings
    tenant_settings = tenant.get_settings()
    
    # Get the configured from address
    from_address = tenant_settings.get_email_from_address()
    
    # Format the from address with tenant name
    from_name = tenant_settings.get_email_from_name()
    if from_name and from_address:
        return f"{from_name} <{from_address}>"
    elif from_address:
        return from_address
    
    # Fallback to default
    return getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@lawfirm.com')


def get_tenant_email_subject_prefix(tenant):
    """
    Get the subject prefix for tenant emails.
    
    Args:
        tenant: The tenant instance
        
    Returns:
        The subject prefix string
    """
    # Get tenant settings
    tenant_settings = tenant.get_settings()
    
    # Get the company name
    company_name = tenant_settings.get_company_name()
    
    # Return the subject prefix
    return f"[{company_name}]"


def format_tenant_email_links(links, tenant):
    """
    Format links for tenant emails.
    
    Args:
        links: A dictionary of link names and URLs
        tenant: The tenant instance
        
    Returns:
        A dictionary of formatted links
    """
    formatted_links = {}
    
    for name, url in links.items():
        # Add tenant prefix to relative URLs
        if url.startswith('/'):
            url = f"/app/{tenant.slug}{url}"
        
        formatted_links[name] = url
    
    return formatted_links


def get_tenant_email_template_context(tenant, extra_context=None):
    """
    Get a complete email template context for a tenant.
    
    Args:
        tenant: The tenant instance
        extra_context: Additional context to include
        
    Returns:
        A complete email template context
    """
    # Get base tenant email context
    context = get_tenant_email_context(tenant)
    
    # Add extra context if provided
    if extra_context:
        context.update(extra_context)
    
    # Add email-specific context
    context.update({
        # Email metadata
        'email_type': context.get('email_type', 'notification'),
        'email_priority': context.get('email_priority', 'normal'),
        'email_category': context.get('email_category', 'general'),
        
        # Tracking
        'tracking_enabled': getattr(settings, 'EMAIL_TRACKING_ENABLED', False),
        'tracking_pixel': getattr(settings, 'EMAIL_TRACKING_PIXEL', ''),
        
        # Unsubscribe information
        'can_unsubscribe': True,
        'unsubscribe_text': _('If you no longer wish to receive these emails, please unsubscribe.'),
        
        # Legal information
        'privacy_policy': getattr(settings, 'PRIVACY_POLICY_URL', '#'),
        'terms_of_service': getattr(settings, 'TERMS_OF_SERVICE_URL', '#'),
        'legal_disclaimer': getattr(settings, 'EMAIL_LEGAL_DISCLAIMER', ''),
    })
    
    return context


def validate_tenant_email_template(template_name, tenant):
    """
    Validate that an email template exists for a tenant.
    
    Args:
        template_name: The name of the email template
        tenant: The tenant instance
        
    Returns:
        True if the template exists, False otherwise
    """
    try:
        # Try to render the template
        render_tenant_email(template_name, {}, tenant=tenant)
        return True
    except Exception:
        return False


def get_tenant_email_templates(tenant):
    """
    Get a list of available email templates for a tenant.
    
    Args:
        tenant: The tenant instance
        
    Returns:
        A list of available email templates
    """
    # Define standard email templates
    templates = [
        'tenants/email/welcome.html',
        'tenants/email/password_reset.html',
        'tenants/email/email_confirmation.html',
        'tenants/email/account_locked.html',
        'tenants/email/subscription_expired.html',
        'tenants/email/subscription_renewed.html',
        'tenants/email/invoice_created.html',
        'tenants/email/payment_received.html',
        'tenants/email/case_assigned.html',
        'tenants/email/document_shared.html',
    ]
    
    # Check if tenant has custom templates
    tenant_templates = []
    for template in templates:
        # Check for tenant-specific template
        tenant_template = template.replace('tenants/', f'tenants/{tenant.slug}/')
        if validate_tenant_email_template(tenant_template, tenant):
            tenant_templates.append(tenant_template)
        else:
            tenant_templates.append(template)
    
    return tenant_templates