from django import template
from django.utils import timezone
from ..models import TenantSubscription, UsageRecord
from ..services import SubscriptionService

register = template.Library()


@register.simple_tag
def subscription_status(tenant):
    """Get subscription status for a tenant"""
    status = SubscriptionService.get_subscription_status(tenant)
    return status.get('status', 'none')


@register.simple_tag
def subscription_plan(tenant):
    """Get subscription plan name for a tenant"""
    subscription = TenantSubscription.objects.filter(
        tenant=tenant,
        status__in=['trial', 'active']
    ).first()
    
    if subscription:
        return subscription.plan.name
    return 'No Subscription'


@register.simple_tag
def days_remaining(tenant):
    """Get days remaining in subscription"""
    subscription = TenantSubscription.objects.filter(
        tenant=tenant,
        status__in=['trial', 'active']
    ).first()
    
    if subscription and subscription.end_date:
        days = (subscription.end_date - timezone.now().date()).days
        return max(0, days)
    return 0


@register.simple_tag
def is_trial(tenant):
    """Check if tenant is on trial"""
    subscription = TenantSubscription.objects.filter(
        tenant=tenant,
        status='trial'
    ).first()
    
    return subscription is not None


@register.simple_tag
def is_active(tenant):
    """Check if tenant has active subscription"""
    subscription = TenantSubscription.objects.filter(
        tenant=tenant,
        status='active'
    ).first()
    
    return subscription is not None


@register.simple_tag
def subscription_feature_limit(tenant, feature_code):
    """Get feature limit for tenant's subscription"""
    subscription = TenantSubscription.objects.filter(
        tenant=tenant,
        status__in=['trial', 'active']
    ).first()
    
    if not subscription:
        return 0
    
    plan_feature = subscription.plan.plan_features.filter(
        feature__code=feature_code
    ).first()
    
    if plan_feature and plan_feature.value and plan_feature.value.isdigit():
        return int(plan_feature.value)
    
    return 0


@register.simple_tag
def subscription_feature_usage(tenant, feature_code):
    """Get current usage for a feature"""
    usage_record = UsageRecord.objects.filter(
        tenant=tenant,
        feature__code=feature_code
    ).first()
    
    if usage_record:
        return usage_record.current_usage
    return 0


@register.simple_tag
def subscription_usage_percentage(tenant, feature_code):
    """Get usage percentage for a feature"""
    limit = subscription_feature_limit(tenant, feature_code)
    usage = subscription_feature_usage(tenant, feature_code)
    
    if limit > 0:
        return (usage / limit) * 100
    return 0


@register.simple_tag
def subscription_usage_status(tenant, feature_code):
    """Get usage status for a feature (ok, warning, critical)"""
    percentage = subscription_usage_percentage(tenant, feature_code)
    
    if percentage >= 90:
        return 'critical'
    elif percentage >= 75:
        return 'warning'
    return 'ok'


@register.simple_tag
def can_add_user(tenant):
    """Check if tenant can add more users"""
    return SubscriptionService.can_access_feature(tenant, 'users')


@register.simple_tag
def can_upload_file(tenant, file_size_mb=0):
    """Check if tenant can upload a file of given size"""
    # Check storage limit
    subscription_status = SubscriptionService.get_subscription_status(tenant)
    
    if subscription_status.get('status') not in ['trial', 'active']:
        return False
    
    # Find storage usage in usage summary
    storage_usage = None
    for usage in subscription_status.get('usage_summary', []):
        if usage['feature_code'] == 'storage':
            storage_usage = usage
            break
    
    if not storage_usage:
        return True  # No limit found, assume unlimited
    
    # Convert MB to bytes for comparison
    current_usage_mb = storage_usage['current_usage']
    limit_mb = storage_usage['limit']
    
    return (current_usage_mb + file_size_mb) <= limit_mb


@register.simple_tag
def subscription_badge_class(tenant):
    """Get CSS class for subscription status badge"""
    status = subscription_status(tenant)
    
    if status == 'active':
        return 'bg-success'
    elif status == 'trial':
        return 'bg-info'
    elif status == 'cancelled':
        return 'bg-warning'
    elif status == 'expired':
        return 'bg-danger'
    else:
        return 'bg-secondary'


@register.simple_tag
def subscription_progress_class(tenant, feature_code):
    """Get CSS class for usage progress bar"""
    status = subscription_usage_status(tenant, feature_code)
    
    if status == 'critical':
        return 'bg-danger'
    elif status == 'warning':
        return 'bg-warning'
    else:
        return 'bg-success'


@register.simple_tag
def subscription_next_billing_date(tenant):
    """Get next billing date for tenant"""
    subscription = TenantSubscription.objects.filter(
        tenant=tenant,
        status__in=['trial', 'active']
    ).first()
    
    if subscription and subscription.end_date:
        return subscription.end_date.strftime('%B %d, %Y')
    return 'N/A'


@register.simple_tag
def subscription_price(tenant):
    """Get subscription price for tenant"""
    subscription = TenantSubscription.objects.filter(
        tenant=tenant,
        status__in=['trial', 'active']
    ).first()
    
    if subscription:
        return f"${subscription.plan.price}/{subscription.plan.get_billing_cycle_display()}"
    return 'N/A'


@register.simple_tag
def subscription_features(tenant):
    """Get all features for tenant's subscription"""
    subscription = TenantSubscription.objects.filter(
        tenant=tenant,
        status__in=['trial', 'active']
    ).first()
    
    if not subscription:
        return []
    
    return subscription.plan.plan_features.select_related('feature').all()


@register.simple_tag
def has_subscription_feature(tenant, feature_code):
    """Check if tenant's subscription includes a specific feature"""
    return SubscriptionService.can_access_feature(tenant, feature_code)['can_access']


@register.simple_tag
def subscription_alerts(tenant):
    """Get subscription alerts for a tenant"""
    alerts = []
    subscription_status = SubscriptionService.get_subscription_status(tenant)
    
    # Check for expired subscription
    if subscription_status.get('status') == 'expired':
        alerts.append({
            'type': 'danger',
            'message': 'Your subscription has expired. Please renew to continue using our services.'
        })
    # Check for cancelled subscription
    elif subscription_status.get('status') == 'cancelled':
        alerts.append({
            'type': 'warning',
            'message': 'Your subscription has been cancelled. You will lose access to premium features soon.'
        })
    # Check for trial ending soon
    elif subscription_status.get('is_trial'):
        days_left = subscription_status.get('days_remaining', 0)
        if days_left <= 3:
            alerts.append({
                'type': 'warning',
                'message': f'Your trial expires in {days_left} day(s). Upgrade to continue using our services.'
            })
    # Check for usage limits
    for usage in subscription_status.get('usage_summary', []):
        if usage['status'] == 'critical':
            alerts.append({
                'type': 'danger',
                'message': f'You have reached your limit for {usage["feature_name"]}. Upgrade your plan to continue using this feature.'
            })
        elif usage['status'] == 'warning':
            alerts.append({
                'type': 'warning',
                'message': f'You are approaching your limit for {usage["feature_name"]}. Consider upgrading your plan.'
            })
    
    return alerts