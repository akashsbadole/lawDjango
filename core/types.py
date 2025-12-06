"""
Common type definitions for the Django lawyer management system.
"""

from typing import TYPE_CHECKING
from django.http import HttpRequest

if TYPE_CHECKING:
    from tenants.models import Tenant
    from accounts.models import CustomUser


class TenantHttpRequest(HttpRequest):
    """HttpRequest subclass that includes the tenant attribute.
    
    This is used for type hinting throughout the application
    to indicate that the request has a tenant attribute set by middleware.
    """
    tenant: 'Tenant'


class UserWithRoleRequest(HttpRequest):
    """HttpRequest subclass that includes user with role attribute.
    
    This is used for type hinting to indicate that the request
    has a user with a role attribute.
    """
    user: 'CustomUser'


class TenantUserRequest(TenantHttpRequest):
    """HttpRequest subclass that includes both tenant and user with role.
    
    This combines both tenant and user role typing for convenience.
    """
    pass