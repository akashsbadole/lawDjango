from .branding_utils import get_tenant_branding_context


def tenant_settings(request):
    """
    Context processor to add tenant settings to all templates.
    """
    context = {}
    
    # Only add tenant settings if tenant is available
    if hasattr(request, 'tenant') and request.tenant:
        # Apply tenant branding to context
        branding_context = get_tenant_branding_context(request.tenant)
        context.update(branding_context)
    
    return context