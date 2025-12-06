from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from .services import SubscriptionService


class SubscriptionRequiredMixin:
    """
    Mixin to ensure user has an active subscription.
    """
    def dispatch(self, request, *args, **kwargs):
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
        
        return super().dispatch(request, *args, **kwargs)


class SubscriptionFeatureMixin:
    """
    Mixin to ensure user's subscription includes a specific feature.
    """
    feature_code = None
    
    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'tenant') or not request.user.tenant:
            messages.error(request, "You must be associated with a tenant to access this feature.")
            return redirect('account_login')
        
        if not self.feature_code:
            raise ValueError("feature_code must be set in the view")
        
        # Check if feature is included in subscription plan
        feature_access = SubscriptionService.can_access_feature(request.user.tenant, self.feature_code)
        
        if not feature_access['can_access']:
            messages.error(request, f"This feature is not available in your current subscription plan. {feature_access.get('reason', '')}")
            return redirect('subscriptions:subscription_restricted')
        
        return super().dispatch(request, *args, **kwargs)


class SubscriptionUsageMixin:
    """
    Mixin to check if usage would exceed limits before processing a view.
    """
    feature_code = None
    usage_delta = 1
    
    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'tenant') or not request.user.tenant:
            messages.error(request, "You must be associated with a tenant to access this feature.")
            return redirect('account_login')
        
        if not self.feature_code:
            raise ValueError("feature_code must be set in the view")
        
        # Check if usage would exceed limits
        usage_result = SubscriptionService.check_and_update_usage(
            request.user.tenant, self.feature_code, self.usage_delta
        )
        
        if not usage_result['success']:
            messages.error(request, usage_result['message'])
            return redirect('subscriptions:subscription_restricted')
        
        return super().dispatch(request, *args, **kwargs)


class TrialLimitMixin:
    """
    Mixin to exempt a view from trial limitations.
    """
    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'tenant') or not request.user.tenant:
            messages.error(request, "You must be associated with a tenant to access this feature.")
            return redirect('account_login')
        
        # Check if tenant is on a trial subscription
        subscription_status = SubscriptionService.get_subscription_status(request.user.tenant)
        
        if subscription_status.get('is_trial', False):
            messages.warning(request, "This feature is not available during trial period.")
            return redirect('subscriptions:subscription_restricted')
        
        return super().dispatch(request, *args, **kwargs)


class AdminSubscriptionMixin:
    """
    Mixin to ensure user has admin access to subscription management.
    """
    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'tenant') or not request.user.tenant:
            messages.error(request, "You must be associated with a tenant to access this feature.")
            return redirect('account_login')
        
        # Check if user is tenant owner or has admin role
        if request.user.tenant.owner != request.user and request.user.role != 'admin':
            messages.error(request, "You don't have permission to manage subscription settings.")
            return redirect('dashboard')
        
        return super().dispatch(request, *args, **kwargs)


class SubscriptionContextMixin:
    """
    Mixin to add subscription context to the view.
    """
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if hasattr(self.request, 'user') and hasattr(self.request.user, 'tenant') and self.request.user.tenant:
            # Add subscription status to context
            subscription_status = SubscriptionService.get_subscription_status(self.request.user.tenant)
            context.update(subscription_status)
            
            # Add subscription object to context
            from .models import TenantSubscription
            subscription = TenantSubscription.objects.filter(
                tenant=self.request.user.tenant,
                status__in=['trial', 'active']
            ).first()
            
            if subscription:
                context['subscription'] = subscription
                context['plan'] = subscription.plan
                context['plan_features'] = subscription.plan.plan_features.select_related('feature').all()
        
        return context


class SubscriptionPlanMixin:
    """
    Mixin to ensure user has a specific subscription plan.
    """
    plan_slug = None
    plan_id = None
    
    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'tenant') or not request.user.tenant:
            messages.error(request, "You must be associated with a tenant to access this feature.")
            return redirect('account_login')
        
        if not self.plan_slug and not self.plan_id:
            raise ValueError("Either plan_slug or plan_id must be set in the view")
        
        # Get required plan
        from .models import SubscriptionPlan
        if self.plan_id:
            required_plan = SubscriptionPlan.objects.get(id=self.plan_id)
        else:
            required_plan = SubscriptionPlan.objects.get(slug=self.plan_slug)
        
        # Check if tenant has an active subscription with required plan
        from .models import TenantSubscription
        subscription = TenantSubscription.objects.filter(
            tenant=request.user.tenant,
            status__in=['trial', 'active'],
            plan=required_plan
        ).first()
        
        if not subscription:
            messages.error(request, f"This feature requires {required_plan.name} plan.")
            return redirect('subscriptions:plan_selection')
        
        return super().dispatch(request, *args, **kwargs)


class SubscriptionUsageCheckMixin:
    """
    Mixin to check usage limits without updating them.
    Useful for views that need to check limits but don't increment usage.
    """
    feature_code = None
    
    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'tenant') or not request.user.tenant:
            messages.error(request, "You must be associated with a tenant to access this feature.")
            return redirect('account_login')
        
        if not self.feature_code:
            raise ValueError("feature_code must be set in the view")
        
        # Check if feature is included in subscription plan
        feature_access = SubscriptionService.can_access_feature(request.user.tenant, self.feature_code)
        
        if not feature_access['can_access']:
            messages.error(request, f"This feature is not available in your current subscription plan. {feature_access.get('reason', '')}")
            return redirect('subscriptions:subscription_restricted')
        
        return super().dispatch(request, *args, **kwargs)