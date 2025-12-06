from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from .models import SubscriptionPlan, SubscriptionFeature, PlanFeature, TenantSubscription, PaymentMethod, Invoice, Payment, UsageRecord
from .services import SubscriptionService, SubscriptionEmailService
from .decorators import subscription_required, subscription_feature_required

User = get_user_model()


class SubscriptionModelTests(TestCase):
    """Test subscription models"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        from tenants.models import Tenant
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            owner=self.user,
            subdomain='test'
        )
        
        # Create test subscription plan
        self.plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            slug='basic',
            price=29.99,
            billing_cycle='monthly',
            max_users=5,
            max_storage_mb=1024,
            max_cases=50,
            is_active=True,
            is_public=True
        )
        
        # Create test features
        self.users_feature = SubscriptionFeature.objects.create(
            name='Users',
            code='users',
            description='Maximum number of users'
        )
        
        self.storage_feature = SubscriptionFeature.objects.create(
            name='Storage',
            code='storage',
            description='Storage space in MB'
        )
        
        # Add features to plan
        PlanFeature.objects.create(
            plan=self.plan,
            feature=self.users_feature,
            value='5',
            is_included=True
        )
        
        PlanFeature.objects.create(
            plan=self.plan,
            feature=self.storage_feature,
            value='1024',
            is_included=True
        )
    
    def test_subscription_plan_creation(self):
        """Test subscription plan creation"""
        self.assertEqual(self.plan.name, 'Basic Plan')
        self.assertEqual(self.plan.price, 29.99)
        self.assertEqual(self.plan.billing_cycle, 'monthly')
        self.assertTrue(self.plan.is_active)
        self.assertTrue(self.plan.is_public)
    
    def test_subscription_feature_creation(self):
        """Test subscription feature creation"""
        self.assertEqual(self.users_feature.name, 'Users')
        self.assertEqual(self.users_feature.code, 'users')
        self.assertEqual(self.storage_feature.name, 'Storage')
        self.assertEqual(self.storage_feature.code, 'storage')
    
    def test_plan_feature_creation(self):
        """Test plan feature creation"""
        users_plan_feature = PlanFeature.objects.get(
            plan=self.plan,
            feature=self.users_feature
        )
        self.assertEqual(users_plan_feature.value, '5')
        self.assertTrue(users_plan_feature.is_included)
    
    def test_tenant_subscription_creation(self):
        """Test tenant subscription creation"""
        subscription = TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
            status='active'
        )
        
        self.assertEqual(subscription.tenant, self.tenant)
        self.assertEqual(subscription.plan, self.plan)
        self.assertEqual(subscription.status, 'active')
    
    def test_payment_method_creation(self):
        """Test payment method creation"""
        payment_method = PaymentMethod.objects.create(
            tenant=self.tenant,
            method_type='card',
            details={
                'card_type': 'visa',
                'card_last4': '1234',
                'expiry_month': '12',
                'expiry_year': '2025'
            },
            is_default=True,
            is_active=True
        )
        
        self.assertEqual(payment_method.tenant, self.tenant)
        self.assertEqual(payment_method.method_type, 'card')
        self.assertTrue(payment_method.is_default)
    
    def test_invoice_creation(self):
        """Test invoice creation"""
        subscription = TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
            status='active'
        )
        
        invoice = Invoice.objects.create(
            subscription=subscription,
            invoice_number='INV-001',
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timedelta(days=15),
            subtotal=self.plan.price,
            tax_rate=0.08,
            tax_amount=self.plan.price * 0.08,
            total_amount=self.plan.price * 1.08,
            status='pending'
        )
        
        self.assertEqual(invoice.subscription, subscription)
        self.assertEqual(invoice.invoice_number, 'INV-001')
        self.assertEqual(invoice.status, 'pending')
    
    def test_usage_record_creation(self):
        """Test usage record creation"""
        usage_record = UsageRecord.objects.create(
            tenant=self.tenant,
            feature=self.users_feature,
            current_usage=3,
            period_start=timezone.now().date().replace(day=1),
            period_end=(timezone.now().date().replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        )
        
        self.assertEqual(usage_record.tenant, self.tenant)
        self.assertEqual(usage_record.feature, self.users_feature)
        self.assertEqual(usage_record.current_usage, 3)


class SubscriptionServiceTests(TestCase):
    """Test subscription service methods"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        from tenants.models import Tenant
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            owner=self.user,
            subdomain='test'
        )
        
        # Create test subscription plan
        self.plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            slug='basic',
            price=29.99,
            billing_cycle='monthly',
            max_users=5,
            max_storage_mb=1024,
            max_cases=50,
            is_active=True,
            is_public=True
        )
        
        # Create test features
        self.users_feature = SubscriptionFeature.objects.create(
            name='Users',
            code='users',
            description='Maximum number of users'
        )
        
        # Add features to plan
        PlanFeature.objects.create(
            plan=self.plan,
            feature=self.users_feature,
            value='5',
            is_included=True
        )
        
        # Create active subscription
        self.subscription = TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
            status='active'
        )
    
    def test_check_and_update_usage_within_limit(self):
        """Test usage check within limits"""
        result = SubscriptionService.check_and_update_usage(
            self.tenant, 'users', 1
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['current_usage'], 1)
        self.assertEqual(result['limit'], 5)
        self.assertEqual(result['usage_percentage'], 20.0)
    
    def test_check_and_update_usage_exceeding_limit(self):
        """Test usage check exceeding limits"""
        # Create usage record at limit
        UsageRecord.objects.create(
            tenant=self.tenant,
            feature=self.users_feature,
            current_usage=5,
            period_start=timezone.now().date().replace(day=1),
            period_end=(timezone.now().date().replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        )
        
        result = SubscriptionService.check_and_update_usage(
            self.tenant, 'users', 1
        )
        
        self.assertFalse(result['success'])
        self.assertIn('Usage limit exceeded', result['message'])
    
    def test_can_access_feature_with_active_subscription(self):
        """Test feature access with active subscription"""
        result = SubscriptionService.can_access_feature(
            self.tenant, 'users'
        )
        
        self.assertTrue(result['can_access'])
    
    def test_can_access_feature_without_subscription(self):
        """Test feature access without subscription"""
        # Create tenant without subscription
        from tenants.models import Tenant
        tenant_no_sub = Tenant.objects.create(
            name='No Sub Tenant',
            owner=self.user,
            subdomain='nosub'
        )
        
        result = SubscriptionService.can_access_feature(
            tenant_no_sub, 'users'
        )
        
        self.assertFalse(result['can_access'])
        self.assertEqual(result['reason'], 'No active subscription')
    
    def test_get_subscription_status_active(self):
        """Test getting subscription status for active subscription"""
        status = SubscriptionService.get_subscription_status(self.tenant)
        
        self.assertEqual(status['status'], 'active')
        self.assertEqual(status['plan_name'], 'Basic Plan')
        self.assertTrue(status['is_active'])
        self.assertFalse(status['is_trial'])
    
    def test_get_subscription_status_none(self):
        """Test getting subscription status for tenant without subscription"""
        # Create tenant without subscription
        from tenants.models import Tenant
        tenant_no_sub = Tenant.objects.create(
            name='No Sub Tenant',
            owner=self.user,
            subdomain='nosub'
        )
        
        status = SubscriptionService.get_subscription_status(tenant_no_sub)
        
        self.assertEqual(status['status'], 'none')


class SubscriptionViewTests(TestCase):
    """Test subscription views"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        from tenants.models import Tenant
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            owner=self.user,
            subdomain='test'
        )
        
        # Create test subscription plan
        self.plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            slug='basic',
            price=29.99,
            billing_cycle='monthly',
            max_users=5,
            max_storage_mb=1024,
            max_cases=50,
            is_active=True,
            is_public=True
        )
        
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')
    
    def test_plan_selection_view(self):
        """Test plan selection view"""
        url = reverse('subscriptions:plan_selection')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Basic Plan')
    
    def test_subscription_detail_view_without_subscription(self):
        """Test subscription detail view without subscription"""
        url = reverse('subscriptions:subscription_detail')
        response = self.client.get(url)
        
        # Should redirect to plan selection
        self.assertEqual(response.status_code, 302)
    
    def test_subscription_detail_view_with_subscription(self):
        """Test subscription detail view with subscription"""
        # Create subscription
        subscription = TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
            status='active'
        )
        
        url = reverse('subscriptions:subscription_detail')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Basic Plan')
    
    def test_billing_dashboard_view(self):
        """Test billing dashboard view"""
        url = reverse('subscriptions:billing_dashboard')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
    
    def test_usage_dashboard_view(self):
        """Test usage dashboard view"""
        url = reverse('subscriptions:usage_dashboard')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)


class SubscriptionDecoratorTests(TestCase):
    """Test subscription decorators"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        from tenants.models import Tenant
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            owner=self.user,
            subdomain='test'
        )
        
        # Create test subscription plan
        self.plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            slug='basic',
            price=29.99,
            billing_cycle='monthly',
            max_users=5,
            max_storage_mb=1024,
            max_cases=50,
            is_active=True,
            is_public=True
        )
        
        # Create test features
        self.users_feature = SubscriptionFeature.objects.create(
            name='Users',
            code='users',
            description='Maximum number of users'
        )
        
        # Add features to plan
        PlanFeature.objects.create(
            plan=self.plan,
            feature=self.users_feature,
            value='5',
            is_included=True
        )
        
        # Create active subscription
        self.subscription = TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
            status='active'
        )
    
    def test_subscription_required_decorator_with_active_subscription(self):
        """Test subscription_required decorator with active subscription"""
        @subscription_required
        def test_view(request):
            return "success"
        
        # Mock request with user and tenant
        from django.http import HttpRequest
        request = HttpRequest()
        request.user = self.user
        
        # This would normally be set by middleware
        self.user.tenant = self.tenant
        
        result = test_view(request)
        self.assertEqual(result, "success")
    
    def test_subscription_feature_required_decorator_with_feature(self):
        """Test subscription_feature_required decorator with included feature"""
        @subscription_feature_required(feature_code='users')
        def test_view(request):
            return "success"
        
        # Mock request with user and tenant
        from django.http import HttpRequest
        request = HttpRequest()
        request.user = self.user
        
        # This would normally be set by middleware
        self.user.tenant = self.tenant
        
        result = test_view(request)
        self.assertEqual(result, "success")
