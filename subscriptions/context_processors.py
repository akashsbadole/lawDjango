from django.utils import timezone


def subscription_context(request):
    """
    Add subscription information to the context for all templates.
    """
    context = {}
    
    # Only add subscription info for authenticated users with a tenant
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return context
    
    if not hasattr(request.user, 'tenant') or not request.user.tenant:
        return context
    
    try:
        from .models import TenantSubscription, UsageRecord
        from .utils import get_usage_percentage
        
        tenant = request.user.tenant
        
        # Get current subscription
        subscription = TenantSubscription.objects.current_for_tenant(tenant)
        
        if subscription:
            context['subscription'] = subscription
            
            # Calculate days until renewal
            if subscription.end_date:
                days_until_renewal = (subscription.end_date - timezone.now().date()).days
                context['days_until_renewal'] = days_until_renewal
                
                # Add warning if renewal is soon
                if days_until_renewal <= 7:
                    context['renewal_soon'] = True
            
            # Check if subscription is in trial
            context['is_trial'] = subscription.status == TenantSubscription.TRIAL
            
            # Get usage information
            if subscription.plan:
                # User usage
                if subscription.plan.max_users:
                    user_usage = get_usage_percentage(
                        tenant, 'users', subscription.plan.max_users
                    )
                    context['user_usage'] = user_usage
                
                # Storage usage
                if subscription.plan.max_storage_mb:
                    storage_usage = get_usage_percentage(
                        tenant, 'storage', subscription.plan.max_storage_mb
                    )
                    context['storage_usage'] = storage_usage
                
                # Get all usage records
                usage_records = UsageRecord.objects.for_tenant(tenant).select_related('feature')
                context['usage_records'] = usage_records
        
        # Add any subscription notifications from middleware
        if hasattr(request, 'subscription_notifications'):
            context['subscription_notifications'] = request.subscription_notifications
        
        # Add available plans for upgrade
        from .models import SubscriptionPlan
        if subscription and subscription.plan:
            available_plans = SubscriptionPlan.objects.public().exclude(
                id=subscription.plan.id
            ).order_by('price')
            context['available_plans'] = available_plans
        elif not subscription:
            # No subscription yet, show all plans
            context['available_plans'] = SubscriptionPlan.objects.public().order_by('price')
    
    except Exception as e:
        # Silently fail to avoid breaking templates
        pass
    
    return context