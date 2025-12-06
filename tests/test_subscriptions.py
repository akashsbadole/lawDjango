"""
Tests for subscription module in multi-tenant context.
"""

from django.test import TestCase, TransactionTestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
from django.contrib.auth import get_user_model

from subscriptions.models import (
    SubscriptionPlan, SubscriptionFeature, PlanFeature, PaymentMethod,
    TenantSubscription, Invoice, Payment, UsageRecord, SubscriptionEvent
)
from tenants.models import Tenant
from tests.utils import TenantTestCase, MultiTenantTestCase, TenantMixinTestMixin

User = get_user_model()


class SubscriptionPlanModelTests(TenantTestCase):
    """Test SubscriptionPlan model."""
    
    def test_subscription_plan_creation(self):
        """Test basic subscription plan creation."""
        plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            slug='basic-plan',
            plan_type='basic',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly',
            max_users=5,
            max_storage_mb=1000,
            trial_days=14,
            setup_fee=Decimal('50.00')
        )
        
        self.assertEqual(plan.name, 'Basic Plan')
        self.assertEqual(plan.slug, 'basic-plan')
        self.assertEqual(plan.plan_type, 'basic')
        self.assertEqual(plan.description, 'Basic subscription plan')
        self.assertEqual(plan.price, Decimal('29.99'))
        self.assertEqual(plan.billing_cycle, 'monthly')
        self.assertEqual(plan.max_users, 5)
        self.assertEqual(plan.max_storage_mb, 1000)
        self.assertEqual(plan.trial_days, 14)
        self.assertEqual(plan.setup_fee, Decimal('50.00'))
        self.assertTrue(plan.is_active)
        self.assertTrue(plan.is_public)
    
    def test_subscription_plan_str_representation(self):
        """Test subscription plan string representation."""
        plan = SubscriptionPlan.objects.create(
            name='Professional Plan',
            slug='professional-plan',
            plan_type='professional',
            description='Professional subscription plan',
            price=Decimal('99.99'),
            billing_cycle='monthly'
        )
        
        expected = "Professional Plan ($99.99/monthly)"
        self.assertEqual(str(plan), expected)
    
    def test_subscription_plan_yearly_price_property(self):
        """Test yearly price property."""
        # Monthly plan
        monthly_plan = SubscriptionPlan.objects.create(
            name='Monthly Plan',
            slug='monthly-plan',
            plan_type='basic',
            description='Monthly subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly'
        )
        
        self.assertEqual(monthly_plan.yearly_price, Decimal('359.88'))  # 29.99 * 12
        
        # Yearly plan
        yearly_plan = SubscriptionPlan.objects.create(
            name='Yearly Plan',
            slug='yearly-plan',
            plan_type='basic',
            description='Yearly subscription plan',
            price=Decimal('299.99'),
            billing_cycle='yearly'
        )
        
        self.assertEqual(yearly_plan.yearly_price, Decimal('299.99'))
    
    def test_subscription_plan_monthly_price_property(self):
        """Test monthly price property."""
        # Monthly plan
        monthly_plan = SubscriptionPlan.objects.create(
            name='Monthly Plan',
            slug='monthly-plan',
            plan_type='basic',
            description='Monthly subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly'
        )
        
        self.assertEqual(monthly_plan.monthly_price, Decimal('29.99'))
        
        # Yearly plan
        yearly_plan = SubscriptionPlan.objects.create(
            name='Yearly Plan',
            slug='yearly-plan',
            plan_type='basic',
            description='Yearly subscription plan',
            price=Decimal('359.88'),
            billing_cycle='yearly'
        )
        
        self.assertEqual(yearly_plan.monthly_price, Decimal('29.99'))  # 359.88 / 12
    
    def test_subscription_plan_ordering(self):
        """Test subscription plan ordering by price and name."""
        # Create plans in random order
        plan3 = SubscriptionPlan.objects.create(
            name='Enterprise Plan',
            slug='enterprise-plan',
            plan_type='enterprise',
            description='Enterprise subscription plan',
            price=Decimal('299.99'),
            billing_cycle='monthly'
        )
        
        plan1 = SubscriptionPlan.objects.create(
            name='Basic Plan',
            slug='basic-plan',
            plan_type='basic',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly'
        )
        
        plan2 = SubscriptionPlan.objects.create(
            name='Professional Plan',
            slug='professional-plan',
            plan_type='professional',
            description='Professional subscription plan',
            price=Decimal('99.99'),
            billing_cycle='monthly'
        )
        
        # Verify ordering
        plans = list(SubscriptionPlan.objects.all())
        self.assertEqual(plans[0], plan1)  # Basic - $29.99
        self.assertEqual(plans[1], plan2)  # Professional - $99.99
        self.assertEqual(plans[2], plan3)  # Enterprise - $299.99


class SubscriptionFeatureModelTests(TestCase):
    """Test SubscriptionFeature model."""
    
    def test_subscription_feature_creation(self):
        """Test basic subscription feature creation."""
        feature = SubscriptionFeature.objects.create(
            name='API Access',
            code='api_access',
            description='Access to API endpoints',
            feature_type='boolean',
            default_value='true'
        )
        
        self.assertEqual(feature.name, 'API Access')
        self.assertEqual(feature.code, 'api_access')
        self.assertEqual(feature.description, 'Access to API endpoints')
        self.assertEqual(feature.feature_type, 'boolean')
        self.assertEqual(feature.default_value, 'true')
        self.assertTrue(feature.is_active)
    
    def test_subscription_feature_str_representation(self):
        """Test subscription feature string representation."""
        feature = SubscriptionFeature.objects.create(
            name='Max Users',
            code='max_users',
            description='Maximum number of users',
            feature_type='number',
            default_value='5'
        )
        
        self.assertEqual(str(feature), 'Max Users')
    
    def test_subscription_feature_ordering(self):
        """Test subscription feature ordering by name."""
        feature2 = SubscriptionFeature.objects.create(
            name='Storage',
            code='storage',
            description='Storage space',
            feature_type='number',
            default_value='1000'
        )
        
        feature1 = SubscriptionFeature.objects.create(
            name='API Access',
            code='api_access',
            description='Access to API endpoints',
            feature_type='boolean',
            default_value='true'
        )
        
        # Verify ordering
        features = list(SubscriptionFeature.objects.all())
        self.assertEqual(features[0], feature1)  # API Access
        self.assertEqual(features[1], feature2)  # Storage


class PlanFeatureModelTests(TestCase):
    """Test PlanFeature model."""
    
    def setUp(self):
        """Set up test data."""
        self.plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            slug='basic-plan',
            plan_type='basic',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly'
        )
        
        self.feature = SubscriptionFeature.objects.create(
            name='API Access',
            code='api_access',
            description='Access to API endpoints',
            feature_type='boolean'
        )
    
    def test_plan_feature_creation(self):
        """Test basic plan feature creation."""
        plan_feature = PlanFeature.objects.create(
            plan=self.plan,
            feature=self.feature,
            value='true',
            is_included=True
        )
        
        self.assertEqual(plan_feature.plan, self.plan)
        self.assertEqual(plan_feature.feature, self.feature)
        self.assertEqual(plan_feature.value, 'true')
        self.assertTrue(plan_feature.is_included)
    
    def test_plan_feature_str_representation(self):
        """Test plan feature string representation."""
        plan_feature = PlanFeature.objects.create(
            plan=self.plan,
            feature=self.feature,
            value='true',
            is_included=True
        )
        
        expected = "Basic Plan - API Access: Included"
        self.assertEqual(str(plan_feature), expected)
    
    def test_plan_feature_unique_constraint(self):
        """Test unique constraint on plan and feature."""
        # Create first plan feature
        PlanFeature.objects.create(
            plan=self.plan,
            feature=self.feature,
            value='true',
            is_included=True
        )
        
        # Try to create duplicate
        with self.assertRaises(Exception):  # IntegrityError or ValidationError
            PlanFeature.objects.create(
                plan=self.plan,
                feature=self.feature,
                value='false',
                is_included=False
            )


class PaymentMethodModelTests(TenantTestCase):
    """Test PaymentMethod model."""
    
    def test_payment_method_creation(self):
        """Test basic payment method creation."""
        payment_method = PaymentMethod.objects.create(
            tenant=self.active_tenant,
            method_type='credit_card',
            details={
                'last4': '1234',
                'brand': 'visa',
                'exp_month': 12,
                'exp_year': 2025
            },
            is_default=True,
            is_active=True,
            stripe_payment_method_id='pm_1234567890'
        )
        
        self.assertEqual(payment_method.tenant, self.active_tenant)
        self.assertEqual(payment_method.method_type, 'credit_card')
        self.assertEqual(payment_method.details['last4'], '1234')
        self.assertEqual(payment_method.details['brand'], 'visa')
        self.assertTrue(payment_method.is_default)
        self.assertTrue(payment_method.is_active)
        self.assertEqual(payment_method.stripe_payment_method_id, 'pm_1234567890')
    
    def test_payment_method_str_representation(self):
        """Test payment method string representation."""
        payment_method = PaymentMethod.objects.create(
            tenant=self.active_tenant,
            method_type='paypal',
            details={'email': 'user@example.com'},
            is_default=False
        )
        
        expected = f"{self.active_tenant.name} - PayPal"
        self.assertEqual(str(payment_method), expected)
    
    def test_payment_method_single_default_per_tenant(self):
        """Test that only one payment method can be default per tenant."""
        # Create first payment method as default
        pm1 = PaymentMethod.objects.create(
            tenant=self.active_tenant,
            method_type='credit_card',
            details={'last4': '1234'},
            is_default=True
        )
        
        self.assertTrue(pm1.is_default)
        
        # Create second payment method as default
        pm2 = PaymentMethod.objects.create(
            tenant=self.active_tenant,
            method_type='bank_transfer',
            details={'account_last4': '5678'},
            is_default=True
        )
        
        # Refresh first payment method from database
        pm1.refresh_from_db()
        
        # Verify only second payment method is default
        self.assertFalse(pm1.is_default)
        self.assertTrue(pm2.is_default)
    
    def test_payment_method_ordering(self):
        """Test payment method ordering."""
        # Create payment methods in random order
        pm2 = PaymentMethod.objects.create(
            tenant=self.active_tenant,
            method_type='bank_transfer',
            details={'account_last4': '5678'},
            is_default=False
        )
        
        pm1 = PaymentMethod.objects.create(
            tenant=self.active_tenant,
            method_type='credit_card',
            details={'last4': '1234'},
            is_default=True
        )
        
        # Verify ordering (default first, then by creation date)
        methods = list(PaymentMethod.objects.all())
        self.assertEqual(methods[0], pm1)  # Default
        self.assertEqual(methods[1], pm2)  # Non-default


class TenantSubscriptionModelTests(TenantTestCase):
    """Test TenantSubscription model."""
    
    def setUp(self):
        """Set up test data."""
        self.plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            slug='basic-plan',
            plan_type='basic',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly',
            trial_days=14
        )
    
    def test_tenant_subscription_creation(self):
        """Test basic tenant subscription creation."""
        now = timezone.now()
        trial_end = now + timedelta(days=14)
        
        subscription = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=self.plan,
            status='trial',
            start_date=now,
            trial_end_date=trial_end,
            auto_renew=True
        )
        
        self.assertEqual(subscription.tenant, self.active_tenant)
        self.assertEqual(subscription.plan, self.plan)
        self.assertEqual(subscription.status, 'trial')
        self.assertEqual(subscription.start_date, now)
        self.assertEqual(subscription.trial_end_date, trial_end)
        self.assertTrue(subscription.auto_renew)
    
    def test_tenant_subscription_str_representation(self):
        """Test tenant subscription string representation."""
        subscription = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=self.plan,
            status='active',
            start_date=timezone.now()
        )
        
        expected = f"{self.active_tenant.name} - {self.plan.name} (active)"
        self.assertEqual(str(subscription), expected)
    
    def test_tenant_subscription_is_active_property(self):
        """Test is_active property."""
        # Active subscription
        active_sub = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=self.plan,
            status='active',
            start_date=timezone.now()
        )
        
        self.assertTrue(active_sub.is_active)
        
        # Cancelled subscription
        cancelled_sub = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=self.plan,
            status='cancelled',
            start_date=timezone.now()
        )
        
        self.assertFalse(cancelled_sub.is_active)
        
        # Expired subscription
        expired_sub = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=self.plan,
            status='expired',
            start_date=timezone.now()
        )
        
        self.assertFalse(expired_sub.is_active)
        
        # Past due subscription
        past_due_sub = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=self.plan,
            status='past_due',
            start_date=timezone.now()
        )
        
        self.assertTrue(past_due_sub.is_active)
    
    def test_tenant_subscription_is_trial_property(self):
        """Test is_trial property."""
        now = timezone.now()
        
        # Trial subscription
        trial_sub = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=self.plan,
            status='trial',
            start_date=now,
            trial_end_date=now + timedelta(days=14)
        )
        
        self.assertTrue(trial_sub.is_trial)
        
        # Expired trial
        expired_trial_sub = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=self.plan,
            status='trial',
            start_date=now - timedelta(days=30),
            trial_end_date=now - timedelta(days=16)
        )
        
        self.assertFalse(expired_trial_sub.is_trial)
        
        # No trial end date
        no_trial_sub = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=self.plan,
            status='active',
            start_date=now
        )
        
        self.assertFalse(no_trial_sub.is_trial)
    
    def test_tenant_subscription_days_until_expiry_property(self):
        """Test days_until_expiry property."""
        now = timezone.now()
        
        # Subscription with end date in future
        future_sub = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=self.plan,
            status='active',
            start_date=now,
            end_date=now + timedelta(days=30)
        )
        
        self.assertEqual(future_sub.days_until_expiry, 30)
        
        # Subscription with end date in past
        past_sub = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=self.plan,
            status='active',
            start_date=now - timedelta(days=60),
            end_date=now - timedelta(days=30)
        )
        
        self.assertEqual(past_sub.days_until_expiry, 0)
        
        # Subscription without end date
        no_end_sub = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=self.plan,
            status='active',
            start_date=now
        )
        
        self.assertIsNone(no_end_sub.days_until_expiry)
    
    def test_tenant_subscription_days_until_trial_end_property(self):
        """Test days_until_trial_end property."""
        now = timezone.now()
        
        # Trial ending in future
        future_trial = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=self.plan,
            status='trial',
            start_date=now,
            trial_end_date=now + timedelta(days=14)
        )
        
        self.assertEqual(future_trial.days_until_trial_end, 14)
        
        # Trial ended in past
        past_trial = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=self.plan,
            status='trial',
            start_date=now - timedelta(days=30),
            trial_end_date=now - timedelta(days=16)
        )
        
        self.assertEqual(past_trial.days_until_trial_end, 0)
        
        # No trial end date
        no_trial = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=self.plan,
            status='active',
            start_date=now
        )
        
        self.assertIsNone(no_trial.days_until_trial_end)
    
    def test_tenant_subscription_extend_subscription_method(self):
        """Test extend_subscription method."""
        now = timezone.now()
        
        subscription = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=self.plan,
            status='active',
            start_date=now,
            end_date=now + timedelta(days=30)
        )
        
        # Ensure original_end_date is not None for the test
        self.assertIsNotNone(original_end_date)
        original_end_date = subscription.end_date
        subscription.extend_subscription(15)
        
        # Verify end date was extended
        subscription.refresh_from_db()
        expected_end_date = original_end_date + timedelta(days=15)
        self.assertEqual(subscription.end_date, expected_end_date)
        
        # Test extending subscription without end date
        subscription_no_end = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=self.plan,
            status='active',
            start_date=now
        )
        
        subscription_no_end.extend_subscription(30)
        subscription_no_end.refresh_from_db()
        
        expected_end_date = now + timedelta(days=30)
        self.assertEqual(subscription_no_end.end_date, expected_end_date)


class SubscriptionInvoiceModelTests(TenantTestCase):
    """Test subscription Invoice model."""
    
    def test_subscription_invoice_creation(self):
        """Test basic subscription invoice creation."""
        plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            slug='basic-plan',
            plan_type='basic',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly'
        )
        
        subscription = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=plan,
            status='active',
            start_date=timezone.now()
        )
        
        invoice = Invoice.objects.create(
            invoice_number='SUB-001',
            tenant=self.active_tenant,
            subscription=subscription,
            invoice_type='subscription',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal('29.99'),
            tax_rate=Decimal('0.08'),
            status='draft'
        )
        
        self.assertEqual(invoice.invoice_number, 'SUB-001')
        self.assertEqual(invoice.tenant, self.active_tenant)
        self.assertEqual(invoice.subscription, subscription)
        self.assertEqual(invoice.invoice_type, 'subscription')
        self.assertEqual(invoice.subtotal, Decimal('29.99'))
        self.assertEqual(invoice.tax_rate, Decimal('0.08'))
        self.assertEqual(invoice.status, 'draft')
    
    def test_subscription_invoice_str_representation(self):
        """Test subscription invoice string representation."""
        invoice = Invoice.objects.create(
            invoice_number='SUB-001',
            tenant=self.active_tenant,
            invoice_type='subscription',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal('29.99'),
            status='draft'
        )
        
        expected = f"Invoice SUB-001 - {self.active_tenant.name}"
        self.assertEqual(str(invoice), expected)
    
    def test_subscription_invoice_is_overdue_property(self):
        """Test is_overdue property."""
        # Overdue invoice
        overdue_invoice = Invoice.objects.create(
            invoice_number='SUB-OVERDUE',
            tenant=self.active_tenant,
            invoice_type='subscription',
            issue_date=date.today() - timedelta(days=60),
            due_date=date.today() - timedelta(days=30),
            subtotal=Decimal('29.99'),
            status='sent'
        )
        
        self.assertTrue(overdue_invoice.is_overdue)
        
        # Not overdue invoice
        not_overdue_invoice = Invoice.objects.create(
            invoice_number='SUB-NOT-OVERDUE',
            tenant=self.active_tenant,
            invoice_type='subscription',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal('29.99'),
            status='sent'
        )
        
        self.assertFalse(not_overdue_invoice.is_overdue)
        
        # Paid invoice (even if past due date)
        paid_invoice = Invoice.objects.create(
            invoice_number='SUB-PAID',
            tenant=self.active_tenant,
            invoice_type='subscription',
            issue_date=date.today() - timedelta(days=60),
            due_date=date.today() - timedelta(days=30),
            subtotal=Decimal('29.99'),
            status='paid'
        )
        
        self.assertFalse(paid_invoice.is_overdue)
    
    def test_subscription_invoice_calculate_totals_method(self):
        """Test calculate_totals method."""
        invoice = Invoice.objects.create(
            invoice_number='SUB-001',
            tenant=self.active_tenant,
            invoice_type='subscription',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal('29.99'),
            tax_rate=Decimal('0.08'),
            status='draft'
        )
        
        invoice.calculate_totals()
        
        # Verify calculations
        expected_tax_amount = Decimal('2.40')  # 29.99 * 0.08
        expected_total_amount = Decimal('32.39')  # 29.99 + 2.40
        
        self.assertEqual(invoice.tax_amount, expected_tax_amount)
        self.assertEqual(invoice.total_amount, expected_total_amount)


class SubscriptionPaymentModelTests(TenantTestCase):
    """Test subscription Payment model."""
    
    def test_subscription_payment_creation(self):
        """Test basic subscription payment creation."""
        invoice = Invoice.objects.create(
            invoice_number='SUB-001',
            tenant=self.active_tenant,
            invoice_type='subscription',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal('29.99'),
            status='sent'
        )
        
        payment = Payment.objects.create(
            invoice=invoice,
            amount=Decimal('29.99'),
            payment_method='stripe',
            status='completed',
            transaction_id='txn_1234567890',
            stripe_payment_intent_id='pi_1234567890'
        )
        
        self.assertEqual(payment.invoice, invoice)
        self.assertEqual(payment.amount, Decimal('29.99'))
        self.assertEqual(payment.payment_method, 'stripe')
        self.assertEqual(payment.status, 'completed')
        self.assertEqual(payment.transaction_id, 'txn_1234567890')
        self.assertEqual(payment.stripe_payment_intent_id, 'pi_1234567890')
    
    def test_subscription_payment_str_representation(self):
        """Test subscription payment string representation."""
        invoice = Invoice.objects.create(
            invoice_number='SUB-001',
            tenant=self.active_tenant,
            invoice_type='subscription',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal('29.99'),
            status='sent'
        )
        
        payment = Payment.objects.create(
            invoice=invoice,
            amount=Decimal('29.99'),
            payment_method='stripe',
            status='completed'
        )
        
        expected = f"Payment of ${payment.amount} for Invoice {invoice.invoice_number}"
        self.assertEqual(str(payment), expected)


class UsageRecordModelTests(TenantTestCase):
    """Test UsageRecord model."""
    
    def setUp(self):
        """Set up test data."""
        self.feature = SubscriptionFeature.objects.create(
            name='API Calls',
            code='api_calls',
            description='Number of API calls',
            feature_type='number'
        )
    
    def test_usage_record_creation(self):
        """Test basic usage record creation."""
        now = timezone.now()
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_end = period_start + timedelta(days=32)  # Next month
        
        usage_record = UsageRecord.objects.create(
            tenant=self.active_tenant,
            feature=self.feature,
            current_usage=Decimal('1000.50'),
            limit=Decimal('5000.00'),
            period='monthly',
            period_start=period_start,
            period_end=period_end
        )
        
        self.assertEqual(usage_record.tenant, self.active_tenant)
        self.assertEqual(usage_record.feature, self.feature)
        self.assertEqual(usage_record.current_usage, Decimal('1000.50'))
        self.assertEqual(usage_record.limit, Decimal('5000.00'))
        self.assertEqual(usage_record.period, 'monthly')
        self.assertEqual(usage_record.period_start, period_start)
        self.assertEqual(usage_record.period_end, period_end)
    
    def test_usage_record_str_representation(self):
        """Test usage record string representation."""
        usage_record = UsageRecord.objects.create(
            tenant=self.active_tenant,
            feature=self.feature,
            current_usage=Decimal('1000.50'),
            limit=Decimal('5000.00'),
            period='monthly',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30)
        )
        
        expected = f"{self.active_tenant.name} - {self.feature.name}: 1000.50/5000.00"
        self.assertEqual(str(usage_record), expected)
    
    def test_usage_record_usage_percentage_property(self):
        """Test usage_percentage property."""
        # With limit
        usage_with_limit = UsageRecord.objects.create(
            tenant=self.active_tenant,
            feature=self.feature,
            current_usage=Decimal('2500.00'),
            limit=Decimal('5000.00'),
            period='monthly',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30)
        )
        
        self.assertEqual(usage_with_limit.usage_percentage, 50.0)
        
        # Over limit
        usage_over_limit = UsageRecord.objects.create(
            tenant=self.active_tenant,
            feature=self.feature,
            current_usage=Decimal('6000.00'),
            limit=Decimal('5000.00'),
            period='monthly',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30)
        )
        
        self.assertEqual(usage_over_limit.usage_percentage, 100.0)
        
        # No limit
        usage_no_limit = UsageRecord.objects.create(
            tenant=self.active_tenant,
            feature=self.feature,
            current_usage=Decimal('1000.00'),
            limit=None,
            period='monthly',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30)
        )
        
        self.assertEqual(usage_no_limit.usage_percentage, 0)
    
    def test_usage_record_is_over_limit_property(self):
        """Test is_over_limit property."""
        # Under limit
        usage_under_limit = UsageRecord.objects.create(
            tenant=self.active_tenant,
            feature=self.feature,
            current_usage=Decimal('2500.00'),
            limit=Decimal('5000.00'),
            period='monthly',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30)
        )
        
        self.assertFalse(usage_under_limit.is_over_limit)
        
        # Over limit
        usage_over_limit = UsageRecord.objects.create(
            tenant=self.active_tenant,
            feature=self.feature,
            current_usage=Decimal('6000.00'),
            limit=Decimal('5000.00'),
            period='monthly',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30)
        )
        
        self.assertTrue(usage_over_limit.is_over_limit)
        
        # No limit
        usage_no_limit = UsageRecord.objects.create(
            tenant=self.active_tenant,
            feature=self.feature,
            current_usage=Decimal('1000.00'),
            limit=None,
            period='monthly',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30)
        )
        
        self.assertFalse(usage_no_limit.is_over_limit)
    
    def test_usage_record_remaining_property(self):
        """Test remaining property."""
        # Under limit
        usage_under_limit = UsageRecord.objects.create(
            tenant=self.active_tenant,
            feature=self.feature,
            current_usage=Decimal('2500.00'),
            limit=Decimal('5000.00'),
            period='monthly',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30)
        )
        
        self.assertEqual(usage_under_limit.remaining, Decimal('2500.00'))
        
        # Over limit
        usage_over_limit = UsageRecord.objects.create(
            tenant=self.active_tenant,
            feature=self.feature,
            current_usage=Decimal('6000.00'),
            limit=Decimal('5000.00'),
            period='monthly',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30)
        )
        
        self.assertEqual(usage_over_limit.remaining, Decimal('0.00'))
        
        # No limit
        usage_no_limit = UsageRecord.objects.create(
            tenant=self.active_tenant,
            feature=self.feature,
            current_usage=Decimal('1000.00'),
            limit=None,
            period='monthly',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30)
        )
        
        self.assertIsNone(usage_no_limit.remaining)


class SubscriptionEventModelTests(TenantTestCase):
    """Test SubscriptionEvent model."""
    
    def setUp(self):
        """Set up test data."""
        self.plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            slug='basic-plan',
            plan_type='basic',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly'
        )
        
        self.subscription = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=self.plan,
            status='active',
            start_date=timezone.now()
        )
    
    def test_subscription_event_creation(self):
        """Test basic subscription event creation."""
        event = SubscriptionEvent.objects.create(
            tenant=self.active_tenant,
            subscription=self.subscription,
            event_type='created',
            description='Subscription created',
            metadata={'plan_id': str(self.plan.pk), 'user_id': str(self.admin_user.pk)}
        )
        
        self.assertEqual(event.tenant, self.active_tenant)
        self.assertEqual(event.subscription, self.subscription)
        self.assertEqual(event.event_type, 'created')
        self.assertEqual(event.description, 'Subscription created')
        self.assertEqual(event.metadata['plan_id'], str(self.plan.pk))
        self.assertEqual(event.metadata['user_id'], str(self.admin_user.pk))
    
    def test_subscription_event_str_representation(self):
        """Test subscription event string representation."""
        event = SubscriptionEvent.objects.create(
            tenant=self.active_tenant,
            subscription=self.subscription,
            event_type='payment_succeeded',
            description='Payment succeeded'
        )
        
        expected = f"{self.active_tenant.name} - Payment Succeeded"
        self.assertEqual(str(event), expected)


class SubscriptionTenantIsolationTests(MultiTenantTestCase, TenantMixinTestMixin):
    """Test subscription isolation between tenants."""
    
    def test_subscription_plans_not_isolated(self):
        """Test that subscription plans are not isolated by tenant (global)."""
        plan1 = SubscriptionPlan.objects.create(
            name='Plan 1',
            slug='plan-1',
            plan_type='basic',
            description='Plan 1 description',
            price=Decimal('29.99'),
            billing_cycle='monthly'
        )
        
        plan2 = SubscriptionPlan.objects.create(
            name='Plan 2',
            slug='plan-2',
            plan_type='professional',
            description='Plan 2 description',
            price=Decimal('99.99'),
            billing_cycle='monthly'
        )
        
        # Both plans should be visible to all tenants
        all_plans = list(SubscriptionPlan.objects.all())
        self.assertIn(plan1, all_plans)
        self.assertIn(plan2, all_plans)
    
    def test_tenant_subscriptions_isolated_by_tenant(self):
        """Test that tenant subscriptions are properly isolated by tenant."""
        plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            slug='basic-plan',
            plan_type='basic',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly'
        )
        
        # Create subscriptions for different tenants
        sub1 = TenantSubscription.objects.create(
            tenant=self.tenant1,
            plan=plan,
            status='active',
            start_date=timezone.now()
        )
        
        sub2 = TenantSubscription.objects.create(
            tenant=self.tenant2,
            plan=plan,
            status='active',
            start_date=timezone.now()
        )
        
        # Test isolation
        self.assertTenantIsolation(
            TenantSubscription,
            self.tenant1,
            self.tenant2,
            {'status': 'active'},
            {'status': 'active'}
        )
    
    def test_payment_methods_isolated_by_tenant(self):
        """Test that payment methods are properly isolated by tenant."""
        # Create payment methods for different tenants
        pm1 = PaymentMethod.objects.create(
            tenant=self.tenant1,
            method_type='credit_card',
            details={'last4': '1234'},
            is_default=True
        )
        
        pm2 = PaymentMethod.objects.create(
            tenant=self.tenant2,
            method_type='credit_card',
            details={'last4': '5678'},
            is_default=True
        )
        
        # Test isolation
        self.assertTenantIsolation(
            PaymentMethod,
            self.tenant1,
            self.tenant2,
            {'method_type': 'credit_card'},
            {'method_type': 'credit_card'}
        )
    
    def test_usage_records_isolated_by_tenant(self):
        """Test that usage records are properly isolated by tenant."""
        feature = SubscriptionFeature.objects.create(
            name='API Calls',
            code='api_calls',
            description='Number of API calls',
            feature_type='number'
        )
        
        # Create usage records for different tenants
        usage1 = UsageRecord.objects.create(
            tenant=self.tenant1,
            feature=feature,
            current_usage=Decimal('1000.00'),
            limit=Decimal('5000.00'),
            period='monthly',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30)
        )
        
        usage2 = UsageRecord.objects.create(
            tenant=self.tenant2,
            feature=feature,
            current_usage=Decimal('2000.00'),
            limit=Decimal('5000.00'),
            period='monthly',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30)
        )
        
        # Test isolation
        self.assertTenantIsolation(
            UsageRecord,
            self.tenant1,
            self.tenant2,
            {'current_usage': Decimal('1000.00')},
            {'current_usage': Decimal('2000.00')}
        )


class SubscriptionTransactionTests(TransactionTestCase):
    """Test subscription functionality with transactions."""
    
    def setUp(self):
        """Set up test data for transaction tests."""
        # Create a tenant
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant'
        )
        
        # Create a plan
        self.plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            slug='basic-plan',
            plan_type='basic',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly'
        )
    
    def test_subscription_creation_rollback_on_error(self):
        """Test subscription creation rollback on error."""
        # Try to create a subscription with invalid data
        with self.assertRaises(Exception):  # IntegrityError or ValidationError
            TenantSubscription.objects.create(
                tenant=self.tenant,
                plan=None,  # Invalid: plan is required
                status='active',
                start_date=timezone.now()
            )
        
        # Verify tenant and plan still exist (transaction rolled back)
        self.assertTrue(Tenant.objects.filter(slug='test-tenant').exists())
        self.assertTrue(SubscriptionPlan.objects.filter(slug='basic-plan').exists())
    
    def test_invoice_payment_transaction(self):
        """Test invoice and payment creation in transaction."""
        # Create subscription
        subscription = TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status='active',
            start_date=timezone.now()
        )
        
        # Create invoice
        invoice = Invoice.objects.create(
            invoice_number='SUB-001',
            tenant=self.tenant,
            subscription=subscription,
            invoice_type='subscription',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal('29.99'),
            status='sent'
        )
        
        # Create payment
        payment = Payment.objects.create(
            invoice=invoice,
            amount=Decimal('29.99'),
            payment_method='stripe',
            status='completed'
        )
        
        # Verify relationship
        self.assertEqual(payment.invoice, invoice)
        self.assertEqual(invoice.subscription, subscription)
        self.assertEqual(invoice.tenant, self.tenant)


class SubscriptionIntegrationTests(TenantTestCase):
    """Test subscription integration with other modules."""
    
    def test_subscription_tenant_relationship(self):
        """Test subscription-tenant relationship."""
        plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            slug='basic-plan',
            plan_type='basic',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly'
        )
        
        subscription = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=plan,
            status='active',
            start_date=timezone.now()
        )
        
        # Test relationship
        self.assertEqual(subscription.tenant, self.active_tenant)
        self.assertTrue(TenantSubscription.objects.filter(tenant=self.active_tenant).exists())
    
    def test_subscription_plan_relationship(self):
        """Test subscription-plan relationship."""
        plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            slug='basic-plan',
            plan_type='basic',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly'
        )
        
        subscription = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=plan,
            status='active',
            start_date=timezone.now()
        )
        
        # Test relationship
        self.assertEqual(subscription.plan, plan)
        self.assertTrue(TenantSubscription.objects.filter(plan=plan).exists())
    
    def test_subscription_invoice_relationship(self):
        """Test subscription-invoice relationship."""
        plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            slug='basic-plan',
            plan_type='basic',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly'
        )
        
        subscription = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=plan,
            status='active',
            start_date=timezone.now()
        )
        
        invoice = Invoice.objects.create(
            invoice_number='SUB-001',
            tenant=self.active_tenant,
            subscription=subscription,
            invoice_type='subscription',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal('29.99'),
            status='sent'
        )
        
        # Test relationship
        self.assertEqual(invoice.subscription, subscription)
        self.assertTrue(Invoice.objects.filter(subscription=subscription).exists())
    
    def test_subscription_payment_relationship(self):
        """Test subscription payment-invoice relationship."""
        plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            slug='basic-plan',
            plan_type='basic',
            description='Basic subscription plan',
            price=Decimal('29.99'),
            billing_cycle='monthly'
        )
        
        subscription = TenantSubscription.objects.create(
            tenant=self.active_tenant,
            plan=plan,
            status='active',
            start_date=timezone.now()
        )
        
        invoice = Invoice.objects.create(
            invoice_number='SUB-001',
            tenant=self.active_tenant,
            subscription=subscription,
            invoice_type='subscription',
            issue_date=date.today(),
            due_date=date.today() + timedelta(days=30),
            subtotal=Decimal('29.99'),
            status='sent'
        )
        
        payment = Payment.objects.create(
            invoice=invoice,
            amount=Decimal('29.99'),
            payment_method='stripe',
            status='completed'
        )
        
        # Test relationship
        self.assertEqual(payment.invoice, invoice)
        self.assertTrue(Payment.objects.filter(invoice=invoice).exists())
    
    def test_subscription_usage_record_relationship(self):
        """Test subscription usage record relationship."""
        feature = SubscriptionFeature.objects.create(
            name='API Calls',
            code='api_calls',
            description='Number of API calls',
            feature_type='number'
        )
        
        usage_record = UsageRecord.objects.create(
            tenant=self.active_tenant,
            feature=feature,
            current_usage=Decimal('1000.00'),
            limit=Decimal('5000.00'),
            period='monthly',
            period_start=timezone.now(),
            period_end=timezone.now() + timedelta(days=30)
        )
        
        # Test relationship
        self.assertEqual(usage_record.tenant, self.active_tenant)
        self.assertEqual(usage_record.feature, feature)
        self.assertTrue(UsageRecord.objects.filter(tenant=self.active_tenant).exists())
        self.assertTrue(UsageRecord.objects.filter(feature=feature).exists())