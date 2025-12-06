"""
Core middleware for common functionality.
"""

import logging
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class RedirectLoopDetectionMiddleware:
    """
    Middleware to detect and prevent redirect loops.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Initialize or get redirect counter from session
        redirect_count = request.session.get('redirect_count', 0)
        last_redirect_url = request.session.get('last_redirect_url', '')
        
        # Check if we're redirecting to the same URL repeatedly
        current_url = request.get_full_path()
        
        # If we've redirected to the same URL more than 3 times, break the loop
        if (redirect_count > 3 and 
            current_url == last_redirect_url and 
            request.method == 'GET'):
            
            logger.warning(
                f"Redirect loop detected for URL: {current_url}, "
                f"User: {request.user if request.user.is_authenticated else 'Anonymous'}"
            )
            
            # Clear redirect tracking
            request.session['redirect_count'] = 0
            request.session['last_redirect_url'] = ''
            request.session.save()
            
            # Return a safe response to break the loop
            return self._get_safe_response(request)
        
        # Get the response
        response = self.get_response(request)
        
        # Track redirects
        if hasattr(response, 'url') and response.url:  # HttpResponseRedirect
            # Increment redirect count
            request.session['redirect_count'] = redirect_count + 1
            request.session['last_redirect_url'] = response.url
            request.session.save()
            
            # Log the redirect for debugging
            logger.info(
                f"Redirect #{redirect_count + 1}: {current_url} -> {response.url}, "
                f"User: {request.user if request.user.is_authenticated else 'Anonymous'}"
            )
        else:
            # Reset redirect count on successful response
            if redirect_count > 0:
                request.session['redirect_count'] = 0
                request.session['last_redirect_url'] = ''
                request.session.save()
        
        return response
    
    def _get_safe_response(self, request):
        """
        Return a safe response to break redirect loops.
        """
        # Check if user is authenticated before accessing user attribute
        is_authenticated = hasattr(request, 'user') and request.user.is_authenticated
        
        if is_authenticated:
            # For authenticated users, show an error page
            from django.shortcuts import render
            return render(request, 'core/redirect_loop_error.html', {
                'user': request.user,
                'title': 'Redirect Loop Detected'
            })
        else:
            # For anonymous users, redirect to login with a clear message
            from django.contrib import messages
            messages.error(
                request,
                "A redirect loop was detected. Please try logging in again."
            )
            return redirect('accounts:login')


class TenantContextMiddleware:
    """
    Middleware to ensure tenant context is available for all authenticated users.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only process for authenticated users
        # Check if user is authenticated before accessing user attribute
        is_authenticated = hasattr(request, 'user') and request.user.is_authenticated
        
        if not is_authenticated:
            response = self.get_response(request)
            return response
        
        # If tenant is not set and user has a tenant, set it
        if not hasattr(request, 'tenant') and hasattr(request.user, 'tenant'):
            if request.user.tenant:
                request.tenant = request.user.tenant
        
        response = self.get_response(request)
        return response