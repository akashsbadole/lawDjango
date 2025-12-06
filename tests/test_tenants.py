"""
Tests for tenant models and functionality.
"""

from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
from decimal import Decimal

from tenants.models import Tenant, TenantSettings, TenantStatusHistory
from tests.utils import TenantTestCase, MultiTenantTestCase
from tests.fixtures import create_test_tenants


class TenantModelTests(TenantTestCase):
    """Test the Tenant model."""
    
    def test_tenant_creation(self):
        """Test basic tenant creation."""
        tenant = self.create_tenant(
            name='Test Law Firm',
            slug='test-law-firm',
            plan='pro',
            max_users=20,
            max_storage_mb=2048
        )
        
        self.assertEqual(tenant.name, 'Test Law Firm')
        self.assertEqual(tenant.slug, 'test-law-firm')
        self.assertEqual(tenant.plan, 'pro')
        self.assertEqual(tenant.max_users, 20)
        self.assertEqual(tenant.max_storage_mb, 2048)
        self.assertTrue(tenant.is_active)
        self.assertEqual(tenant.status, 'active')
    
    def test_tenant_str_representation(self):
        """Test tenant string representation."""
        self.assertEqual(str(self.active_tenant), 'Active Tenant')
        self.assertEqual(str(self.suspended_tenant), 'Suspended Tenant')
    
    def test_tenant_slug_auto_generation(self):
        """Test automatic slug generation."""
        tenant = Tenant.objects.create(
            name='New Law Firm PLLC'
        )
        
        self.assertEqual(tenant.slug, 'new-law-firm-pllc')
    
    def test_tenant_slug_uniqueness(self):
        """Test slug uniqueness with counter."""
        tenant1 = Tenant.objects.create(
            name='Test Firm'
        )
        tenant2 = Tenant.objects.create(
            name='Test Firm'
        )
        tenant3 = Tenant.objects.create(
            name='Test Firm'
        )
        
        self.assertEqual(tenant1.slug, 'test-firm')
        self.assertEqual(tenant2.slug, 'test-firm-1')
        self.assertEqual(tenant3.slug, 'test-firm-2')
    
    def test_tenant_property_is_deleted(self):
        """Test is_deleted property."""
        self.assertFalse(self.active_tenant.is_deleted)
        self.assertFalse(self.suspended_tenant.is_deleted)
        self.assertTrue(self.deleted_tenant.is_deleted)
    
    def test_tenant_property_is_suspended(self):
        """Test is_suspended property."""
        self.assertFalse(self.active_tenant.is_suspended)
        self.assertTrue(self.suspended_tenant.is_suspended)
        self.assertFalse(self.deleted_tenant.is_suspended)
    
    def test_tenant_property_is_trial_expired(self):
        """Test is_trial_expired property."""
        self.assertFalse(self.active_tenant.is_trial_expired)
        self.assertFalse(self.suspended_tenant.is_trial_expired)
        self.assertTrue(self.trial_expired_tenant.is_trial_expired)
    
    def test_tenant_can_transition_to(self):
        """Test status transition validation."""
        # Active tenant can transition to these statuses
        self.assertTrue(self.active_tenant.can_transition_to('suspended'))
        self.assertTrue(self.active_tenant.can_transition_to('deleted'))
        self.assertTrue(self.active_tenant.can_transition_to('trial_expired'))
        self.assertFalse(self.active_tenant.can_transition_to('active'))  # Same status
        
        # Suspended tenant can transition to these statuses
        self.assertTrue(self.suspended_tenant.can_transition_to('active'))
        self.assertTrue(self.suspended_tenant.can_transition_to('deleted'))
        self.assertFalse(self.suspended_tenant.can_transition_to('suspended'))
        self.assertFalse(self.suspended_tenant.can_transition_to('trial_expired'))
        
        # Deleted tenant can only be restored to active
        self.assertTrue(self.deleted_tenant.can_transition_to('active'))
        self.assertFalse(self.deleted_tenant.can_transition_to('suspended'))
        self.assertFalse(self.deleted_tenant.can_transition_to('deleted'))
        self.assertFalse(self.deleted_tenant.can_transition_to('trial_expired'))
    
    def test_tenant_soft_delete(self):
        """Test soft delete functionality."""
        tenant = self.create_tenant(name='To Delete')
        user = self.create_user_for_tenant(tenant, 'deleter')
        
        # Verify tenant is active before deletion
        self.assertTrue(tenant.is_active)
        self.assertEqual(tenant.status, 'active')
        self.assertIsNone(tenant.deleted_at)
        
        # Soft delete the tenant
        tenant.soft_delete(reason='Test deletion', changed_by=user)
        
        # Refresh from database
        tenant.refresh_from_db()
        
        # Verify tenant is marked as deleted
        self.assertFalse(tenant.is_active)
        self.assertEqual(tenant.status, 'deleted')
        self.assertIsNotNone(tenant.deleted_at)
        
        # Verify status history was created
        history = TenantStatusHistory.objects.get(
            tenant=tenant,
            old_status='active',
            new_status='deleted',
            reason='Test deletion'
        )
        self.assertEqual(history.changed_by, user)
    
    def test_tenant_restore(self):
        """Test tenant restoration."""
        user = self.create_user_for_tenant(self.deleted_tenant, 'restorer')
        
        # Restore the tenant
        self.deleted_tenant.restore(changed_by=user)
        
        # Refresh from database
        self.deleted_tenant.refresh_from_db()
        
        # Verify tenant is restored
        self.assertTrue(self.deleted_tenant.is_active)
        self.assertEqual(self.deleted_tenant.status, 'active')
        self.assertIsNone(self.deleted_tenant.deleted_at)
        
        # Verify status history was created
        history = TenantStatusHistory.objects.get(
            tenant=self.deleted_tenant,
            old_status='deleted',
            new_status='active',
            reason='Tenant restored'
        )
        self.assertEqual(history.changed_by, user)
    
    def test_tenant_suspend(self):
        """Test tenant suspension."""
        tenant = self.create_tenant(name='To Suspend')
        user = self.create_user_for_tenant(tenant, 'suspender')
        
        # Suspend the tenant
        tenant.suspend(reason='Test suspension', changed_by=user)
        
        # Refresh from database
        tenant.refresh_from_db()
        
        # Verify tenant is suspended
        self.assertFalse(tenant.is_active)
        self.assertEqual(tenant.status, 'suspended')
        self.assertIsNotNone(tenant.suspended_at)
        self.assertEqual(tenant.suspension_reason, 'Test suspension')
        
        # Verify status history was created
        history = TenantStatusHistory.objects.get(
            tenant=tenant,
            old_status='active',
            new_status='suspended',
            reason='Test suspension'
        )
        self.assertEqual(history.changed_by, user)
    
    def test_tenant_unsuspend(self):
        """Test tenant unsuspension."""
        user = self.create_user_for_tenant(self.suspended_tenant, 'unsuspender')
        
        # Unuspend the tenant
        self.suspended_tenant.unsuspend(changed_by=user)
        
        # Refresh from database
        self.suspended_tenant.refresh_from_db()
        
        # Verify tenant is unsuspended
        self.assertTrue(self.suspended_tenant.is_active)
        self.assertEqual(self.suspended_tenant.status, 'active')
        self.assertIsNone(self.suspended_tenant.suspended_at)
        self.assertEqual(self.suspended_tenant.suspension_reason, '')
        
        # Verify status history was created
        history = TenantStatusHistory.objects.get(
            tenant=self.suspended_tenant,
            old_status='suspended',
            new_status='active',
            reason='Tenant unsuspended'
        )
        self.assertEqual(history.changed_by, user)
    
    def test_tenant_expire_trial(self):
        """Test trial expiration."""
        tenant = self.create_tenant(name='Trial Tenant')
        user = self.create_user_for_tenant(tenant, 'expirer')
        
        # Expire the trial
        tenant.expire_trial(changed_by=user)
        
        # Refresh from database
        tenant.refresh_from_db()
        
        # Verify trial is expired
        self.assertFalse(tenant.is_active)
        self.assertEqual(tenant.status, 'trial_expired')
        
        # Verify status history was created
        history = TenantStatusHistory.objects.get(
            tenant=tenant,
            new_status='trial_expired',
            reason='Trial period expired'
        )
        self.assertEqual(history.changed_by, user)
    
    def test_tenant_get_current_user_count(self):
        """Test getting current user count for tenant."""
        # Create additional users for the active tenant
        self.create_user_for_tenant(self.active_tenant, 'user1')
        self.create_user_for_tenant(self.active_tenant, 'user2')
        self.create_user_for_tenant(self.active_tenant, 'user3')
        
        # Count should include the existing users from setUpTestData
        user_count = self.active_tenant.get_current_user_count()
        self.assertGreaterEqual(user_count, 3)
    
    def test_tenant_can_add_users_by_plan(self):
        """Test if tenant can add users based on plan."""
        # Active tenant with max_users=10 should be able to add users
        self.assertTrue(self.active_tenant.can_add_users_by_plan())
        
        # Create a tenant with max_users=1 and add a user
        small_tenant = self.create_tenant(max_users=1)
        self.create_user_for_tenant(small_tenant, 'onlyuser')
        
        # Now it shouldn't be able to add more users
        self.assertFalse(small_tenant.can_add_users_by_plan())
    
    def test_tenant_get_settings(self):
        """Test getting tenant settings."""
        settings = self.active_tenant.get_settings()
        self.assertIsInstance(settings, TenantSettings)
        self.assertEqual(settings.tenant, self.active_tenant)
    
    def test_tenant_get_current_subscription(self):
        """Test getting current subscription."""
        # Initially should return None
        subscription = self.active_tenant.get_current_subscription()
        self.assertIsNone(subscription)
        
        # This would test with actual subscription if subscription module is available
        # For now, we just test the method exists and returns None
    
    def test_tenant_has_active_subscription(self):
        """Test checking if tenant has active subscription."""
        # Initially should return False
        has_subscription = self.active_tenant.has_active_subscription()
        self.assertFalse(has_subscription)
    
    def test_tenant_can_add_user(self):
        """Test if tenant can add users based on subscription."""
        # This would test with actual subscription if available
        # For now, it falls back to plan-based checking
        can_add = self.active_tenant.can_add_user()
        self.assertIsInstance(can_add, bool)
    
    def test_tenant_get_storage_limit(self):
        """Test getting storage limit."""
        limit = self.active_tenant.get_storage_limit()
        self.assertIsInstance(limit, int)
        self.assertGreater(limit, 0)
    
    def test_tenant_get_storage_used(self):
        """Test getting storage used."""
        used = self.active_tenant.get_storage_used()
        self.assertIsInstance(used, int)
        self.assertGreaterEqual(used, 0)
    
    def test_tenant_status_display_with_icon(self):
        """Test status display with icons."""
        active_display = self.active_tenant.get_status_display_with_icon()
        self.assertIn('badge-success', active_display)
        self.assertIn('Active', active_display)
        
        suspended_display = self.suspended_tenant.get_status_display_with_icon()
        self.assertIn('badge-warning', suspended_display)
        self.assertIn('Suspended', suspended_display)
        
        deleted_display = self.deleted_tenant.get_status_display_with_icon()
        self.assertIn('badge-danger', deleted_display)
        self.assertIn('Deleted', deleted_display)
        
        trial_expired_display = self.trial_expired_tenant.get_status_display_with_icon()
        self.assertIn('badge-info', trial_expired_display)
        self.assertIn('Trial Expired', trial_expired_display)


class TenantManagerTests(TenantTestCase):
    """Test the TenantManager."""
    
    def test_manager_active_tenants(self):
        """Test getting active tenants."""
        # This would test custom manager methods if they exist
        # For now, we just test basic functionality
        active_tenants = Tenant.objects.filter(is_active=True, status='active')
        self.assertIn(self.active_tenant, active_tenants)
        self.assertNotIn(self.suspended_tenant, active_tenants)
        self.assertNotIn(self.deleted_tenant, active_tenants)
    
    def test_manager_by_slug(self):
        """Test getting tenant by slug."""
        tenant = Tenant.objects.get(slug=self.active_tenant.slug)
        self.assertEqual(tenant, self.active_tenant)
        
        # Test with non-existent slug
        with self.assertRaises(Tenant.DoesNotExist):
            Tenant.objects.get(slug='non-existent')


class TenantSettingsTests(TenantTestCase):
    """Test the TenantSettings model."""
    
    def test_tenant_settings_creation(self):
        """Test tenant settings creation."""
        tenant = self.create_tenant(name='Settings Test')
        settings = TenantSettings.objects.create(
            tenant=tenant,
            company_name='Test Company',
            primary_color='#ff0000',
            date_format='d/m/Y',
            timezone='US/Eastern'
        )
        
        self.assertEqual(settings.tenant, tenant)
        self.assertEqual(settings.company_name, 'Test Company')
        self.assertEqual(settings.primary_color, '#ff0000')
        self.assertEqual(settings.date_format, 'd/m/Y')
        self.assertEqual(settings.timezone, 'US/Eastern')
    
    def test_tenant_settings_str_representation(self):
        """Test tenant settings string representation."""
        self.assertEqual(str(self.tenant_settings), 'Active Tenant Settings')
    
    def test_tenant_settings_get_logo_url(self):
        """Test getting logo URL."""
        # Test without logo (should return default)
        logo_url = self.tenant_settings.get_logo_url()
        self.assertIsNotNone(logo_url)
        
        # Test with logo (would need actual file upload)
        # For now, just test the method exists
    
    def test_tenant_settings_get_favicon_url(self):
        """Test getting favicon URL."""
        favicon_url = self.tenant_settings.get_favicon_url()
        self.assertIsNotNone(favicon_url)
    
    def test_tenant_settings_get_company_name(self):
        """Test getting company name."""
        # Test with company name set
        self.assertEqual(self.tenant_settings.get_company_name(), 'Test Law Firm')
        
        # Test without company name (should fallback to tenant name)
        self.tenant_settings.company_name = ''
        self.tenant_settings.save()
        self.assertEqual(self.tenant_settings.get_company_name(), 'Active Tenant')
    
    def test_tenant_settings_get_email_from_name(self):
        """Test getting email from name."""
        # Test with email from name set
        self.tenant_settings.email_from_name = 'Custom Name'
        self.tenant_settings.save()
        self.assertEqual(self.tenant_settings.get_email_from_name(), 'Custom Name')
        
        # Test without email from name (should fallback to company name)
        self.tenant_settings.email_from_name = ''
        self.tenant_settings.save()
        self.assertEqual(self.tenant_settings.get_email_from_name(), 'Test Law Firm')
    
    def test_tenant_settings_get_email_from_address(self):
        """Test getting email from address."""
        # Test with email from address set
        self.tenant_settings.email_from_address = 'custom@example.com'
        self.tenant_settings.save()
        self.assertEqual(self.tenant_settings.get_email_from_address(), 'custom@example.com')
        
        # Test without email from address (should generate default)
        self.tenant_settings.email_from_address = ''
        self.tenant_settings.save()
        self.assertEqual(self.tenant_settings.get_email_from_address(), 'noreply@active-tenant.lawfirm.com')
    
    def test_tenant_settings_get_brand_colors(self):
        """Test getting brand colors."""
        colors = self.tenant_settings.get_brand_colors()
        self.assertIsInstance(colors, dict)
        self.assertIn('primary', colors)
        self.assertIn('secondary', colors)
        self.assertIn('accent', colors)
        self.assertIn('text', colors)
        self.assertIn('background', colors)
    
    def test_tenant_settings_get_color_variations(self):
        """Test getting color variations."""
        variations = self.tenant_settings.get_color_variations('#4e73df')
        self.assertIsInstance(variations, dict)
        self.assertIn('light', variations)
        self.assertIn('dark', variations)
        self.assertIn('background', variations)
    
    def test_tenant_settings_get_theme_css_variables(self):
        """Test getting theme CSS variables."""
        css_vars = self.tenant_settings.get_theme_css_variables()
        self.assertIsInstance(css_vars, dict)
        self.assertIn('--brand-primary', css_vars)
        self.assertIn('--brand-font-family', css_vars)
    
    def test_tenant_settings_get_company_info(self):
        """Test getting company information."""
        company_info = self.tenant_settings.get_company_info()
        self.assertIsInstance(company_info, dict)
        self.assertIn('name', company_info)
        self.assertIn('tagline', company_info)
        self.assertIn('website', company_info)
        self.assertIn('address', company_info)
        self.assertIn('phone', company_info)
        self.assertIn('email', company_info)
    
    def test_tenant_settings_get_email_settings(self):
        """Test getting email settings."""
        email_settings = self.tenant_settings.get_email_settings()
        self.assertIsInstance(email_settings, dict)
        self.assertIn('from_name', email_settings)
        self.assertIn('from_address', email_settings)
        self.assertIn('reply_to', email_settings)
        self.assertIn('header', email_settings)
        self.assertIn('footer', email_settings)
    
    def test_tenant_settings_get_default_categories_list(self):
        """Test getting default document categories as list."""
        categories = self.tenant_settings.get_default_categories_list()
        self.assertIsInstance(categories, list)
        self.assertIn('contract', categories)
        self.assertIn('court_filing', categories)
    
    def test_tenant_settings_set_default_categories_list(self):
        """Test setting default document categories from list."""
        new_categories = ['contract', 'evidence', 'research', 'custom']
        self.tenant_settings.set_default_categories_list(new_categories)
        self.tenant_settings.save()
        
        categories = self.tenant_settings.get_default_categories_list()
        self.assertEqual(categories, new_categories)
    
    def test_tenant_settings_get_password_requirements(self):
        """Test getting password requirements."""
        requirements = self.tenant_settings.get_password_requirements()
        self.assertIsInstance(requirements, dict)
        self.assertIn('min_length', requirements)
        self.assertIn('require_letters', requirements)
        self.assertIn('require_numbers', requirements)
        self.assertIn('require_symbols', requirements)
    
    def test_tenant_settings_is_feature_enabled(self):
        """Test checking if feature is enabled."""
        # Test enabled features
        self.assertTrue(self.tenant_settings.is_feature_enabled('document_sharing'))
        self.assertTrue(self.tenant_settings.is_feature_enabled('time_tracking'))
        
        # Test disabled feature
        self.assertFalse(self.tenant_settings.is_feature_enabled('client_portal'))
        
        # Test non-existent feature
        self.assertFalse(self.tenant_settings.is_feature_enabled('non_existent'))


class TenantStatusHistoryTests(TenantTestCase):
    """Test the TenantStatusHistory model."""
    
    def test_status_history_creation(self):
        """Test status history creation."""
        history = TenantStatusHistory.objects.create(
            tenant=self.active_tenant,
            old_status='active',
            new_status='suspended',
            reason='Test suspension',
            changed_by=self.admin_user
        )
        
        self.assertEqual(history.tenant, self.active_tenant)
        self.assertEqual(history.old_status, 'active')
        self.assertEqual(history.new_status, 'suspended')
        self.assertEqual(history.reason, 'Test suspension')
        self.assertEqual(history.changed_by, self.admin_user)
        self.assertIsNotNone(history.changed_at)
    
    def test_status_history_str_representation(self):
        """Test status history string representation."""
        history = TenantStatusHistory.objects.create(
            tenant=self.active_tenant,
            old_status='active',
            new_status='suspended',
            reason='Test'
        )
        
        expected = f"Active Tenant: active → suspended at {history.changed_at}"
        self.assertEqual(str(history), expected)


class TenantTransactionTests(TransactionTestCase):
    """Test tenant functionality with transactions."""
    
    def setUp(self):
        """Set up for transaction tests."""
        self.tenant = Tenant.objects.create(
            name='Transaction Test',
            slug='transaction-test',
            plan='basic',
            status='active',
            is_active=True
        )
    
    def test_tenant_deletion_with_history(self):
        """Test that tenant deletion also deletes related history."""
        # Create status history
        TenantStatusHistory.objects.create(
            tenant=self.tenant,
            old_status='active',
            new_status='suspended',
            reason='Test'
        )
        
        # Create tenant settings
        TenantSettings.objects.create(
            tenant=self.tenant,
            company_name='Test Company'
        )
        
        # Verify related objects exist
        self.assertEqual(TenantStatusHistory.objects.filter(tenant=self.tenant).count(), 1)
        self.assertEqual(TenantSettings.objects.filter(tenant=self.tenant).count(), 1)
        
        # Delete tenant
        self.tenant.permanent_delete()
        
        # Verify related objects are deleted
        self.assertEqual(TenantStatusHistory.objects.filter(tenant=self.tenant).count(), 0)
        self.assertEqual(TenantSettings.objects.filter(tenant=self.tenant).count(), 0)
    
    def test_tenant_soft_delete_preserves_history(self):
        """Test that soft delete preserves status history."""
        # Create status history
        history = TenantStatusHistory.objects.create(
            tenant=self.tenant,
            old_status='active',
            new_status='suspended',
            reason='Test'
        )
        
        # Soft delete tenant
        self.tenant.soft_delete()
        
        # Verify history is preserved
        self.assertTrue(TenantStatusHistory.objects.filter(pk=history.pk).exists())
        
        # Verify tenant is marked as deleted but still exists
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.status, 'deleted')
        self.assertIsNotNone(self.tenant.deleted_at)