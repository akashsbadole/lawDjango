"""
Test utilities for multi-tenant functionality.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock
import tempfile
import shutil
import os

from tenants.models import Tenant, TenantSettings
from permissions.models import Role, TenantPermission, UserRole

User = get_user_model()


class TenantTestCase(TestCase):
    """
    Base test case for tenant-related tests.
    Provides common setup and utility methods for tenant testing.
    """
    
    @classmethod
    def setUpTestData(cls):
        """Set up data for all test methods."""
        # Create test users
        cls.superuser = User.objects.create_superuser(
            username='superuser',
            email='superuser@example.com',
            password='testpass123'
        )
        
        cls.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='testpass123',
            role='admin'
        )
        
        cls.lawyer_user = User.objects.create_user(
            username='lawyer',
            email='lawyer@example.com',
            password='testpass123',
            role='lawyer'
        )
        
        cls.paralegal_user = User.objects.create_user(
            username='paralegal',
            email='paralegal@example.com',
            password='testpass123',
            role='paralegal'
        )
        
        # Create test tenants
        cls.active_tenant = Tenant.objects.create(
            name='Active Tenant',
            slug='active-tenant',
            plan='pro',
            status='active',
            is_active=True,
            max_users=10,
            max_storage_mb=1024
        )
        
        cls.suspended_tenant = Tenant.objects.create(
            name='Suspended Tenant',
            slug='suspended-tenant',
            plan='basic',
            status='suspended',
            is_active=False,
            max_users=5,
            max_storage_mb=512,
            suspension_reason='Non-payment'
        )
        
        cls.deleted_tenant = Tenant.objects.create(
            name='Deleted Tenant',
            slug='deleted-tenant',
            plan='free',
            status='deleted',
            is_active=False,
            max_users=3,
            max_storage_mb=100,
            deleted_at=timezone.now()
        )
        
        cls.trial_expired_tenant = Tenant.objects.create(
            name='Trial Expired Tenant',
            slug='trial-expired-tenant',
            plan='free',
            status='trial_expired',
            is_active=False,
            max_users=3,
            max_storage_mb=100
        )
        
        # Associate users with tenants
        cls.admin_user.tenant = cls.active_tenant
        cls.admin_user.save()
        
        cls.lawyer_user.tenant = cls.active_tenant
        cls.lawyer_user.save()
        
        cls.paralegal_user.tenant = cls.active_tenant
        cls.paralegal_user.save()
        
        # Create tenant settings
        cls.tenant_settings = TenantSettings.objects.create(
            tenant=cls.active_tenant,
            company_name='Test Law Firm',
            primary_color='#4e73df',
            date_format='Y-m-d',
            timezone='UTC'
        )
    
    def setUp(self):
        """Set up for each test method."""
        self.client = Client()
    
    def login_as_user(self, user):
        """Log in as a specific user."""
        self.client.force_login(user)
        return user
    
    def login_as_superuser(self):
        """Log in as the superuser."""
        return self.login_as_user(self.superuser)
    
    def login_as_admin(self):
        """Log in as the admin user."""
        return self.login_as_user(self.admin_user)
    
    def login_as_lawyer(self):
        """Log in as the lawyer user."""
        return self.login_as_user(self.lawyer_user)
    
    def login_as_paralegal(self):
        """Log in as the paralegal user."""
        return self.login_as_user(self.paralegal_user)
    
    def create_tenant(self, name='Test Tenant', slug='test-tenant', **kwargs):
        """Create a new tenant with default values."""
        defaults = {
            'name': name,
            'slug': slug,
            'plan': 'basic',
            'status': 'active',
            'is_active': True,
            'max_users': 5,
            'max_storage_mb': 512
        }
        defaults.update(kwargs)
        return Tenant.objects.create(**defaults)
    
    def create_user_for_tenant(self, tenant, username='testuser', role='lawyer', **kwargs):
        """Create a user for a specific tenant."""
        defaults = {
            'username': username,
            'email': f'{username}@example.com',
            'password': 'testpass123',
            'role': role,
            'tenant': tenant
        }
        defaults.update(kwargs)
        return User.objects.create_user(**defaults)
    
    def create_role_for_tenant(self, tenant, name='Test Role', permissions=None, **kwargs):
        """Create a role for a specific tenant."""
        defaults = {
            'name': name,
            'tenant': tenant,
            'description': f'Test role: {name}'
        }
        defaults.update(kwargs)
        
        role = Role.objects.create(**defaults)
        
        if permissions:
            for permission_codename in permissions:
                try:
                    permission = TenantPermission.objects.get(codename=permission_codename)
                    role.permissions.add(permission)
                except TenantPermission.DoesNotExist:
                    # Create the permission if it doesn't exist
                    permission = TenantPermission.objects.create(
                        name=f'Permission {permission_codename}',
                        codename=permission_codename,
                        module='test'
                    )
                    role.permissions.add(permission)
        
        return role
    
    def assign_role_to_user(self, user, role, tenant):
        """Assign a role to a user within a tenant."""
        return UserRole.objects.create(
            user=user,
            role=role,
            tenant=tenant
        )
    
    def get_tenant_client(self, tenant):
        """Get a client configured for a specific tenant."""
        client = Client()
        # Set tenant in the request headers
        client.defaults['HTTP_X_TENANT_ID'] = tenant.slug
        return client
    
    def make_tenant_request(self, url, tenant, user=None, method='GET', data=None):
        """Make a request as if it were for a specific tenant."""
        client = self.get_tenant_client(tenant)
        
        if user:
            client.force_login(user)
        
        # Modify URL to include tenant prefix if needed
        if not url.startswith('/app/'):
            url = f'/app/{tenant.slug}{url}'
        
        if method == 'GET':
            return client.get(url)
        elif method == 'POST':
            return client.post(url, data or {})
        elif method == 'PUT':
            return client.put(url, data or {})
        elif method == 'DELETE':
            return client.delete(url)
        
        return client.get(url)


class TenantAwareTestCase(TenantTestCase):
    """
    Test case that automatically sets up tenant context.
    """
    
    def setUp(self):
        """Set up for each test method with tenant context."""
        super().setUp()
        # Set the current tenant for the test
        self.tenant = self.active_tenant
        self.user = self.admin_user
    
    def get_tenant_context(self, tenant=None):
        """Get a mock request with tenant context."""
        from django.http import HttpRequest
        
        request = HttpRequest()
        setattr(request, 'tenant', tenant or self.tenant)
        request.user = self.user
        
        return request


class MultiTenantTestCase(TenantTestCase):
    """
    Test case for testing multi-tenant scenarios with multiple tenants.
    """
    
    @classmethod
    def setUpTestData(cls):
        """Set up data for all test methods with multiple tenants."""
        super().setUpTestData()
        
        # Create additional tenants for multi-tenant testing
        cls.tenant1 = cls.active_tenant
        cls.tenant2 = Tenant.objects.create(
            name='Second Tenant',
            slug='second-tenant',
            plan='enterprise'
        )
        
        cls.tenant3 = Tenant.objects.create(
            name='Third Tenant',
            slug='third-tenant',
            plan='basic'
        )
        
        # Create users for each tenant
        cls.tenant1_admin = User.objects.create_user(
            username='tenant1_admin',
            email='tenant1_admin@example.com',
            password='testpass123',
            role='admin',
            tenant=cls.tenant1
        )
        
        cls.tenant2_admin = User.objects.create_user(
            username='tenant2_admin',
            email='tenant2_admin@example.com',
            password='testpass123',
            role='admin',
            tenant=cls.tenant2
        )
        
        cls.tenant3_admin = User.objects.create_user(
            username='tenant3_admin',
            email='tenant3_admin@example.com',
            password='testpass123',
            role='admin',
            tenant=cls.tenant3
        )


class TenantMixinTestMixin:
    """
    Mixin for testing tenant-specific functionality in views and models.
    """
    
    def assertTenantIsolation(self, model, tenant1, tenant2, tenant1_data, tenant2_data):
        """Assert that data is properly isolated between tenants."""
        # Create objects for different tenants
        obj1 = model.objects.create(tenant=tenant1, **tenant1_data)
        obj2 = model.objects.create(tenant=tenant2, **tenant2_data)
        
        # Verify isolation
        self.assertEqual(model.objects.filter(tenant=tenant1).count(), 1)
        self.assertEqual(model.objects.filter(tenant=tenant2).count(), 1)
        
        # Verify cross-tenant access doesn't work
        with patch('tenants.utils.get_current_tenant', return_value=tenant1):
            self.assertIn(obj1, model.objects.all())
            self.assertNotIn(obj2, model.objects.all())
        
        with patch('tenants.utils.get_current_tenant', return_value=tenant2):
            self.assertIn(obj2, model.objects.all())
            self.assertNotIn(obj1, model.objects.all())
    
    def get_tenant_context(self, tenant):
        """Context manager for a specific tenant."""
        return patch('tenants.utils.get_current_tenant', return_value=tenant)


class FileTestCase(TenantTestCase):
    """
    Test case for file-related functionality with tenant isolation.
    """
    
    def setUp(self):
        """Set up for each test method with temporary directories."""
        super().setUp()
        # Create temporary directory for file tests
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up temporary directories."""
        super().tearDown()
        # Clean up temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_file(self, filename='test.txt', content='Test content'):
        """Create a test file in the temporary directory."""
        file_path = os.path.join(self.temp_dir, filename)
        with open(file_path, 'w') as f:
            f.write(content)
        return file_path
    
    def get_tenant_file_path(self, tenant, filename):
        """Get the tenant-specific file path."""
        return os.path.join(self.temp_dir, tenant.slug, filename)


class PerformanceTestCase(TenantTestCase):
    """
    Test case for performance testing with large datasets.
    """
    
    def create_large_dataset(self, model, tenant, count=1000, **kwargs):
        """Create a large dataset for performance testing."""
        objects = []
        for i in range(count):
            obj_data = {
                'tenant': tenant,
                'name': f'Test Object {i}',
                **kwargs
            }
            objects.append(model(**obj_data))
        
        return model.objects.bulk_create(objects)
    
    def assert_query_performance(self, query, max_time=0.1):
        """Assert that a query executes within the specified time."""
        import time
        start_time = time.time()
        list(query)  # Force evaluation
        end_time = time.time()
        
        execution_time = end_time - start_time
        self.assertLess(execution_time, max_time, 
                       f"Query took {execution_time:.3f}s, expected < {max_time:.3f}s")


class APITestCase(TenantTestCase):
    """
    Test case for API testing with tenant context.
    """
    
    def setUp(self):
        """Set up for each test method with API client."""
        super().setUp()
        # Use Django REST framework's APIClient if available
        try:
            from rest_framework.test import APIClient
            self.api_client = APIClient()
        except ImportError:
            self.api_client = Client()
    
    def authenticate_api_client(self, user):
        """Authenticate the API client with a user."""
        if hasattr(self.api_client, 'force_authenticate'):
            # REST framework client
            self.api_client.force_authenticate(user=user)
        else:
            # Regular Django client
            self.api_client.force_login(user)
    
    def make_api_request(self, method, url, tenant=None, data=None, format='json'):
        """Make an API request with tenant context."""
        if tenant:
            # Set tenant header
            self.api_client.defaults['HTTP_X_TENANT_ID'] = tenant.slug
        
        method_func = getattr(self.api_client, method.lower())
        
        if data and format == 'json':
            return method_func(url, data, content_type='application/json')
        else:
            return method_func(url, data)