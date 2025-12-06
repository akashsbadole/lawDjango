"""
Tenant Impersonation Views
Implements Feature #13 from todo.md: Tenant Impersonation (SuperAdmin Only)
"""
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth import login, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_POST, require_GET

from tenants.models import Tenant

User = get_user_model()


def is_superuser(user):
    """Check if user is a superuser."""
    return user.is_superuser


@login_required
@user_passes_test(is_superuser)
@require_POST
def impersonate_tenant(request, tenant_id):
    """
    Allow superadmin to impersonate a tenant admin for support.
    Stores original user in session for later restoration.
    """
    tenant = get_object_or_404(Tenant, pk=tenant_id, deleted_at__isnull=True)
    
    # Find the tenant admin
    admin_user = tenant.users.filter(role='admin').first()
    
    if not admin_user:
        # Try to find any user from the tenant
        admin_user = tenant.users.first()
    
    if not admin_user:
        messages.error(request, f'No users found for tenant "{tenant.name}".')
        return redirect('platform_admin:tenant_list')
    
    # Store original user info in session
    request.session['_impersonate_original_user_id'] = request.user.pk
    request.session['_impersonate_original_user_email'] = request.user.email
    request.session['_impersonate_tenant_id'] = tenant.pk
    request.session['_impersonate_tenant_name'] = tenant.name
    request.session['_is_impersonating'] = True
    
    # Log the impersonation for audit
    from audit.models import AuditLog
    AuditLog.objects.create(
        user=request.user,
        action='impersonate_start',
        model_name='Tenant',
        object_id=tenant.pk,
        details=f'Started impersonating tenant "{tenant.name}" as user "{admin_user.email}"',
        tenant=tenant
    )
    
    # Login as the tenant admin
    login(request, admin_user, backend='django.contrib.auth.backends.ModelBackend')
    
    messages.warning(
        request,
        f'⚠️ You are now impersonating "{tenant.name}" as {admin_user.email}. '
        f'Click "Stop Impersonation" in the header to return to your account.'
    )
    
    return redirect('lawyer_panel:dashboard')


@login_required
@require_GET
def stop_impersonation(request):
    """
    Stop impersonating and return to original superadmin account.
    """
    original_user_id = request.session.get('_impersonate_original_user_id')
    
    if not original_user_id:
        messages.error(request, 'You are not currently impersonating anyone.')
        return redirect('home')
    
    try:
        original_user = User.objects.get(pk=original_user_id)
    except User.DoesNotExist:
        messages.error(request, 'Original user not found.')
        return redirect('home')
    
    # Get impersonation details for audit log
    tenant_id = request.session.get('_impersonate_tenant_id')
    tenant_name = request.session.get('_impersonate_tenant_name')
    impersonated_user_email = request.user.email
    
    # Clear impersonation session data
    del request.session['_impersonate_original_user_id']
    del request.session['_impersonate_original_user_email']
    del request.session['_impersonate_tenant_id']
    del request.session['_impersonate_tenant_name']
    del request.session['_is_impersonating']
    
    # Log the end of impersonation
    if tenant_id:
        from audit.models import AuditLog
        try:
            tenant = Tenant.objects.get(pk=tenant_id)
            AuditLog.objects.create(
                user=original_user,
                action='impersonate_stop',
                model_name='Tenant',
                object_id=tenant_id,
                details=f'Stopped impersonating tenant "{tenant_name}" (was logged in as "{impersonated_user_email}")',
                tenant=tenant
            )
        except Tenant.DoesNotExist:
            pass
    
    # Login as original user
    login(request, original_user, backend='django.contrib.auth.backends.ModelBackend')
    
    messages.success(request, f'Welcome back, {original_user.email}! Impersonation ended.')
    
    return redirect('platform_admin:dashboard')


def impersonation_context_processor(request):
    """
    Context processor to add impersonation status to all templates.
    Add to settings.py TEMPLATES context_processors.
    """
    return {
        'is_impersonating': request.session.get('_is_impersonating', False),
        'impersonate_original_user_email': request.session.get('_impersonate_original_user_email'),
        'impersonate_tenant_name': request.session.get('_impersonate_tenant_name'),
    }
