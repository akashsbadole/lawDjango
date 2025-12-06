from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.conf import settings
from decimal import Decimal
import uuid
from .managers import (
    SubscriptionPlanManager, TenantSubscriptionManager, InvoiceManager,
    PaymentManager, UsageRecordManager, SubscriptionEventManager
)


class SubscriptionPlan(models.Model):
    """
    Model representing subscription plans available to tenants.
    """
    PLAN_TYPES = [
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('professional', 'Professional'),
        ('enterprise', 'Enterprise'),
    ]
    
    BILLING_CYCLES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES)
    description = models.TextField()
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CYCLES)
    max_users = models.IntegerField(default=3)
    max_storage_mb = models.IntegerField(default=100)
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)
    trial_days = models.IntegerField(default=0)
    setup_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = SubscriptionPlanManager()
    
    class Meta:
        db_table = 'subscription_plans'
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'
        ordering = ['price', 'name']
    
    def __str__(self):
        return f"{self.name} (${self.price}/{self.billing_cycle})"
    
    @property
    def yearly_price(self):
        """Calculate yearly price for monthly plans."""
        if self.billing_cycle == 'monthly':
            return self.price * 12
        return self.price
    
    @property
    def monthly_price(self):
        """Calculate monthly price for yearly plans."""
        if self.billing_cycle == 'yearly':
            return self.price / 12
        return self.price


class SubscriptionFeature(models.Model):
    """
    Model representing features that can be included in subscription plans.
    """
    FEATURE_TYPES = [
        ('boolean', 'Yes/No'),
        ('number', 'Numeric Limit'),
        ('text', 'Text Value'),
    ]
    
    name = models.CharField(max_length=100)
    code = models.SlugField(max_length=100, unique=True)
    description = models.TextField()
    feature_type = models.CharField(max_length=20, choices=FEATURE_TYPES)
    default_value = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = models.Manager()  # Default manager
    
    class Meta:
        db_table = 'subscription_features'
        verbose_name = 'Subscription Feature'
        verbose_name_plural = 'Subscription Features'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class PlanFeature(models.Model):
    """
    Model linking features to subscription plans with specific values.
    """
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.CASCADE,
        related_name='plan_features'
    )
    feature = models.ForeignKey(
        SubscriptionFeature,
        on_delete=models.CASCADE,
        related_name='plan_features'
    )
    value = models.TextField()
    is_included = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = models.Manager()  # Default manager
    
    class Meta:
        db_table = 'plan_features'
        verbose_name = 'Plan Feature'
        verbose_name_plural = 'Plan Features'
        unique_together = ['plan', 'feature']
    
    def __str__(self):
        status = "Included" if self.is_included else "Not Included"
        return f"{self.plan.name} - {self.feature.name}: {status}"


class PaymentMethod(models.Model):
    """
    Model representing payment methods for tenants.
    """
    METHOD_TYPES = [
        ('credit_card', 'Credit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('paypal', 'PayPal'),
        ('stripe', 'Stripe'),
        ('check', 'Check'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='payment_methods'
    )
    method_type = models.CharField(max_length=20, choices=METHOD_TYPES)
    details = models.JSONField(default=dict)  # Store payment method details
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    stripe_payment_method_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = models.Manager()  # Default manager
    
    class Meta:
        db_table = 'payment_methods'
        verbose_name = 'Payment Method'
        verbose_name_plural = 'Payment Methods'
        ordering = ['-is_default', '-created_at']
    
    def __str__(self):
        return f"{self.tenant.name} - {self.get_method_type_display()}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default payment method per tenant
        if self.is_default:
            PaymentMethod.objects.filter(
                tenant=self.tenant, 
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class TenantSubscription(models.Model):
    """
    Model representing a tenant's subscription to a plan.
    """
    STATUS_CHOICES = [
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='subscriptions'
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        related_name='tenant_subscriptions'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    trial_end_date = models.DateTimeField(null=True, blank=True)
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subscriptions'
    )
    stripe_subscription_id = models.CharField(max_length=255, blank=True, null=True)
    auto_renew = models.BooleanField(default=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = TenantSubscriptionManager()
    
    class Meta:
        db_table = 'tenant_subscriptions'
        verbose_name = 'Tenant Subscription'
        verbose_name_plural = 'Tenant Subscriptions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.tenant.name} - {self.plan.name if self.plan else 'No Plan'} ({self.status})"
    
    @property
    def is_active(self):
        """Check if subscription is currently active."""
        now = timezone.now()
        if self.status == 'cancelled':
            return False
        if self.status == 'expired':
            return False
        if self.status == 'past_due':
            return True  # Still active but needs payment
        if self.trial_end_date and now < self.trial_end_date:
            return True
        if self.end_date and now > self.end_date:
            return False
        return self.status in ['trial', 'active']
    
    @property
    def is_trial(self):
        """Check if subscription is in trial period."""
        if not self.trial_end_date:
            return False
        return timezone.now() < self.trial_end_date
    
    @property
    def days_until_expiry(self):
        """Calculate days until subscription expires."""
        if not self.end_date:
            return None
        delta = self.end_date - timezone.now()
        return max(0, delta.days)
    
    @property
    def days_until_trial_end(self):
        """Calculate days until trial ends."""
        if not self.trial_end_date:
            return None
        delta = self.trial_end_date - timezone.now()
        return max(0, delta.days)
    
    def extend_subscription(self, days):
        """Extend subscription by specified number of days."""
        if self.end_date:
            self.end_date += timezone.timedelta(days=days)
        else:
            self.end_date = timezone.now() + timezone.timedelta(days=days)
        self.save()


class Invoice(models.Model):
    """
    Model representing invoices for subscription billing.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]
    
    INVOICE_TYPES = [
        ('subscription', 'Subscription'),
        ('setup_fee', 'Setup Fee'),
        ('overage', 'Overage'),
        ('other', 'Other'),
    ]
    
    invoice_number = models.CharField(max_length=50, unique=True)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='subscription_invoices'
    )
    subscription = models.ForeignKey(
        TenantSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices'
    )
    invoice_type = models.CharField(max_length=20, choices=INVOICE_TYPES, default='subscription')
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    subtotal = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=Decimal('0.00')
    )
    tax_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=4,
        default=Decimal('0.0000')
    )
    tax_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=Decimal('0.00')
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    description = models.TextField(blank=True, null=True)
    stripe_invoice_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = InvoiceManager()
    
    class Meta:
        db_table = 'subscription_invoices'
        verbose_name = 'Subscription Invoice'
        verbose_name_plural = 'Subscription Invoices'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.tenant.name}"
    
    @property
    def is_overdue(self):
        """Check if the invoice is overdue."""
        return (
            self.due_date < timezone.now().date() and 
            self.status in ['draft', 'sent']
        )
    
    def calculate_totals(self):
        """Calculate subtotal, tax, and total."""
        self.tax_amount = self.subtotal * self.tax_rate
        self.total_amount = self.subtotal + self.tax_amount
        self.save()


class Payment(models.Model):
    """
    Model representing payments for subscription invoices.
    """
    PAYMENT_METHODS = [
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('bank_transfer', 'Bank Transfer'),
        ('check', 'Check'),
        ('other', 'Other'),
    ]
    
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    payment_date = models.DateTimeField(default=timezone.now)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = PaymentManager()
    
    class Meta:
        db_table = 'subscription_payments'
        verbose_name = 'Subscription Payment'
        verbose_name_plural = 'Subscription Payments'
        ordering = ['-payment_date', '-created_at']
    
    def __str__(self):
        return f"Payment of ${self.amount} for Invoice {self.invoice.invoice_number}"


class UsageRecord(models.Model):
    """
    Model tracking usage of subscription features.
    """
    PERIOD_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='usage_records'
    )
    feature = models.ForeignKey(
        SubscriptionFeature,
        on_delete=models.CASCADE,
        related_name='usage_records'
    )
    current_usage = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        default=Decimal('0.00')
    )
    limit = models.DecimalField(
        max_digits=15, 
        decimal_places=2,
        null=True,
        blank=True
    )
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES, default='monthly')
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UsageRecordManager()
    
    class Meta:
        db_table = 'usage_records'
        verbose_name = 'Usage Record'
        verbose_name_plural = 'Usage Records'
        unique_together = ['tenant', 'feature', 'period', 'period_start']
        ordering = ['-period_start', 'tenant', 'feature']
    
    def __str__(self):
        return f"{self.tenant.name} - {self.feature.name}: {self.current_usage}/{self.limit or '∞'}"
    
    @property
    def usage_percentage(self):
        """Calculate usage as percentage of limit."""
        if not self.limit or self.limit == 0:
            return 0
        return min(100, (self.current_usage / self.limit) * 100)
    
    @property
    def is_over_limit(self):
        """Check if usage exceeds limit."""
        if not self.limit:
            return False
        return self.current_usage > self.limit
    
    @property
    def remaining(self):
        """Calculate remaining usage."""
        if not self.limit:
            return None
        return max(0, self.limit - self.current_usage)


class SubscriptionEvent(models.Model):
    """
    Model tracking subscription events for audit purposes.
    """
    EVENT_TYPES = [
        ('created', 'Subscription Created'),
        ('updated', 'Subscription Updated'),
        ('cancelled', 'Subscription Cancelled'),
        ('renewed', 'Subscription Renewed'),
        ('payment_failed', 'Payment Failed'),
        ('payment_succeeded', 'Payment Succeeded'),
        ('trial_started', 'Trial Started'),
        ('trial_ended', 'Trial Ended'),
        ('plan_changed', 'Plan Changed'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='subscription_events'
    )
    subscription = models.ForeignKey(
        TenantSubscription,
        on_delete=models.CASCADE,
        related_name='events'
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    description = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    objects = SubscriptionEventManager()
    
    class Meta:
        db_table = 'subscription_events'
        verbose_name = 'Subscription Event'
        verbose_name_plural = 'Subscription Events'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.tenant.name} - {self.get_event_type_display()}"
