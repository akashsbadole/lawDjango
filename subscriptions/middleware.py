import logging
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)


class SubscriptionMiddleware:
    """
    Middleware to check subscription status and enforce limits.
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip subscription check for certain URLs
        skip_paths = [
            '/subscriptions/',
            '/account/',
            '/admin/',
            '/static/',
            '/media/',
            '/accounts/login/',
            '/accounts/logout/',
        ]
        
        if request.path.startswith(tuple(skip_paths)):
            response = self.get_response(request)
            return response
        
        # Only check for authenticated users
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            response = self.get_response(request)
            return response
        
        # Get tenant from request (set by middleware) or from user
        tenant = getattr(request, 'tenant', None)
        if not tenant and hasattr(request.user, 'tenant'):
            tenant = request.user.tenant
        
        # Only check for users with a tenant
        if not tenant:
            response = self.get_response(request)
            return response
        
        try:
            from .models import TenantSubscription
            from .utils import check_subscription_limits
            
            subscription = TenantSubscription.objects.current_for_tenant(tenant)
            
            # Skip check if no subscription (will be handled by views)
            if not subscription:
                response = self.get_response(request)
                return response
            
            # Check if subscription is expired
            if not subscription.is_active:
                # Only show message and redirect if not already on subscription page
                if not request.path.startswith('/subscriptions/'):
                    messages.warning(
                        request,
                        "Your subscription has expired. Please renew to continue using the service."
                    )
                    return redirect('subscriptions:plan_selection')
                else:
                    # Already on subscription page, don't redirect again
                    response = self.get_response(request)
                    return response
            
            # Check usage limits
            notifications = check_subscription_limits(tenant)
            
            # Add notifications to request for display in templates
            if notifications:
                request.subscription_notifications = notifications
            
            response = self.get_response(request)
            return response
            
        except Exception as e:
            logger.error(f"Error in subscription middleware: {str(e)}")
            response = self.get_response(request)
            return response