from django.db import models
from django.utils import timezone
from django.db.models import Q


class SubscriptionPlanManager(models.Manager):
    """
    Manager for SubscriptionPlan model.
    """
    def active(self):
        """Get all active subscription plans."""
        return self.filter(is_active=True)
    
    def public(self):
        """Get all public subscription plans."""
        return self.filter(is_public=True, is_active=True)
    
    def by_type(self, plan_type):
        """Get plans by type."""
        return self.filter(plan_type=plan_type, is_active=True)
    
    def by_billing_cycle(self, cycle):
        """Get plans by billing cycle."""
        return self.filter(billing_cycle=cycle, is_active=True)


class TenantSubscriptionManager(models.Manager):
    """
    Manager for TenantSubscription model.
    """
    def active(self):
        """Get all active subscriptions."""
        return self.filter(
            Q(status='active') | 
            Q(status='trial') | 
            Q(status='past_due')
        ).filter(
            Q(end_date__gte=timezone.now()) | Q(end_date__isnull=True)
        )
    
    def expired(self):
        """Get all expired subscriptions."""
        return self.filter(
            Q(end_date__lt=timezone.now()) |
            Q(status='expired') |
            Q(status='cancelled')
        )
    
    def trialing(self):
        """Get all subscriptions in trial period."""
        return self.filter(
            status='trial',
            trial_end_date__gte=timezone.now()
        )
    
    def past_due(self):
        """Get all past due subscriptions."""
        return self.filter(status='past_due')
    
    def for_tenant(self, tenant):
        """Get subscriptions for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def current_for_tenant(self, tenant):
        """Get current subscription for a tenant."""
        return self.filter(
            tenant=tenant,
            status__in=['active', 'trial', 'past_due']
        ).filter(
            Q(end_date__gte=timezone.now()) | Q(end_date__isnull=True)
        ).first()


class InvoiceManager(models.Manager):
    """
    Manager for Invoice model.
    """
    def for_tenant(self, tenant):
        """Get invoices for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def unpaid(self, tenant=None):
        """Get unpaid invoices."""
        queryset = self.filter(status__in=['draft', 'sent'])
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def overdue(self, tenant=None):
        """Get overdue invoices."""
        queryset = self.filter(
            status__in=['draft', 'sent'],
            due_date__lt=timezone.now().date()
        )
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def paid(self, tenant=None):
        """Get paid invoices."""
        queryset = self.filter(status='paid')
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset


class PaymentManager(models.Manager):
    """
    Manager for Payment model.
    """
    def for_tenant(self, tenant):
        """Get payments for a specific tenant."""
        return self.filter(invoice__tenant=tenant)
    
    def successful(self, tenant=None):
        """Get successful payments."""
        queryset = self.filter(status='completed')
        if tenant:
            queryset = queryset.filter(invoice__tenant=tenant)
        return queryset
    
    def failed(self, tenant=None):
        """Get failed payments."""
        queryset = self.filter(status='failed')
        if tenant:
            queryset = queryset.filter(invoice__tenant=tenant)
        return queryset
    
    def pending(self, tenant=None):
        """Get pending payments."""
        queryset = self.filter(status__in=['pending', 'processing'])
        if tenant:
            queryset = queryset.filter(invoice__tenant=tenant)
        return queryset


class UsageRecordManager(models.Manager):
    """
    Manager for UsageRecord model.
    """
    def for_tenant(self, tenant):
        """Get usage records for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def for_feature(self, feature):
        """Get usage records for a specific feature."""
        return self.filter(feature=feature)
    
    def current_period(self, tenant, feature, period='monthly'):
        """Get usage record for current period."""
        now = timezone.now()
        
        if period == 'daily':
            period_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            period_end = period_start + timezone.timedelta(days=1)
        elif period == 'weekly':
            # Start of week (Monday)
            period_start = now - timezone.timedelta(days=now.weekday())
            period_start = period_start.replace(hour=0, minute=0, second=0, microsecond=0)
            period_end = period_start + timezone.timedelta(days=7)
        elif period == 'monthly':
            period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # Calculate first day of next month
            if period_start.month == 12:
                period_end = period_start.replace(year=period_start.year + 1, month=1)
            else:
                period_end = period_start.replace(month=period_start.month + 1)
        elif period == 'yearly':
            period_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            period_end = period_start.replace(year=period_start.year + 1)
        else:
            period_start = now
            period_end = now + timezone.timedelta(days=1)
        
        record, created = self.get_or_create(
            tenant=tenant,
            feature=feature,
            period=period,
            period_start=period_start,
            defaults={
                'period_end': period_end,
                'current_usage': 0,
            }
        )
        
        return record
    
    def over_limit(self, tenant=None):
        """Get usage records that are over limit."""
        queryset = self.filter(
            limit__isnull=False,
            current_usage__gt=models.F('limit')
        )
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def update_usage(self, tenant, feature_code, usage_delta, period='monthly'):
        """Update usage for a specific feature."""
        from .models import SubscriptionFeature
        
        try:
            feature = SubscriptionFeature.objects.get(code=feature_code)
        except SubscriptionFeature.DoesNotExist:
            return None
        
        record = self.current_period(tenant, feature, period)
        record.current_usage += usage_delta
        record.save()
        
        return record


class SubscriptionEventManager(models.Manager):
    """
    Manager for SubscriptionEvent model.
    """
    def for_tenant(self, tenant):
        """Get events for a specific tenant."""
        return self.filter(tenant=tenant)
    
    def for_subscription(self, subscription):
        """Get events for a specific subscription."""
        return self.filter(subscription=subscription)
    
    def by_type(self, event_type):
        """Get events by type."""
        return self.filter(event_type=event_type)
    
    def recent(self, tenant=None, days=30):
        """Get recent events."""
        since = timezone.now() - timezone.timedelta(days=days)
        queryset = self.filter(created_at__gte=since)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def log_event(self, tenant, subscription, event_type, description, metadata=None):
        """Log a subscription event."""
        return self.create(
            tenant=tenant,
            subscription=subscription,
            event_type=event_type,
            description=description,
            metadata=metadata or {}
        )