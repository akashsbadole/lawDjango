from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages


def role_required(role_name):
    """
    Decorator to require a specific role to access a view.
    
    Usage:
    @role_required('Admin')
    def my_view(request):
        ...
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if not hasattr(request.user, 'tenant') or not request.user.tenant:
                messages.error(request, "You don't have a tenant assigned.")
                return redirect('home')
            
            from .utils import get_user_roles
            roles = get_user_roles(request.user, request.user.tenant)
            
            if not any(role.name == role_name for role in roles):
                messages.error(request, f"You don't have permission to access this page. Required role: {role_name}")
                return redirect('home')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def permission_required(permission_codename):
    """
    Decorator to require a specific permission to access a view.
    
    Usage:
    @permission_required('clients.view_client')
    def my_view(request):
        ...
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if not hasattr(request.user, 'tenant') or not request.user.tenant:
                messages.error(request, "You don't have a tenant assigned.")
                return redirect('home')
            
            from .utils import has_permission
            if not has_permission(request.user, permission_codename, request.user.tenant):
                messages.error(request, f"You don't have permission to access this page. Required permission: {permission_codename}")
                return redirect('home')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def any_permission_required(permission_codenames):
    """
    Decorator to require any of the specified permissions to access a view.
    
    Usage:
    @any_permission_required(['clients.view_client', 'clients.add_client'])
    def my_view(request):
        ...
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if not hasattr(request.user, 'tenant') or not request.user.tenant:
                messages.error(request, "You don't have a tenant assigned.")
                return redirect('home')
            
            from .utils import has_permission
            if not any(has_permission(request.user, perm, request.user.tenant) for perm in permission_codenames):
                messages.error(request, f"You don't have permission to access this page. Required one of: {', '.join(permission_codenames)}")
                return redirect('home')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def all_permissions_required(permission_codenames):
    """
    Decorator to require all of the specified permissions to access a view.
    
    Usage:
    @all_permissions_required(['clients.view_client', 'clients.add_client'])
    def my_view(request):
        ...
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            if not hasattr(request.user, 'tenant') or not request.user.tenant:
                messages.error(request, "You don't have a tenant assigned.")
                return redirect('home')
            
            from .utils import has_permission
            if not all(has_permission(request.user, perm, request.user.tenant) for perm in permission_codenames):
                messages.error(request, f"You don't have permission to access this page. Required all of: {', '.join(permission_codenames)}")
                return redirect('home')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator