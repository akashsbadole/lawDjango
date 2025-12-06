"""
Tests for user model functionality in multi-tenant system.
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from tenants.models import Tenant
from accounts.models import CustomUser
from tests.utils import TenantTestCase, MultiTenantTestCase
from tests.fixtures import create_test_tenants, create_test_users_for_tenants

User = CustomUser


class UserModelTests(TenantTestCase):
    """Test CustomUser model."""
    
    def test_user_creation(self):
        """Test basic user creation."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        
        # Set role separately since it's a custom field
        user.role = 'lawyer'
        user.save()
        
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'User')
        self.assertEqual(user.role, 'lawyer')
        self.assertTrue(user.check_password('testpass123'))
        self.assertTrue(user.is_active)
    
    def test_user_creation_with_tenant(self):
        """Test user creation with tenant."""
        user = User.objects.create_user(
            username='tenantuser',
            email='tenant@example.com',
            password='testpass123'
        )
        
        # Set tenant and role separately since they're custom fields
        user.tenant_id = self.active_tenant.id
        user.role = 'lawyer'
        user.save()
        
        user.refresh_from_db()
        self.assertEqual(user.tenant, self.active_tenant)
        self.assertEqual(user.role, 'lawyer')
    
    def test_user_str_representation(self):
        """Test user string representation."""
        self.assertEqual(str(self.admin_user), 'admin@example.com')
        self.assertEqual(str(self.lawyer_user), 'lawyer@example.com')
    
    def test_user_tenant_relationship(self):
        """Test user-tenant relationship."""
        # Create a new user with tenant
        user = self.create_user_for_tenant(self.active_tenant, 'testuser')
        
        # Verify relationship
        user.refresh_from_db()
        self.assertEqual(user.tenant, self.active_tenant)
        
        # Verify reverse relationship
        self.assertIn(user, self.active_tenant.users.all())
    
    def test_user_role_choices(self):
        """Test user role choices."""
        # Test valid roles
        valid_roles = ['admin', 'lawyer', 'paralegal', 'billing_manager', 'staff']
        
        for role in valid_roles:
            user = User.objects.create_user(
                username=f'user_{role}',
                email=f'{role}@example.com',
                password='testpass123'
            )
            
            # Set role separately since it's a custom field
            user.role = role
            user.save()
            
            self.assertEqual(user.role, role)
    
    def test_user_without_tenant(self):
        """Test user without tenant (superuser)."""
        # Superusers might not have a tenant
        superuser = User.objects.create_superuser(
            username='super',
            email='super@example.com',
            password='testpass123'
        )
        
        # Superuser should not have a tenant
        self.assertIsNone(superuser.tenant)
    
    def test_user_unique_email_per_tenant(self):
        """Test that email must be unique per tenant."""
        # Create first user
        user1 = self.create_user_for_tenant(self.active_tenant, 'user1', email='same@example.com')
        
        # Create second user with same email in same tenant (should fail)
        with self.assertRaises(IntegrityError):
            self.create_user_for_tenant(self.active_tenant, 'user2', email='same@example.com')
        
        # Create user with same email in different tenant (should succeed)
        other_tenant = self.create_tenant(name='Other Tenant')
        user2 = self.create_user_for_tenant(other_tenant, 'user2', email='same@example.com')
        
        user2.refresh_from_db()
        self.assertEqual(user2.email, 'same@example.com')
        self.assertEqual(user2.tenant, other_tenant)
    
    def test_user_unique_username_per_tenant(self):
        """Test that username must be unique per tenant."""
        # Create first user
        user1 = self.create_user_for_tenant(self.active_tenant, 'sameuser')
        
        # Create second user with same username in same tenant (should fail)
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username='sameuser',
                email='another@example.com',
                password='testpass123',
                tenant=self.active_tenant
            )
        
        # Create user with same username in different tenant (should succeed)
        other_tenant = self.create_tenant(name='Other Tenant')
        user2 = User.objects.create_user(
            username='sameuser',
            email='another@example.com',
            password='testpass123',
            tenant=other_tenant
        )
        
        self.assertEqual(user2.username, 'sameuser')
        self.assertEqual(user2.tenant, other_tenant)
    
    def test_user_is_staff_property(self):
        """Test user is_staff property based on role."""
        # Admin should be staff
        self.assertTrue(self.admin_user.is_staff)
        
        # Other roles should not be staff
        self.assertFalse(self.lawyer_user.is_staff)
        self.assertFalse(self.paralegal_user.is_staff)
    
    def test_user_is_superuser_property(self):
        """Test user is_superuser property."""
        # Regular users should not be superusers
        self.assertFalse(self.admin_user.is_superuser)
        self.assertFalse(self.lawyer_user.is_superuser)
        self.assertFalse(self.paralegal_user.is_superuser)
        
        # Superuser should be superuser
        self.assertTrue(self.superuser.is_superuser)
    
    def test_user_get_full_name(self):
        """Test user get_full_name method."""
        # User with first and last name
        user = User.objects.create_user(
            username='fulluser',
            email='full@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
        self.assertEqual(user.get_full_name(), 'John Doe')
        
        # User with only first name
        user2 = User.objects.create_user(
            username='firstuser',
            email='first@example.com',
            password='testpass123',
            first_name='Jane'
        )
        self.assertEqual(user2.get_full_name(), 'Jane')
        
        # User with no names
        user3 = User.objects.create_user(
            username='nouser',
            email='no@example.com',
            password='testpass123'
        )
        self.assertEqual(user3.get_full_name(), '')
    
    def test_user_get_short_name(self):
        """Test user get_short_name method."""
        # User with first name
        user = User.objects.create_user(
            username='shortuser',
            email='short@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
        self.assertEqual(user.get_short_name(), 'John')
        
        # User with no first name
        user2 = User.objects.create_user(
            username='noshortuser',
            email='noshort@example.com',
            password='testpass123'
        )
        self.assertEqual(user2.get_short_name(), '')
    
    def test_user_email_user_property(self):
        """Test user email_user property."""
        user = User.objects.create_user(
            username='emailuser',
            email='email@example.com',
            password='testpass123'
        )
        
        # Email should be the username
        self.assertEqual(user.email_user, 'email@example.com')


class UserTenantIsolationTests(MultiTenantTestCase):
    """Test user isolation between tenants."""
    
    def test_users_isolated_by_tenant(self):
        """Test that users are properly isolated by tenant."""
        # Get users for each tenant
        tenant1_users = User.objects.filter(tenant=self.tenant1)
        tenant2_users = User.objects.filter(tenant=self.tenant2)
        tenant3_users = User.objects.filter(tenant=self.tenant3)
        
        # Verify each tenant has its own users
        self.assertGreater(tenant1_users.count(), 0)
        self.assertGreater(tenant2_users.count(), 0)
        self.assertGreater(tenant3_users.count(), 0)
        
        # Verify no cross-tenant users
        for user in tenant1_users:
            self.assertEqual(user.tenant, self.tenant1)
        
        for user in tenant2_users:
            self.assertEqual(user.tenant, self.tenant2)
        
        for user in tenant3_users:
            self.assertEqual(user.tenant, self.tenant3)
    
    def test_user_cannot_access_other_tenants(self):
        """Test that users cannot access other tenants."""
        # Get a user from tenant1
        tenant1_user = User.objects.filter(tenant=self.tenant1).first()
        
        # Try to access tenant2 data
        tenant2_users = User.objects.filter(tenant=self.tenant2)
        
        # User from tenant1 should not be in tenant2 users
        self.assertNotIn(tenant1_user, tenant2_users)
    
    def test_user_deletion_affects_only_tenant(self):
        """Test that user deletion affects only their tenant."""
        # Get initial user counts
        tenant1_count = User.objects.filter(tenant=self.tenant1).count()
        tenant2_count = User.objects.filter(tenant=self.tenant2).count()
        
        # Delete a user from tenant1
        tenant1_user = User.objects.filter(tenant=self.tenant1).first()
        if tenant1_user:
            tenant1_user.delete()
        
        # Verify only tenant1 count changed
        self.assertEqual(
            User.objects.filter(tenant=self.tenant1).count(),
            tenant1_count - 1
        )
        self.assertEqual(
            User.objects.filter(tenant=self.tenant2).count(),
            tenant2_count
        )


class UserAuthenticationTests(TenantTestCase):
    """Test user authentication in multi-tenant context."""
    
    def test_user_authentication_with_tenant(self):
        """Test user authentication with tenant context."""
        # Create a user with tenant
        user = self.create_user_for_tenant(self.active_tenant, 'authuser', password='testpass123')
        
        # Authenticate user
        self.client.login(username='authuser', password='testpass123')
        
        # Verify user is authenticated
        response = self.client.get('/app/active-tenant/dashboard/')
        self.assertEqual(response.status_code, 200)
    
    def test_user_authentication_wrong_tenant(self):
        """Test user authentication with wrong tenant context."""
        # Create a user with tenant1
        user = self.create_user_for_tenant(self.active_tenant, 'wronguser', password='testpass123')
        
        # Try to authenticate with tenant2 context
        self.client.login(username='wronguser', password='testpass123')
        
        # This should fail or redirect depending on implementation
        # For now, we just test the basic authentication
        response = self.client.get('/app/nonexistent-tenant/dashboard/')
        self.assertEqual(response.status_code, 404)
    
    def test_user_authentication_without_tenant(self):
        """Test user authentication without tenant context."""
        # Create a user without tenant (superuser)
        superuser = User.objects.create_superuser(
            username='super',
            email='super@example.com',
            password='testpass123'
        )
        
        # Authenticate superuser
        self.client.login(username='super', password='testpass123')
        
        # Superuser should be able to access non-tenant URLs
        response = self.client.get('/admin/')
        self.assertEqual(response.status_code, 200)
    
    def test_user_authentication_inactive_user(self):
        """Test authentication with inactive user."""
        # Create an inactive user
        user = self.create_user_for_tenant(self.active_tenant, 'inactiveuser')
        user.is_active = False
        user.save()
        
        # Try to authenticate inactive user
        self.client.login(username='inactiveuser', password='testpass123')
        
        # Should fail authentication
        response = self.client.get('/app/active-tenant/dashboard/')
        self.assertEqual(response.status_code, 302)  # Redirect to login


class UserPermissionTests(TenantTestCase):
    """Test user permissions in multi-tenant context."""
    
    def test_user_has_perm_method(self):
        """Test user has_perm method with tenant context."""
        # This would test custom has_perm method if implemented
        # For now, we test the basic Django functionality
        user = self.create_user_for_tenant(self.active_tenant, 'permuser')
        
        # Test with a permission
        has_perm = user.has_perm('clients.view_client')
        self.assertIsInstance(has_perm, bool)
    
    def test_user_has_module_perms_method(self):
        """Test user has_module_perms method with tenant context."""
        user = self.create_user_for_tenant(self.active_tenant, 'moduleuser')
        
        # Test with a module
        has_module_perms = user.has_module_perms('clients')
        self.assertIsInstance(has_module_perms, bool)
    
    def test_user_get_all_permissions(self):
        """Test getting all user permissions."""
        user = self.create_user_for_tenant(self.active_tenant, 'allpermsuser')
        
        # Get all permissions
        permissions = user.get_all_permissions()
        self.assertIsInstance(permissions, set)
    
    def test_user_get_group_permissions(self):
        """Test getting group permissions."""
        user = self.create_user_for_tenant(self.active_tenant, 'groupuser')
        
        # Get group permissions
        permissions = user.get_group_permissions()
        self.assertIsInstance(permissions, set)


class UserQuerySetTests(TenantTestCase):
    """Test custom user queryset methods."""
    
    def test_user_queryset_for_tenant(self):
        """Test filtering users by tenant."""
        # Create users for different tenants
        user1 = self.create_user_for_tenant(self.active_tenant, 'tenant1user')
        user2 = self.create_user_for_tenant(self.suspended_tenant, 'tenant2user')
        user3 = self.create_user_for_tenant(self.deleted_tenant, 'tenant3user')
        
        # Filter by active tenant
        active_users = User.objects.filter(tenant=self.active_tenant)
        suspended_users = User.objects.filter(tenant=self.suspended_tenant)
        deleted_users = User.objects.filter(tenant=self.deleted_tenant)
        
        # Verify results
        self.assertIn(user1, active_users)
        self.assertIn(user2, suspended_users)
        self.assertIn(user3, deleted_users)
        
        # Verify no cross-tenant users
        self.assertNotIn(user2, active_users)
        self.assertNotIn(user3, active_users)
    
    def test_user_queryset_by_role(self):
        """Test filtering users by role."""
        # Create users with different roles
        admin_user = self.create_user_for_tenant(self.active_tenant, 'adminuser', role='admin')
        lawyer_user = self.create_user_for_tenant(self.active_tenant, 'lawyeruser', role='lawyer')
        paralegal_user = self.create_user_for_tenant(self.active_tenant, 'paralegaluser', role='paralegal')
        
        # Filter by role
        admin_users = User.objects.filter(tenant=self.active_tenant, role='admin')
        lawyer_users = User.objects.filter(tenant=self.active_tenant, role='lawyer')
        paralegal_users = User.objects.filter(tenant=self.active_tenant, role='paralegal')
        
        # Verify results
        self.assertIn(admin_user, admin_users)
        self.assertIn(lawyer_user, lawyer_users)
        self.assertIn(paralegal_user, paralegal_users)
        
        # Verify no cross-role users
        self.assertNotIn(lawyer_user, admin_users)
        self.assertNotIn(paralegal_user, lawyer_users)


class UserTransactionTests(TransactionTestCase):
    """Test user functionality with transactions."""
    
    def test_user_creation_rollback_on_error(self):
        """Test user creation rollback on error."""
        # Create a tenant
        tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant'
        )
        
        # Try to create a user with invalid data
        with self.assertRaises(ValidationError):
            User.objects.create_user(
                username='',  # Invalid: empty username
                email='invalid@example.com',
                password='testpass123',
                tenant=tenant
            )
        
        # Verify tenant still exists (transaction rolled back)
        self.assertTrue(Tenant.objects.filter(slug='test-tenant').exists())
    
    def test_user_tenant_change_transaction(self):
        """Test changing user tenant in transaction."""
        # Create user and tenants
        tenant1 = Tenant.objects.create(
            name='Tenant 1',
            slug='tenant-1'
        )
        tenant2 = Tenant.objects.create(
            name='Tenant 2',
            slug='tenant-2'
        )
        
        user = User(
            username='changeuser',
            email='change@example.com',
            tenant=tenant1
        )
        user.set_password('testpass123')
        user.save()
        
        # Change tenant in transaction
        with self.assertNumQueries(1):
            setattr(user, 'tenant', tenant2)
            user.save()
        
        # Verify change
        user.refresh_from_db()
        self.assertEqual(user.tenant, tenant2)