"""
Adapters for django-allauth to support multi-tenancy.

This module provides adapters that customize django-allauth behavior
for multi-tenant applications, ensuring proper tenant isolation.
"""

from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.http import Http404
from django.shortcuts import get_object_or_404
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from .models import Tenant


class TenantAccountAdapter(DefaultAccountAdapter):
    """
    Account adapter for multi-tenant application.
    
    This adapter customizes django-allauth behavior to support
    tenant-specific user accounts and authentication.
    """
    
    def get_signup_redirect_url(self, request):
        """
        Get the URL to redirect to after successful signup.
        
        Args:
            request: The HTTP request object
            
        Returns:
            The URL to redirect to
        """
        # Get the tenant from the request
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            # Redirect to tenant-specific home page
            return f"/app/{tenant.slug}/"
        
        # Fallback to default redirect URL
        return settings.LOGIN_REDIRECT_URL
    
    def get_logout_redirect_url(self, request):
        """
        Get the URL to redirect to after logout.
        
        Args:
            request: The HTTP request object
            
        Returns:
            The URL to redirect to
        """
        # Get the tenant from the request
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            # Redirect to tenant-specific home page
            return f"/app/{tenant.slug}/"
        
        # Fallback to default redirect URL
        return settings.ACCOUNT_LOGOUT_REDIRECT_URL
    
    def get_email_confirmation_redirect_url(self, request):
        """
        Get the URL to redirect to after email confirmation.
        
        Args:
            request: The HTTP request object
            
        Returns:
            The URL to redirect to
        """
        # Get the tenant from the request
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            # Redirect to tenant-specific home page
            return f"/app/{tenant.slug}/"
        
        # Fallback to default redirect URL
        return settings.LOGIN_REDIRECT_URL
    
    def get_password_change_redirect_url(self, request):
        """
        Get the URL to redirect to after password change.
        
        Args:
            request: The HTTP request object
            
        Returns:
            The URL to redirect to
        """
        # Get the tenant from the request
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            # Redirect to tenant-specific home page
            return f"/app/{tenant.slug}/"
        
        # Fallback to default redirect URL
        return settings.LOGIN_REDIRECT_URL
    
    def get_reset_password_redirect_url(self, request):
        """
        Get the URL to redirect to after password reset.
        
        Args:
            request: The HTTP request object
            
        Returns:
            The URL to redirect to
        """
        # Get the tenant from the request
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            # Redirect to tenant-specific home page
            return f"/app/{tenant.slug}/"
        
        # Fallback to default redirect URL
        return settings.LOGIN_REDIRECT_URL
    
    def is_open_for_signup(self, request):
        """
        Check if signup is allowed for the current tenant.
        
        Args:
            request: The HTTP request object
            
        Returns:
            True if signup is allowed, False otherwise
        """
        # Get the tenant from the request
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            # Check if tenant allows signup
            return tenant.is_active and tenant.status == 'active'
        
        # Fallback to allowing signup
        return True
    
    def save_user(self, request, user, form):
        """
        Save a user with tenant context.
        
        Args:
            request: The HTTP request object
            user: The user instance
            form: The form instance
            
        Returns:
            The saved user instance
        """
        # Get the tenant from the request
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            # Assign the tenant to the user
            user.tenant = tenant
        
        # Save the user
        user.save()
        
        return super().save_user(request, user, form)
    
    def get_connection_context(self, request, provider):
        """
        Get the context for social account connections.
        
        Args:
            request: The HTTP request object
            provider: The social provider
            
        Returns:
            A dictionary with connection context
        """
        # Get the tenant from the request
        tenant = getattr(request, 'tenant', None)
        
        context = super().get_connection_context(request, provider)
        
        if tenant:
            # Add tenant information to the context
            context['tenant'] = tenant
            context['tenant_name'] = tenant.name
            context['tenant_slug'] = tenant.slug
        
        return context


class TenantSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Social account adapter for multi-tenant application.
    
    This adapter customizes django-allauth social account behavior
    to support tenant-specific social authentication.
    """
    
    def pre_social_login(self, request, sociallogin):
        """
        Process a social login before it completes.
        
        Args:
            request: The HTTP request object
            sociallogin: The social login instance
        """
        # Get the tenant from the request
        tenant = getattr(request, 'tenant', None)
        
        if tenant and sociallogin.is_existing:
            # Ensure the user belongs to the current tenant
            user = sociallogin.user
            if hasattr(user, 'tenant') and user.tenant != tenant:
                # Don't allow cross-tenant login
                raise Http404(f"User does not belong to tenant '{tenant.slug}'")
        
        return super().pre_social_login(request, sociallogin)
    
    def get_connect_redirect_url(self, request, socialaccount):
        """
        Get the URL to redirect to after connecting a social account.
        
        Args:
            request: The HTTP request object
            socialaccount: The social account instance
            
        Returns:
            The URL to redirect to
        """
        # Get the tenant from the request
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            # Redirect to tenant-specific home page
            return f"/app/{tenant.slug}/"
        
        # Fallback to default redirect URL
        return settings.LOGIN_REDIRECT_URL
    
    def get_disconnect_redirect_url(self, request, socialaccount):
        """
        Get the URL to redirect to after disconnecting a social account.
        
        Args:
            request: The HTTP request object
            socialaccount: The social account instance
            
        Returns:
            The URL to redirect to
        """
        # Get the tenant from the request
        tenant = getattr(request, 'tenant', None)
        
        if tenant:
            # Redirect to tenant-specific home page
            return f"/app/{tenant.slug}/"
        
        # Fallback to default redirect URL
        return settings.LOGIN_REDIRECT_URL
    
    def validate_disconnect(self, account, accounts):
        """
        Validate disconnecting a social account.
        
        Args:
            account: The social account to disconnect
            accounts: A list of social accounts
            
        Returns:
            True if disconnection is allowed, False otherwise
        """
        # Get the current user from the account
        user = account.user
        
        # Check if the user has a tenant
        if hasattr(user, 'tenant'):
            # Get the tenant
            try:
                tenant = user.tenant
                
                # Check if the tenant allows social account disconnection
                if tenant.status != 'active' or not tenant.is_active:
                    return False
                
                # Check if this is the user's only social account
                if len(accounts) <= 1:
                    # Don't allow disconnecting the only social account
                    # if the tenant requires social authentication
                    if hasattr(tenant.settings, 'require_social_auth') and tenant.settings.require_social_auth:
                        return False
            except Exception:
                # If anything goes wrong, be safe and allow disconnection
                pass
        
        # Allow disconnection
        return True