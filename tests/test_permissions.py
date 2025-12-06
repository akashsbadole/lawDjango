"""
Tests for permission system in multi-tenant context.
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from permissions.models import TenantPermission, Role, UserRole
from tenants.models import Tenant
from tests.utils import TenantTestCase, MultiTenantTestCase
from tests.fixtures import create_test_permissions, create_test_roles, create_test_user_roles

User = get_user_model()


class TenantPermissionTests(TenantTestCase):
    """Test TenantPermission model."""
    
    def test_permission_creation(self):
        """Test basic permission creation."""
        permission = TenantPermission.objects.create(
            name='View Clients',
            codename='clients.view_client',
            description='View client information',
            module='clients'
        )
        
        self.assertEqual(permission.name, 'View Clients')
        self.assertEqual(permission.codename, 'clients.view_client')
        self.assertEqual(permission.description, 'View client information')
        self.assertEqual(permission.module, 'clients')
        self.assertIsNotNone(permission.created_at)
    
    def test_permission_str_representation(self):
        """Test permission string representation."""
        permission = TenantPermission.objects.create(
            name='Test Permission',
            codename='test.permission',
            module='test'
        )
        
        self.assertEqual(str(permission), 'test.Test Permission')
    
    def test_permission_unique_codename(self):
        """Test that permission codename must be unique."""
        # Create first permission
        TenantPermission.objects.create(
            name='Test Permission',
            codename='test.unique',
            module='test'
        )
        
        # Try to create second permission with same codename
        with self.assertRaises(IntegrityError):
            TenantPermission.objects.create(
                name='Another Test Permission',
                codename='test.unique',
                module='test'
            )
    
    def test_permission_ordering(self):
        """Test that permissions are ordered by module and name."""
        # Create permissions in different modules
        perm1 = TenantPermission.objects.create(
            name='Z Permission',
            codename='z.permission',
            module='a'
        )
        perm2 = TenantPermission.objects.create(
            name='A Permission',
            codename='a.permission',
            module='a'
        )
        perm3 = TenantPermission.objects.create(
            name='M Permission',
            codename='m.permission',
            module='z'
        )
        
        # Get all permissions
        permissions = list(TenantPermission.objects.all())
        
        # Should be ordered by module first, then name
        self.assertEqual(permissions[0], perm2)  # a.a
        self.assertEqual(permissions[1], perm1)  # a.z
        self.assertEqual(permissions[2], perm3)  # z.m


class RoleTests(TenantTestCase):
    """Test Role model."""
    
    def test_role_creation(self):
        """Test basic role creation."""
        permission = TenantPermission.objects.create(
            name='Test Permission',
            codename='test.permission',
            module='test'
        )
        
        role = Role.objects.create(
            name='Test Role',
            tenant=self.active_tenant,
            description='A test role for testing'
        )
        role.permissions.add(permission)
        
        self.assertEqual(role.name, 'Test Role')
        self.assertEqual(role.tenant, self.active_tenant)
        self.assertEqual(role.description, 'A test role for testing')
        self.assertFalse(role.is_system_role)
        self.assertIn(permission, role.permissions.all())
    
    def test_role_str_representation(self):
        """Test role string representation."""
        role = Role.objects.create(
            name='Test Role',
            tenant=self.active_tenant
        )
        
        self.assertEqual(str(role), f'Test Role ({self.active_tenant.name})')
    
    def test_role_unique_name_per_tenant(self):
        """Test that role name must be unique per tenant."""
        # Create first role
        Role.objects.create(
            name='Same Role',
            tenant=self.active_tenant
        )
        
        # Try to create second role with same name in same tenant
        with self.assertRaises(IntegrityError):
            Role.objects.create(
                name='Same Role',
                tenant=self.active_tenant
            )
        
        # Create role with same name in different tenant (should succeed)
        other_tenant = self.create_tenant(name='Other Tenant')
        role2 = Role.objects.create(
            name='Same Role',
            tenant=other_tenant
        )
        
        self.assertEqual(role2.name, 'Same Role')
        self.assertEqual(role2.tenant, other_tenant)
    
    def test_role_system_role_flag(self):
        """Test system role flag."""
        # Regular role
        regular_role = Role.objects.create(
            name='Regular Role',
            tenant=self.active_tenant,
            is_system_role=False
        )
        
        # System role
        system_role = Role.objects.create(
            name='System Role',
            tenant=self.active_tenant,
            is_system_role=True
        )
        
        self.assertFalse(regular_role.is_system_role)
        self.assertTrue(system_role.is_system_role)
    
    def test_role_has_permission_method(self):
        """Test role has_permission method."""
        # Create permissions
        perm1 = TenantPermission.objects.create(
            name='Permission 1',
            codename='test.permission1',
            module='test'
        )
        perm2 = TenantPermission.objects.create(
            name='Permission 2',
            codename='test.permission2',
            module='test'
        )
        perm3 = TenantPermission.objects.create(
            name='Permission 3',
            codename='test.permission3',
            module='test'
        )
        
        # Create role with some permissions
        role = Role.objects.create(
            name='Test Role',
            tenant=self.active_tenant
        )
        role.permissions.add(perm1, perm3)
        
        # Test permission checking
        self.assertTrue(role.has_permission('test.permission1'))
        self.assertTrue(role.has_permission('test.permission3'))
        self.assertFalse(role.has_permission('test.permission2'))
        self.assertFalse(role.has_permission('nonexistent.permission'))
    
    def test_role_ordering(self):
        """Test that roles are ordered by name."""
        # Create roles in different order
        role1 = Role.objects.create(
            name='Z Role',
            tenant=self.active_tenant
        )
        role2 = Role.objects.create(
            name='A Role',
            tenant=self.active_tenant
        )
        role3 = Role.objects.create(
            name='M Role',
            tenant=self.active_tenant
        )
        
        # Get all roles
        roles = list(Role.objects.all())
        
        # Should be ordered by name
        self.assertEqual(roles[0], role2)  # A
        self.assertEqual(roles[1], role3)  # M
        self.assertEqual(roles[2], role1)  # Z


class UserRoleTests(TenantTestCase):
    """Test UserRole model."""
    
    def test_user_role_creation(self):
        """Test basic user role creation."""
        permission = TenantPermission.objects.create(
            name='Test Permission',
            codename='test.permission',
            module='test'
        )
        
        role = Role.objects.create(
            name='Test Role',
            tenant=self.active_tenant,
            description='A test role'
        )
        role.permissions.add(permission)
        
        user_role = UserRole.objects.create(
            user=self.admin_user,
            role=role,
            tenant=self.active_tenant,
            assigned_by=self.superuser
        )
        
        self.assertEqual(user_role.user, self.admin_user)
        self.assertEqual(user_role.role, role)
        self.assertEqual(user_role.tenant, self.active_tenant)
        self.assertEqual(user_role.assigned_by, self.superuser)
        self.assertIsNotNone(user_role.assigned_at)
    
    def test_user_role_str_representation(self):
        """Test user role string representation."""
        role = Role.objects.create(
            name='Test Role',
            tenant=self.active_tenant
        )
        
        user_role = UserRole.objects.create(
            user=self.admin_user,
            role=role,
            tenant=self.active_tenant
        )
        
        expected = f"{self.admin_user.email} - Test Role ({self.active_tenant.name})"
        self.assertEqual(str(user_role), expected)
    
    def test_user_role_unique_combination(self):
        """Test that user-role-tenant combination must be unique."""
        role = Role.objects.create(
            name='Test Role',
            tenant=self.active_tenant
        )
        
        # Create first user role
        UserRole.objects.create(
            user=self.admin_user,
            role=role,
            tenant=self.active_tenant
        )
        
        # Try to create duplicate
        with self.assertRaises(IntegrityError):
            UserRole.objects.create(
                user=self.admin_user,
                role=role,
                tenant=self.active_tenant
            )
        
        # Create same user-role combination for different tenant (should succeed)
        other_tenant = self.create_tenant(name='Other Tenant')
        other_role = Role.objects.create(
            name='Other Role',
            tenant=other_tenant
        )
        
        user_role2 = UserRole.objects.create(
            user=self.admin_user,
            role=other_role,
            tenant=other_tenant
        )
        
        self.assertEqual(user_role2.user, self.admin_user)
        self.assertEqual(user_role2.tenant, other_tenant)
    
    def test_user_role_ordering(self):
        """Test that user roles are ordered by assignment time."""
        role1 = Role.objects.create(
            name='Role 1',
            tenant=self.active_tenant
        )
        role2 = Role.objects.create(
            name='Role 2',
            tenant=self.active_tenant
        )
        
        # Create roles with delay
        user_role1 = UserRole.objects.create(
            user=self.admin_user,
            role=role1,
            tenant=self.active_tenant
        )
        
        # Create second role after a delay
        import time
        time.sleep(0.01)
        
        user_role2 = UserRole.objects.create(
            user=self.admin_user,
            role=role2,
            tenant=self.active_tenant
        )
        
        # Get all user roles
        user_roles = list(UserRole.objects.all())
        
        # Should be ordered by assigned_at (newest first)
        self.assertEqual(user_roles[0], user_role2)
        self.assertEqual(user_roles[1], user_role1)


class PermissionIsolationTests(MultiTenantTestCase):
    """Test permission isolation between tenants."""
    
    def test_permissions_shared_across_tenants(self):
        """Test that permissions are shared across tenants."""
        # Create permissions
        permissions = create_test_permissions()
        
        # Verify permissions are available to all tenants
        for tenant in [self.tenant1, self.tenant2, self.tenant3]:
            tenant_permissions = TenantPermission.objects.all()
            for permission in permissions:
                self.assertIn(permission, tenant_permissions)
    
    def test_roles_isolated_by_tenant(self):
        """Test that roles are isolated by tenant."""
        # Create roles for each tenant
        roles = create_test_roles([self.tenant1, self.tenant2, self.tenant3], [])
        
        # Get roles for each tenant
        tenant1_roles = Role.objects.filter(tenant=self.tenant1)
        tenant2_roles = Role.objects.filter(tenant=self.tenant2)
        tenant3_roles = Role.objects.filter(tenant=self.tenant3)
        
        # Verify each tenant has its own roles
        self.assertGreater(tenant1_roles.count(), 0)
        self.assertGreater(tenant2_roles.count(), 0)
        self.assertGreater(tenant3_roles.count(), 0)
        
        # Verify no cross-tenant roles
        for role in tenant1_roles:
            self.assertEqual(role.tenant, self.tenant1)
        
        for role in tenant2_roles:
            self.assertEqual(role.tenant, self.tenant2)
        
        for role in tenant3_roles:
            self.assertEqual(role.tenant, self.tenant3)
    
    def test_user_roles_isolated_by_tenant(self):
        """Test that user roles are isolated by tenant."""
        # Create users and roles for each tenant
        users = []
        for tenant in [self.tenant1, self.tenant2, self.tenant3]:
            for i in range(3):
                user = User.objects.create_user(
                    username=f'user_{tenant.slug}_{i}',
                    email=f'user{i}@{tenant.slug}.example.com',
                    password='testpass123'
                )
                setattr(user, 'tenant', tenant)
                user.save()
                users.append(user)
        
        roles = create_test_roles([self.tenant1, self.tenant2, self.tenant3], [])
        user_roles = create_test_user_roles(users, roles)
        
        # Get user roles for each tenant
        tenant1_user_roles = UserRole.objects.filter(tenant=self.tenant1)
        tenant2_user_roles = UserRole.objects.filter(tenant=self.tenant2)
        tenant3_user_roles = UserRole.objects.filter(tenant=self.tenant3)
        
        # Verify each tenant has its own user roles
        self.assertGreater(tenant1_user_roles.count(), 0)
        self.assertGreater(tenant2_user_roles.count(), 0)
        self.assertGreater(tenant3_user_roles.count(), 0)
        
        # Verify no cross-tenant user roles
        for user_role in tenant1_user_roles:
            self.assertEqual(user_role.tenant, self.tenant1)
        
        for user_role in tenant2_user_roles:
            self.assertEqual(user_role.tenant, self.tenant2)
        
        for user_role in tenant3_user_roles:
            self.assertEqual(user_role.tenant, self.tenant3)


class PermissionIntegrationTests(TenantTestCase):
    """Test permission integration with Django's auth system."""
    
    def test_user_permissions_through_roles(self):
        """Test that users get permissions through roles."""
        # Create permissions
        perm1 = TenantPermission.objects.create(
            name='Permission 1',
            codename='test.permission1',
            module='test'
        )
        perm2 = TenantPermission.objects.create(
            name='Permission 2',
            codename='test.permission2',
            module='test'
        )
        
        # Create role with permissions
        role = Role.objects.create(
            name='Test Role',
            tenant=self.active_tenant
        )
        role.permissions.add(perm1, perm2)
        
        # Assign role to user
        UserRole.objects.create(
            user=self.admin_user,
            role=role,
            tenant=self.active_tenant
        )
        
        # Test user has permissions through role
        # This would require custom has_perm implementation
        # For now, we test the relationship exists
        user_role = UserRole.objects.get(user=self.admin_user, tenant=self.active_tenant)
        self.assertEqual(user_role.role, role)
        self.assertIn(perm1, user_role.role.permissions.all())
        self.assertIn(perm2, user_role.role.permissions.all())
    
    def test_multiple_roles_per_user(self):
        """Test that users can have multiple roles."""
        # Create permissions and roles
        perm1 = TenantPermission.objects.create(
            name='Permission 1',
            codename='test.permission1',
            module='test'
        )
        perm2 = TenantPermission.objects.create(
            name='Permission 2',
            codename='test.permission2',
            module='test'
        )
        
        role1 = Role.objects.create(
            name='Role 1',
            tenant=self.active_tenant
        )
        role1.permissions.add(perm1)
        
        role2 = Role.objects.create(
            name='Role 2',
            tenant=self.active_tenant
        )
        role2.permissions.add(perm2)
        
        # Assign both roles to user
        UserRole.objects.create(
            user=self.admin_user,
            role=role1,
            tenant=self.active_tenant
        )
        UserRole.objects.create(
            user=self.admin_user,
            role=role2,
            tenant=self.active_tenant
        )
        
        # Verify user has both roles
        user_roles = UserRole.objects.filter(user=self.admin_user, tenant=self.active_tenant)
        self.assertEqual(user_roles.count(), 2)
        
        role_ids = list(user_roles.values_list('role_id', flat=True))
        self.assertIn(role1.pk, role_ids)
        self.assertIn(role2.pk, role_ids)
    
    def test_role_permission_inheritance(self):
        """Test that roles can inherit permissions from other roles."""
        # This would test role inheritance if implemented
        # For now, we test basic permission assignment
        perm = TenantPermission.objects.create(
            name='Test Permission',
            codename='test.permission',
            module='test'
        )
        
        parent_role = Role.objects.create(
            name='Parent Role',
            tenant=self.active_tenant
        )
        parent_role.permissions.add(perm)
        
        child_role = Role.objects.create(
            name='Child Role',
            tenant=self.active_tenant
        )
        
        # If inheritance is implemented, child would get parent's permissions
        # For now, we just test basic functionality
        self.assertIn(perm, parent_role.permissions.all())
        self.assertNotIn(perm, child_role.permissions.all())


class PermissionTransactionTests(TransactionTestCase):
    """Test permission functionality with transactions."""
    
    def test_role_creation_rollback_on_error(self):
        """Test role creation rollback on error."""
        # Create a tenant for transaction tests
        # Create a tenant for transaction tests
        tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant'
        )
        
        # Try to create a role with invalid data
        with self.assertRaises(ValidationError):
            Role.objects.create(
                name='',  # Invalid: empty name
                tenant=tenant
            )
        
        # Verify tenant still exists (transaction rolled back)
        self.assertTrue(Tenant.objects.filter(slug='test-tenant').exists())
    
    def test_user_role_assignment_rollback(self):
        """Test user role assignment rollback on error."""
        # Create user and role
        # Create a user and role for transaction tests
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        setattr(user, 'tenant', self.active_tenant)
        user.save()
        
        role = Role.objects.create(
            name='Test Role',
            tenant=self.active_tenant
        )
        
        # Try to assign invalid user role
        with self.assertRaises(IntegrityError):
            UserRole.objects.create(
                user=None,  # Invalid: no user
                role=role,
                tenant=self.active_tenant
            )
        
        # Verify user and role still exist
        self.assertTrue(User.objects.filter(username='testuser').exists())
        self.assertTrue(Role.objects.filter(name='Test Role').exists())