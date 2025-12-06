from django.shortcuts import get_object_or_404
from django.http import Http404, HttpResponsePermanentRedirect
from django.urls import reverse
from django.conf import settings
from .models import Tenant


class TenantMiddleware:
    """
    Middleware to identify the current tenant based on the URL structure.
    
    This middleware extracts the tenant slug from URLs with the pattern /app/{tenant_slug}/
    and sets request.tenant to the appropriate Tenant object.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Process the request to identify tenant
        tenant = self.get_tenant_from_request(request)
        
        # Set the tenant on the request object
        request.tenant = tenant
        
        # Get the response
        response = self.get_response(request)
        
        return response
    
    def get_tenant_from_request(self, request):
        """
        Extract tenant slug from the URL path and return the corresponding Tenant object.
        
        Expected URL pattern: /app/{tenant_slug}/
        Also checks session for tenant context for login flows.
        """
        path = request.path
        
        # First, check if tenant is already set in session (for login flows)
        if hasattr(request, 'user') and request.user.is_authenticated:
            if 'current_tenant_id' in request.session:
                try:
                    tenant_id = request.session['current_tenant_id']
                    tenant = Tenant.objects.get(pk=tenant_id)
                    
                    # Validate tenant status
                    if tenant.status == 'deleted':
                        return None
                    elif tenant.status == 'suspended':
                        return self.handle_suspended_tenant(request, tenant)
                    elif tenant.status == 'trial_expired':
                        return self.handle_trial_expired_tenant(request, tenant)
                    elif not tenant.is_active:
                        return self.handle_inactive_tenant(request, tenant)
                    
                    return tenant
                except (Tenant.DoesNotExist, ValueError):
                    # Clear invalid tenant from session
                    if 'current_tenant_id' in request.session:
                        del request.session['current_tenant_id']
                        request.session.save()
        
        # Check if the path matches our tenant pattern
        # Split the path and check if it starts with 'app'
        path_parts = path.strip('/').split('/')
        
        # If path doesn't have enough parts or doesn't start with 'app', return None
        if len(path_parts) < 2 or path_parts[0] != 'app':
            return None
        
        # Extract the tenant slug
        tenant_slug = path_parts[1]
        
        # If no tenant slug provided, return None
        if not tenant_slug:
            return None
        
        try:
            # Get the tenant with the provided slug (including deleted ones)
            tenant = Tenant.objects.get(slug=tenant_slug)
            
            if not tenant:
                raise Http404(f"Tenant '{tenant_slug}' not found")
            
            # Handle different tenant statuses
            if tenant.status == 'deleted':
                raise Http404(f"Tenant '{tenant_slug}' has been deleted")
            elif tenant.status == 'suspended':
                return self.handle_suspended_tenant(request, tenant)
            elif tenant.status == 'trial_expired':
                return self.handle_trial_expired_tenant(request, tenant)
            elif not tenant.is_active:
                return self.handle_inactive_tenant(request, tenant)
            
            # Store tenant in session for future requests
            if hasattr(request, 'user') and request.user.is_authenticated:
                request.session['current_tenant_id'] = tenant.pk
                request.session.save()
            
            return tenant
            
        except Tenant.DoesNotExist:
            # Handle non-existent tenant
            raise Http404(f"Tenant '{tenant_slug}' not found")
    
    def handle_suspended_tenant(self, request, tenant):
        """
        Handle the case when a tenant is suspended.
        
        Shows a maintenance page with suspension information.
        """
        from django.shortcuts import render
        
        # For API requests, return JSON response
        if request.path.startswith('/api/') or request.headers.get('Accept') == 'application/json':
            from django.http import JsonResponse
            return JsonResponse({
                'error': 'Tenant suspended',
                'message': f"Tenant '{tenant.name}' is temporarily suspended",
                'reason': tenant.suspension_reason or 'No reason provided'
            }, status=403)
        
        # For web requests, show a maintenance page
        return render(request, 'tenants/tenant_suspended.html', {
            'tenant': tenant,
            'reason': tenant.suspension_reason or 'No reason provided'
        })
    
    def handle_trial_expired_tenant(self, request, tenant):
        """
        Handle the case when a tenant's trial has expired.
        
        Shows a page with upgrade options.
        """
        from django.shortcuts import render
        
        # For API requests, return JSON response
        if request.path.startswith('/api/') or request.headers.get('Accept') == 'application/json':
            from django.http import JsonResponse
            return JsonResponse({
                'error': 'Trial expired',
                'message': f"Trial for '{tenant.name}' has expired",
                'upgrade_required': True
            }, status=402)
        
        # For web requests, show a trial expired page
        return render(request, 'tenants/tenant_trial_expired.html', {
            'tenant': tenant
        })
    
    def handle_inactive_tenant(self, request, tenant):
        """
        Handle the case when a tenant exists but is inactive.
        
        This could redirect to a subscription page, show a message, etc.
        """
        from django.shortcuts import render
        
        # For API requests, return JSON response
        if request.path.startswith('/api/') or request.headers.get('Accept') == 'application/json':
            from django.http import JsonResponse
            return JsonResponse({
                'error': 'Tenant inactive',
                'message': f"Tenant '{tenant.name}' is currently inactive"
            }, status=403)
        
        # For web requests, show an inactive page
        return render(request, 'tenants/tenant_inactive.html', {
            'tenant': tenant
        })