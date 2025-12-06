from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseRedirect
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class SuperAdminAccessMiddleware(MiddlewareMixin):
    """
    Middleware to control access to super admin areas.
    Ensures only superusers can access platform admin URLs.
    """
    
    def process_request(self, request):
        """
        Check if the requested URL requires super admin access.
        If so, verify the user is a superuser.
        """
        # URLs that require super admin access
        admin_urls = [
            '/platform-admin/',
            '/admin/platform_admin/',
        ]
        
        # Check if the request is for a super admin URL
        path = request.path
        is_admin_url = any(path.startswith(url) for url in admin_urls)
        
        if is_admin_url:
            # If user is not authenticated, redirect to login
            if not request.user.is_authenticated:
                logger.info(f"Unauthenticated user attempted to access {path}")
                return redirect(f"{settings.LOGIN_URL}?next={path}")
            
            # If user is authenticated but not a superuser
            if not request.user.is_superuser:
                logger.warning(
                    f"Non-superuser {request.user.email} attempted to access {path}"
                )
                messages.error(
                    request,
                    "You don't have permission to access the super admin panel."
                )
                return redirect('home')  # Redirect to home page
        
        return None


class SuperAdminActivityMiddleware(MiddlewareMixin):
    """
    Middleware to log super admin activities for audit purposes.
    """
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Log super admin activities before the view is executed.
        """
        # Only log activities for super admins
        if not (request.user.is_authenticated and request.user.is_superuser):
            return None
        
        # Only log activities for platform admin URLs
        path = request.path
        admin_urls = [
            '/platform-admin/',
            '/admin/platform_admin/',
        ]
        
        is_admin_url = any(path.startswith(url) for url in admin_urls)
        if not is_admin_url:
            return None
        
        # Get action type based on request method and view name
        action_type = self._get_action_type(request, view_func)
        
        # Skip logging for certain views (like dashboard views)
        if action_type == 'view' and 'dashboard' in path:
            return None
        
        # Store the activity info in request for later processing
        request.admin_activity = {
            'action_type': action_type,
            'view_name': getattr(view_func, '__name__', 'Unknown'),
            'path': path,
            'method': request.method,
        }
        
        return None
    
    def process_response(self, request, response):
        """
        Log the admin activity after the view has been processed.
        """
        if hasattr(request, 'admin_activity') and response.status_code < 400:
            from .models import AdminActivityLog
            from tenants.models import Tenant
            
            try:
                activity = request.admin_activity
                
                # Extract tenant ID from URL if present
                tenant_id = None
                if 'tenant' in activity['path']:
                    # Extract tenant ID from URL pattern like /platform-admin/tenants/123/
                    parts = activity['path'].split('/')
                    for i, part in enumerate(parts):
                        if part == 'tenants' and i + 1 < len(parts):
                            try:
                                tenant_id = int(parts[i + 1])
                            except (ValueError, IndexError):
                                pass
                            break
                
                # Get tenant object if ID is available
                tenant = None
                if tenant_id:
                    try:
                        tenant = Tenant.objects.get(id=tenant_id)
                    except Tenant.DoesNotExist:
                        pass
                
                # Create activity log entry
                AdminActivityLog.objects.create(
                    admin_user=request.user,
                    action_type=activity['action_type'],
                    action_description=self._get_action_description(request, activity),
                    tenant=tenant,
                    ip_address=self._get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    details={
                        'view_name': activity['view_name'],
                        'path': activity['path'],
                        'method': activity['method'],
                        'status_code': response.status_code,
                    }
                )
                
            except Exception as e:
                logger.error(f"Error logging admin activity: {e}")
        
        return response
    
    def _get_action_type(self, request, view_func):
        """Determine the action type based on request method and view name."""
        method = request.method.lower()
        view_name = getattr(view_func, '__name__', '').lower()
        
        if method == 'get':
            if 'detail' in view_name or 'edit' in view_name:
                return 'view'
            return 'view'
        elif method == 'post':
            if 'delete' in view_name:
                return 'delete'
            elif 'create' in view_name or 'add' in view_name:
                return 'create'
            elif 'bulk' in view_name:
                return 'bulk_operation'
            else:
                return 'update'
        elif method == 'put' or method == 'patch':
            return 'update'
        elif method == 'delete':
            return 'delete'
        
        return 'view'
    
    def _get_action_description(self, request, activity):
        """Generate a human-readable description of the action."""
        action_type = activity['action_type']
        path = activity['path']
        view_name = activity['view_name']
        
        # Extract resource type from path
        resource_type = 'Unknown'
        if '/tenants/' in path:
            resource_type = 'Tenant'
        elif '/users/' in path:
            resource_type = 'User'
        elif '/notes/' in path:
            resource_type = 'Admin Note'
        elif '/announcements/' in path:
            resource_type = 'System Announcement'
        elif '/settings/' in path:
            resource_type = 'System Settings'
        elif '/health/' in path:
            resource_type = 'System Health'
        elif '/revenue/' in path:
            resource_type = 'Revenue Report'
        elif '/activity/' in path:
            resource_type = 'Activity Log'
        
        # Generate description based on action type and resource
        if action_type == 'view':
            if 'dashboard' in path:
                return 'Viewed super admin dashboard'
            elif 'list' in view_name:
                return f'Viewed {resource_type} list'
            else:
                return f'Viewed {resource_type}'
        elif action_type == 'create':
            return f'Created {resource_type}'
        elif action_type == 'update':
            return f'Updated {resource_type}'
        elif action_type == 'delete':
            return f'Deleted {resource_type}'
        elif action_type == 'bulk_operation':
            return f'Performed bulk operation on {resource_type}s'
        elif action_type == 'system_change':
            return f'Modified system settings'
        else:
            return f'Accessed {resource_type}'
    
    def _get_client_ip(self, request):
        """Get the client's IP address from the request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SuperAdminSecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add security headers for super admin areas.
    """
    
    def process_response(self, request, response):
        """
        Add security headers for super admin responses.
        """
        # Only apply to super admin URLs
        path = request.path
        admin_urls = [
            '/platform-admin/',
            '/admin/platform_admin/',
        ]
        
        is_admin_url = any(path.startswith(url) for url in admin_urls)
        if not is_admin_url:
            return response
        
        # Add security headers
        response['X-Frame-Options'] = 'DENY'
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Add Cache-Control headers for sensitive pages
        if 'login' in path or 'settings' in path:
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        
        return response