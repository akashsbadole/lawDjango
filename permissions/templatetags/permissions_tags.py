from django import template
from ..utils import has_permission, get_user_roles

register = template.Library()


@register.filter
def has_permission(user, permission_codename):
    """
    Check if a user has a specific permission.
    
    Usage:
    {% if user|has_permission:'clients.view_client' %}
        <!-- Show content -->
    {% endif %}
    """
    if not user.is_authenticated:
        return False
    
    # Get tenant from user
    if not hasattr(user, 'tenant') or not user.tenant:
        return False
    
    from ..utils import has_permission as check_permission
    return check_permission(user, permission_codename, user.tenant)


@register.filter
def has_role(user, role_name):
    """
    Check if a user has a specific role.
    
    Usage:
    {% if user|has_role:'Admin' %}
        <!-- Show admin content -->
    {% endif %}
    """
    if not user.is_authenticated:
        return False
    
    # Get tenant from user
    if not hasattr(user, 'tenant') or not user.tenant:
        return False
    
    roles = get_user_roles(user, user.tenant)
    return any(role == role_name for role in roles)


@register.simple_tag
def get_user_permissions(user):
    """
    Get all permissions for a user.
    
    Usage:
    {% get_user_permissions user as perms %}
    {% for perm in perms %}
        {{ perm.name }}
    {% endfor %}
    """
    if not user.is_authenticated or not hasattr(user, 'tenant') or not user.tenant:
        return []
    
    from ..models import TenantPermission
    roles = get_user_roles(user, user.tenant)
    permissions = set()
    
    for role in roles:
        permissions.update(role.permissions.all())
    
    # Admin role gets all permissions
    if any(role.name == 'Admin' for role in roles):
        permissions = set(TenantPermission.objects.filter(tenant=user.tenant))
    
    return list(permissions)


@register.simple_tag
def get_user_role_names(user):
    """
    Get all role names for a user.
    
    Usage:
    {% get_user_role_names user as role_names %}
    {% for role_name in role_names %}
        {{ role_name }}
    {% endfor %}
    """
    if not user.is_authenticated or not hasattr(user, 'tenant') or not user.tenant:
        return []
    
    roles = get_user_roles(user, user.tenant)
    return [role.name for role in roles]