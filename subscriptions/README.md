# Subscriptions App

This app provides comprehensive subscription management functionality for the multi-tenant law firm management system.

## Features

- Subscription plan management with flexible pricing and billing cycles
- Feature-based plan configuration with limits
- Payment method management with support for multiple payment providers
- Invoice generation and payment tracking
- Usage tracking and limit enforcement
- Automated subscription lifecycle management
- Email notifications for subscription events
- Middleware for subscription validation
- Template tags for subscription information
- Decorators and mixins for easy integration

## Models

### SubscriptionPlan
Defines available subscription plans with pricing, billing cycles, and limits.

Fields:
- `name`: Plan name
- `slug`: URL-friendly slug
- `price`: Monthly/yearly price
- `billing_cycle`: 'monthly' or 'yearly'
- `max_users`: Maximum number of users
- `max_storage_mb`: Storage limit in MB
- `max_cases`: Maximum number of cases
- `is_active`: Whether plan is available
- `is_public`: Whether plan is shown to all tenants

### SubscriptionFeature
Defines features that can be included in plans.

Fields:
- `name`: Feature name
- `code`: Unique code for reference
- `description`: Feature description

### PlanFeature
Links features to plans with specific values.

Fields:
- `plan`: Related subscription plan
- `feature`: Related subscription feature
- `value`: Feature limit or value
- `is_included`: Whether feature is included

### PaymentMethod
Stores payment methods for tenants.

Fields:
- `tenant`: Related tenant
- `method_type`: 'card', 'bank', etc.
- `details`: Payment method details (encrypted)
- `is_default`: Default payment method
- `is_active`: Whether method is active

### TenantSubscription
Tracks tenant subscriptions with status and dates.

Fields:
- `tenant`: Related tenant
- `plan`: Current subscription plan
- `start_date`: Subscription start date
- `end_date`: Subscription end date
- `status`: 'trial', 'active', 'past_due', 'cancelled', 'expired'
- `cancelled_at`: Cancellation date
- `payment_method`: Default payment method

### Invoice
Models subscription billing invoices.

Fields:
- `subscription`: Related subscription
- `invoice_number`: Unique invoice number
- `issue_date`: Invoice issue date
- `due_date`: Payment due date
- `subtotal`: Subtotal amount
- `tax_rate`: Tax rate
- `tax_amount`: Tax amount
- `total_amount`: Total amount
- `status`: 'pending', 'paid', 'overdue'
- `paid_date`: Payment date

### Payment
Tracks payments for invoices.

Fields:
- `invoice`: Related invoice
- `amount`: Payment amount
- `payment_method`: Payment method used
- `transaction_id`: External transaction ID
- `status`: 'pending', 'success', 'failed'
- `payment_date`: Payment date

### UsageRecord
Tracks feature usage with limits.

Fields:
- `tenant`: Related tenant
- `feature`: Related feature
- `current_usage`: Current usage amount
- `period_start`: Usage period start
- `period_end`: Usage period end

### SubscriptionEvent
Logs subscription events for audit trail.

Fields:
- `tenant`: Related tenant
- `subscription`: Related subscription
- `event_type`: Event type
- `description`: Event description
- `old_status`: Previous status
- `new_status`: New status
- `metadata`: Additional event data

## Managers

### SubscriptionPlanManager
Methods:
- `active()`: Get active plans
- `public()`: Get public plans
- `for_tenant(tenant)`: Get plans available to tenant

### TenantSubscriptionManager
Methods:
- `active()`: Get active subscriptions
- `expired()`: Get expired subscriptions
- `trialing()`: Get trial subscriptions
- `current_for_tenant(tenant)`: Get current subscription for tenant

### InvoiceManager
Methods:
- `unpaid(tenant)`: Get unpaid invoices
- `overdue(tenant)`: Get overdue invoices
- `for_tenant(tenant)`: Get invoices for tenant

### PaymentManager
Methods:
- `successful(tenant)`: Get successful payments
- `failed(tenant)`: Get failed payments
- `for_tenant(tenant)`: Get payments for tenant

### UsageRecordManager
Methods:
- `for_tenant(tenant)`: Get usage records for tenant
- `for_feature(tenant, feature_code)`: Get usage for specific feature
- `check_limit(tenant, feature_code)`: Check if limit is exceeded

## Views

### Plan Selection and Management
- `PlanSelectionView`: Display available plans
- `PlanDetailView`: Show plan details
- `SubscriptionCreateView`: Create new subscription
- `SubscriptionUpdateView`: Update/upgrade/downgrade subscription
- `SubscriptionCancelView`: Cancel subscription

### Billing and Payments
- `BillingDashboardView`: Billing overview
- `InvoiceListView`: List invoices
- `InvoiceDetailView`: Show invoice details
- `PaymentMethodListView`: Manage payment methods
- `PaymentMethodCreateView`: Add payment method
- `PaymentMethodUpdateView`: Update payment method
- `PaymentMethodDeleteView`: Delete payment method

### Usage Tracking
- `UsageDashboardView`: Display usage statistics
- `SubscriptionDetailView`: Show subscription details

## Services

### SubscriptionEmailService
Handles email notifications for subscription events.

Methods:
- `send_welcome_email(subscription)`: Send welcome email
- `send_renewal_reminder(subscription, days)`: Send renewal reminder
- `send_cancellation_email(subscription)`: Send cancellation confirmation
- `send_usage_notification(tenant, usage, type)`: Send usage alert
- `send_invoice_notification(invoice)`: Send invoice notification

### SubscriptionService
Provides subscription management functionality.

Methods:
- `check_and_update_usage(tenant, feature, delta)`: Check and update usage
- `can_access_feature(tenant, feature)`: Check feature access
- `get_subscription_status(tenant)`: Get comprehensive status

## Decorators

### Subscription Validation
- `@subscription_required`: Ensure active subscription
- `@subscription_feature_required(feature_code)`: Require specific feature
- `@usage_limit_check(feature_code, delta)`: Check usage limits
- `@trial_limit_exempt`: Exempt from trial limitations
- `@plan_required(plan_slug/id)`: Require specific plan
- `@admin_subscription_required`: Require admin access

## Mixins

### View Mixins
- `SubscriptionRequiredMixin`: Require active subscription
- `SubscriptionFeatureMixin`: Require specific feature
- `SubscriptionUsageMixin`: Check usage limits
- `TrialLimitMixin`: Exempt from trial limitations
- `AdminSubscriptionMixin`: Require admin access
- `SubscriptionContextMixin`: Add subscription context
- `SubscriptionPlanMixin`: Require specific plan
- `SubscriptionUsageCheckMixin`: Check usage without updating

## Middleware

### SubscriptionMiddleware
Validates subscription status and enforces limits.

Features:
- Checks subscription status on each request
- Redirects for expired/cancelled subscriptions
- Adds subscription context to request
- Handles usage limit enforcement

## Template Tags

### Subscription Tags
- `subscription_status(tenant)`: Get subscription status
- `subscription_plan(tenant)`: Get plan name
- `days_remaining(tenant)`: Get days remaining
- `is_trial(tenant)`: Check if on trial
- `is_active(tenant)`: Check if active
- `subscription_feature_limit(tenant, feature)`: Get feature limit
- `subscription_feature_usage(tenant, feature)`: Get current usage
- `subscription_usage_percentage(tenant, feature)`: Get usage percentage
- `subscription_usage_status(tenant, feature)`: Get usage status
- `can_add_user(tenant)`: Check if can add users
- `can_upload_file(tenant, size)`: Check file upload limit
- `subscription_badge_class(tenant)`: Get badge CSS class
- `subscription_progress_class(tenant, feature)`: Get progress bar class
- `subscription_next_billing_date(tenant)`: Get next billing date
- `subscription_price(tenant)`: Get subscription price
- `subscription_features(tenant)`: Get all features
- `has_subscription_feature(tenant, feature)`: Check feature access
- `subscription_alerts(tenant)`: Get subscription alerts

## Management Commands

### Subscription Management
- `check_subscription_status`: Check and update subscription status
- `send_usage_notifications`: Send usage notifications
- `process_recurring_payments`: Process recurring payments
- `update_usage_records`: Update usage records

## Templates

### Subscription Pages
- `plan_selection.html`: Plan comparison and selection
- `plan_detail.html`: Detailed plan information
- `subscription_detail.html`: Current subscription details
- `subscription_create.html`: New subscription form
- `subscription_update.html`: Update subscription form
- `subscription_cancel.html`: Cancellation confirmation
- `subscription_success.html`: Success confirmation
- `subscription_expired.html`: Expired subscription page
- `subscription_restricted.html`: Feature restricted page

### Billing Pages
- `billing_dashboard.html`: Billing overview
- `invoice_list.html`: Invoice listing
- `invoice_detail.html`: Invoice details
- `payment_form.html`: Payment form
- `payment_method_list.html`: Payment methods
- `payment_method_form.html`: Add/edit payment method
- `payment_method_confirm_delete.html`: Delete confirmation

### Usage Pages
- `usage_dashboard.html`: Usage statistics and limits

### Email Templates
- `welcome_email.html/txt`: New subscriber welcome
- `renewal_reminder_email.html/txt`: Subscription renewal reminders
- `cancellation_email.html/txt`: Cancellation confirmation
- `usage_notification_email.html/txt`: Usage alerts
- `invoice_email.html/txt`: Invoice notifications

## Payment Integration

### Stripe Integration
The system includes placeholder Stripe integration that can be easily configured:

1. Set Stripe API keys in settings
2. Configure webhook endpoints
3. Implement payment processing in views

### Webhook Handling
The system handles Stripe webhooks for:
- Payment succeeded
- Payment failed
- Subscription created
- Subscription updated
- Subscription deleted

## Usage Tracking

### Feature Monitoring
The system tracks usage for:
- User count
- Storage usage
- Case count
- Document uploads
- Custom features

### Limit Enforcement
Usage limits are enforced through:
- Middleware checks
- View decorators
- Service methods
- Template tags

## Configuration

### Settings
Add these settings to your Django settings:

```python
# Subscription settings
SUBSCRIPTION_TRIAL_DAYS = 14  # Trial period length
SUBSCRIPTION_WARNING_DAYS = 7  # Days before expiry to send warning
SUBSCRIPTION_CRITICAL_DAYS = 3  # Days before expiry to send critical alert

# Payment settings
STRIPE_PUBLISHABLE_KEY = 'your_publishable_key'
STRIPE_SECRET_KEY = 'your_secret_key'
STRIPE_WEBHOOK_SECRET = 'your_webhook_secret'

# Email settings
SITE_URL = 'https://your-domain.com'
DEFAULT_FROM_EMAIL = 'noreply@your-domain.com'
```

## Integration

### Adding to Existing Views
Use decorators and mixins to add subscription checks:

```python
from subscriptions.decorators import subscription_required, subscription_feature_required
from subscriptions.mixins import SubscriptionRequiredMixin

# Using decorator
@subscription_required
def my_view(request):
    # View logic here
    pass

# Using mixin
class MyView(SubscriptionRequiredMixin):
    # View logic here
    pass
```

### Checking Usage
Use the service to check and update usage:

```python
from subscriptions.services import SubscriptionService

# Check if user can add another user
result = SubscriptionService.check_and_update_usage(
    request.user.tenant, 'users', 1
)

if not result['success']:
    # Handle limit exceeded
    pass
```

### Template Integration
Use template tags to display subscription information:

```html
{% load subscription_tags %}

<div class="subscription-status">
  <span class="badge {{ subscription_badge_class|default:'bg-secondary' }}">
    {{ subscription_plan|default:'No Subscription' }}
  </span>
  {% if days_remaining > 0 %}
    <small>{{ days_remaining }} days remaining</small>
  {% endif %}
</div>
```

## Testing

Run tests with:

```bash
python manage.py test subscriptions
```

Tests cover:
- Model creation and validation
- Service methods
- View functionality
- Decorator behavior
- Template tag output

## Security Considerations

- Payment method details are encrypted
- Tenant isolation is enforced in all queries
- Usage limits are validated server-side
- Webhook signatures are verified
- Admin access is restricted to tenant owners

## Performance Optimization

- Subscription status is cached in middleware
- Usage records are efficiently queried
- Email notifications are queued
- Database queries are optimized with select_related

## Future Enhancements

- Multi-currency support
- Advanced reporting
- Custom plan creation
- API usage tracking
- Discount and coupon system