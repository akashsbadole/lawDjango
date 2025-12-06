from django.contrib.auth.mixins import LoginRequiredMixin, AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages


class TenantPermissionRequiredMixin(LoginRequiredMixin, AccessMixin):
    """
    Mixin to require specific permissions for view access.
    Ensures user is authenticated and has the required permission.
    """
    permission_required = None
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        if not hasattr(request.user, 'tenant') or not request.user.tenant:
            messages.error(request, "You don't have a tenant assigned.")
            return redirect('home')
        
        if self.permission_required:
            from .utils import has_permission
            if not has_permission(request.user, self.permission_required, request.user.tenant):
                messages.error(request, f"You don't have permission to access this page. Required permission: {self.permission_required}")
                return self.handle_no_permission()
        
        return super().dispatch(request, *args, **kwargs)


class AnyPermissionRequiredMixin(LoginRequiredMixin, AccessMixin):
    """
    Mixin to require any of the specified permissions for view access.
    Ensures user is authenticated and has at least one of the required permissions.
    """
    permission_required = None  # Can be a string or list of strings
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        if not hasattr(request.user, 'tenant') or not request.user.tenant:
            messages.error(request, "You don't have a tenant assigned.")
            return redirect('home')
        
        if self.permission_required:
            from .utils import has_permission
            
            # Convert to list if it's a single string
            permissions = self.permission_required
            if isinstance(permissions, str):
                permissions = [permissions]
            
            if not any(has_permission(request.user, perm, request.user.tenant) for perm in permissions):
                perms_str = ', '.join(permissions)
                messages.error(request, f"You don't have permission to access this page. Required one of: {perms_str}")
                return self.handle_no_permission()
        
        return super().dispatch(request, *args, **kwargs)


class AllPermissionsRequiredMixin(LoginRequiredMixin, AccessMixin):
    """
    Mixin to require all of the specified permissions for view access.
    Ensures user is authenticated and has all of the required permissions.
    """
    permission_required = None  # Can be a string or list of strings
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        if not hasattr(request.user, 'tenant') or not request.user.tenant:
            messages.error(request, "You don't have a tenant assigned.")
            return redirect('home')
        
        if self.permission_required:
            from .utils import has_permission
            
            # Convert to list if it's a single string
            permissions = self.permission_required
            if isinstance(permissions, str):
                permissions = [permissions]
            
            if not all(has_permission(request.user, perm, request.user.tenant) for perm in permissions):
                perms_str = ', '.join(permissions)
                messages.error(request, f"You don't have permission to access this page. Required all of: {perms_str}")
                return self.handle_no_permission()
        
        return super().dispatch(request, *args, **kwargs)


class RoleRequiredMixin(LoginRequiredMixin, AccessMixin):
    """
    Mixin to require a specific role for view access.
    Ensures user is authenticated and has the required role.
    """
    role_required = None
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        if not hasattr(request.user, 'tenant') or not request.user.tenant:
            messages.error(request, "You don't have a tenant assigned.")
            return redirect('home')
        
        if self.role_required:
            from .utils import get_user_roles
            roles = get_user_roles(request.user, request.user.tenant)
            
            # Check if roles is a list of strings (from direct role field) or role objects
            has_role = False
            if roles and isinstance(roles[0], str):
                # List of role names
                has_role = self.role_required.lower() in [r.lower() for r in roles]
            else:
                # List of role objects
                has_role = any(role.name == self.role_required for role in roles)
            
            if not has_role:
                messages.error(request, f"You don't have permission to access this page. Required role: {self.role_required}")
                return self.handle_no_permission()
        
        return super().dispatch(request, *args, **kwargs)


class AnyRoleRequiredMixin(LoginRequiredMixin, AccessMixin):
    """
    Mixin to require any of the specified roles for view access.
    Ensures user is authenticated and has at least one of the required roles.
    """
    role_required = None  # Can be a string or list of strings
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        if not hasattr(request.user, 'tenant') or not request.user.tenant:
            messages.error(request, "You don't have a tenant assigned.")
            return redirect('home')
        
        if self.role_required:
            from .utils import get_user_roles
            roles = get_user_roles(request.user, request.user.tenant)
            
            # Convert to list if it's a single string
            required_roles = self.role_required
            if isinstance(required_roles, str):
                required_roles = [required_roles]
            
            # Check if roles is a list of strings (from direct role field) or role objects
            has_role = False
            if roles and isinstance(roles[0], str):
                # List of role names
                has_role = any(r.lower() in [role.lower() for role in required_roles] for r in roles)
            else:
                # List of role objects
                has_role = any(role.name in required_roles for role in roles)
            
            if not has_role:
                roles_str = ', '.join(required_roles)
                messages.error(request, f"You don't have permission to access this page. Required one of: {roles_str}")
                return self.handle_no_permission()
        
        return super().dispatch(request, *args, **kwargs)