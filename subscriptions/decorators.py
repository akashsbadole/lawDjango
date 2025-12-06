import functools
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.http import Http404
from django.urls import reverse
from .models import SubscriptionPlan, TenantSubscription
from .services import SubscriptionService


def subscription_required(view_func=None, feature_code=None):
    """
    Decorator to ensure user has an active subscription.
    Optionally checks for specific feature access if feature_code is provided.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not hasattr(request.user, 'tenant') or not request.user.tenant:
                messages.error(request, "You must be associated with a tenant to access this feature.")
                return redirect('account_login')
            
            # Check if tenant has an active subscription
            subscription_status = SubscriptionService.get_subscription_status(request.user.tenant)
            
            if subscription_status['status'] == 'none':
                messages.error(request, "You need an active subscription to access this feature.")
                return redirect('subscriptions:plan_selection')
            elif subscription_status['status'] == 'expired':
                messages.error(request, "Your subscription has expired. Please renew to access this feature.")
                return redirect('subscriptions:subscription_expired')
            elif subscription_status['status'] == 'cancelled':
                messages.error(request, "Your subscription has been cancelled. Please reactivate to access this feature.")
                return redirect('subscriptions:subscription_cancelled')
            
            # If specific feature is required, check access
            if feature_code:
                feature_access = SubscriptionService.can_access_feature(request.user.tenant, feature_code)
                if not feature_access['can_access']:
                    messages.error(request, f"This feature is not available in your current subscription plan. {feature_access.get('reason', '')}")
                    return redirect('subscriptions:subscription_restricted')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    
    if view_func:
        return decorator(view_func)
    return decorator


def plan_required(plan_slug=None, plan_id=None):
    """
    Decorator to ensure user has a specific subscription plan.
    Either plan_slug or plan_id must be provided.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not hasattr(request.user, 'tenant') or not request.user.tenant:
                messages.error(request, "You must be associated with a tenant to access this feature.")
                return redirect('account_login')
            
            # Get the required plan
            if plan_id:
                required_plan = get_object_or_404(SubscriptionPlan, id=plan_id)
            elif plan_slug:
                required_plan = get_object_or_404(SubscriptionPlan, slug=plan_slug)
            else:
                raise ValueError("Either plan_slug or plan_id must be provided")
            
            # Check if tenant has an active subscription with the required plan
            subscription = TenantSubscription.objects.filter(
                tenant=request.user.tenant,
                status__in=['trial', 'active'],
                plan=required_plan
            ).first()
            
            if not subscription:
                messages.error(request, f"This feature requires the {required_plan.name} plan.")
                return redirect('subscriptions:plan_selection')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def usage_limit_check(feature_code, usage_delta=1):
    """
    Decorator to check if usage would exceed limits before processing a view.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not hasattr(request.user, 'tenant') or not request.user.tenant:
                messages.error(request, "You must be associated with a tenant to access this feature.")
                return redirect('account_login')
            
            # Check if usage would exceed limits
            usage_result = SubscriptionService.check_and_update_usage(
                request.user.tenant, feature_code, usage_delta
            )
            
            if not usage_result['success']:
                messages.error(request, usage_result['message'])
                return redirect('subscriptions:subscription_restricted')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def trial_limit_exempt(view_func):
    """
    Decorator to exempt a view from trial limitations.
    """
    @functools.wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request.user, 'tenant') or not request.user.tenant:
            messages.error(request, "You must be associated with a tenant to access this feature.")
            return redirect('account_login')
        
        # Check if tenant is on a trial subscription
        subscription_status = SubscriptionService.get_subscription_status(request.user.tenant)
        
        if subscription_status.get('is_trial', False):
            messages.warning(request, "This feature is not available during the trial period.")
            return redirect('subscriptions:subscription_restricted')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def subscription_feature_required(feature_code):
    """
    Decorator to ensure the subscription includes a specific feature.
    This is different from usage_limit_check as it only checks if the feature is included,
    not if usage limits are exceeded.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not hasattr(request.user, 'tenant') or not request.user.tenant:
                messages.error(request, "You must be associated with a tenant to access this feature.")
                return redirect('account_login')
            
            # Check if feature is included in the subscription plan
            feature_access = SubscriptionService.can_access_feature(request.user.tenant, feature_code)
            
            if not feature_access['can_access']:
                messages.error(request, f"This feature is not included in your current subscription plan. {feature_access.get('reason', '')}")
                return redirect('subscriptions:subscription_restricted')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def admin_subscription_required(view_func):
    """
    Decorator to ensure user has admin access to subscription management.
    """
    @functools.wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request.user, 'tenant') or not request.user.tenant:
            messages.error(request, "You must be associated with a tenant to access this feature.")
            return redirect('account_login')
        
        # Check if user is the tenant owner or has admin role
        if request.user.tenant.owner != request.user and request.user.role != 'admin':
            messages.error(request, "You don't have permission to manage subscription settings.")
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view