from functools import wraps
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.generic import View
from .models import UserRole, Role, TenantPermission


def has_permission(user, permission_codename, tenant=None):
    """
    Check if a user has a specific permission within a tenant.
    
    Args:
        user: The user to check permissions for
        permission_codename: The codename of the permission to check
        tenant: The tenant to check permissions in (defaults to user's tenant)
    
    Returns:
        bool: True if the user has the permission, False otherwise
    """
    if not user.is_authenticated:
        return False
    
    # Use the user's tenant if none is provided
    if tenant is None:
        tenant = getattr(user, 'tenant', None)
        if tenant is None:
            return False
    
    # Superusers have all permissions
    if user.is_superuser:
        return True
    
    # Check if user has any role with the required permission
    user_roles = UserRole.objects.filter(user=user, tenant=tenant).select_related('role')
    
    for user_role in user_roles:
        # Admin role has all permissions
        if user_role.role.name.lower() == 'admin':
            return True
        
        # Check if the role has the specific permission
        if user_role.role.has_permission(permission_codename):
            return True
    
    return False


def has_role(user, role_name, tenant=None):
    """
    Check if a user has a specific role within a tenant.
    
    Args:
        user: The user to check roles for
        role_name: The name of the role to check
        tenant: The tenant to check roles in (defaults to user's tenant)
    
    Returns:
        bool: True if the user has the role, False otherwise
    """
    if not user.is_authenticated:
        return False
    
    # Use the user's tenant if none is provided
    if tenant is None:
        tenant = getattr(user, 'tenant', None)
        if tenant is None:
            return False
    
    # Superusers have all roles
    if user.is_superuser:
        return True
    
    return UserRole.objects.filter(
        user=user,
        role__name=role_name,
        tenant=tenant
    ).exists()


def get_user_permissions(user, tenant=None):
    """
    Get all permissions for a user within a tenant.
    
    Args:
        user: The user to get permissions for
        tenant: The tenant to get permissions in (defaults to user's tenant)
    
    Returns:
        list: A list of permission codenames
    """
    if not user.is_authenticated:
        return []
    
    # Use the user's tenant if none is provided
    if tenant is None:
        tenant = getattr(user, 'tenant', None)
        if tenant is None:
            return []
    
    # Superusers have all permissions
    if user.is_superuser:
        return TenantPermission.objects.values_list('codename', flat=True)
    
    permissions = set()
    user_roles = UserRole.objects.filter(user=user, tenant=tenant).select_related('role')
    
    for user_role in user_roles:
        # Admin role gets all permissions
        if user_role.role.name.lower() == 'admin':
            return list(TenantPermission.objects.values_list('codename', flat=True))
        
        # Add permissions from this role
        role_permissions = user_role.role.permissions.values_list('codename', flat=True)
        permissions.update(role_permissions)
    
    return list(permissions)


def get_user_roles(user, tenant=None):
    """
    Get all roles for a user within a tenant.
    
    Args:
        user: The user to get roles for
        tenant: The tenant to get roles in (defaults to user's tenant)
    
    Returns:
        list: A list of role names
    """
    if not user.is_authenticated:
        return []
    
    # Use the user's tenant if none is provided
    if tenant is None:
        tenant = getattr(user, 'tenant', None)
        if tenant is None:
            return []
    
    # Check if user has UserRole entries
    user_roles = UserRole.objects.filter(user=user, tenant=tenant)
    
    if user_roles.exists():
        # Use UserRole entries if they exist
        return list(user_roles.values_list('role__name', flat=True))
    else:
        # Fall back to direct role field from CustomUser
        if hasattr(user, 'role'):
            return [user.role]
        return []


def role_required(roles=None, permissions=None, login_url=None, raise_exception=False):
    """
    Decorator for views that checks whether a user has any of the specified roles
    or any of the specified permissions, redirecting to the log-in page if necessary.
    
    Args:
        roles: A list of role names that are allowed to access the view
        permissions: A list of permission codenames that are allowed to access the view
        login_url: The URL to redirect to if the user is not authenticated
        raise_exception: Whether to raise PermissionDenied instead of redirecting
    """
    def check_perms(user):
        if not user.is_authenticated:
            return False
        
        # Superusers have access to everything
        if user.is_superuser:
            return True
        
        tenant = getattr(user, 'tenant', None)
        if tenant is None:
            return False
        
        # Check if user has any of the required roles
        if roles:
            for role_name in roles:
                if has_role(user, role_name, tenant):
                    return True
        
        # Check if user has any of the required permissions
        if permissions:
            for permission_codename in permissions:
                if has_permission(user, permission_codename, tenant):
                    return True
        
        # If no roles or permissions were specified, deny access
        if not roles and not permissions:
            return False
        
        return False
    
    return user_passes_test(check_perms, login_url=login_url)


def permission_required(permission_codename, login_url=None, raise_exception=False):
    """
    Decorator for views that checks whether a user has a specific permission.
    
    Args:
        permission_codename: The codename of the permission required
        login_url: The URL to redirect to if the user is not authenticated
        raise_exception: Whether to raise PermissionDenied instead of redirecting
    """
    return role_required(permissions=[permission_codename], login_url=login_url, raise_exception=raise_exception)


class TenantPermissionRequiredMixin:
    """
    Mixin for class-based views that checks whether a user has a specific permission.
    """
    permission_codename = None
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        # Superusers have access to everything
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        
        tenant = getattr(request.user, 'tenant', None)
        if tenant is None:
            return self.handle_no_permission()
        
        if self.permission_codename and not has_permission(request.user, self.permission_codename, tenant):
            return self.handle_no_permission()
        
        return super().dispatch(request, *args, **kwargs)
    
    def handle_no_permission(self):
        """
        Handle the case when the user doesn't have permission.
        By default, this raises PermissionDenied.
        """
        raise PermissionDenied


class TenantRoleRequiredMixin:
    """
    Mixin for class-based views that checks whether a user has a specific role.
    """
    required_roles = None
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        # Superusers have access to everything
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        
        tenant = getattr(request.user, 'tenant', None)
        if tenant is None:
            return self.handle_no_permission()
        
        if self.required_roles:
            has_required_role = False
            for role_name in self.required_roles:
                if has_role(request.user, role_name, tenant):
                    has_required_role = True
                    break
            
            if not has_required_role:
                return self.handle_no_permission()
        
        return super().dispatch(request, *args, **kwargs)
    
    def handle_no_permission(self):
        """
        Handle the case when the user doesn't have the required role.
        By default, this raises PermissionDenied.
        """
        raise PermissionDenied


def get_permission_context(request):
    """
    Get permission context for templates.
    
    Args:
        request: The HttpRequest object
    
    Returns:
        dict: A dictionary with permission information
    """
    if not request.user.is_authenticated:
        return {}
    
    tenant = getattr(request.user, 'tenant', None)
    if tenant is None:
        return {}
    
    return {
        'user_permissions': get_user_permissions(request.user, tenant),
        'user_roles': get_user_roles(request.user, tenant),
        'is_admin': has_role(request.user, 'Admin', tenant),
        'is_lawyer': has_role(request.user, 'Lawyer', tenant),
        'is_paralegal': has_role(request.user, 'Paralegal', tenant),
        'is_billing_manager': has_role(request.user, 'Billing Manager', tenant),
        'is_readonly_staff': has_role(request.user, 'Read-only Staff', tenant),
    }