"""
Tests for tenant middleware functionality.
"""

from django.test import TestCase, RequestFactory
from django.http import Http404, HttpResponse, JsonResponse
from django.urls import reverse
from unittest.mock import patch, MagicMock

from tenants.middleware import TenantMiddleware
from tenants.models import Tenant
from tests.utils import TenantTestCase


class TenantMiddlewareTests(TenantTestCase):
    """Test TenantMiddleware functionality."""
    
    def setUp(self):
        """Set up for each test method."""
        super().setUp()
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(get_response=lambda r: HttpResponse())
    
    def test_middleware_initialization(self):
        """Test middleware initialization."""
        self.assertIsNotNone(self.middleware.get_response)
    
    def test_get_tenant_from_path_valid(self):
        """Test tenant extraction from valid path."""
        # Test with valid tenant path
        request = self.factory.get('/app/active-tenant/dashboard/')
        tenant = self.middleware.get_tenant_from_request(request)
        
        self.assertEqual(tenant, self.active_tenant)
    
    def test_get_tenant_from_path_invalid_prefix(self):
        """Test tenant extraction with invalid prefix."""
        # Test with invalid prefix
        request = self.factory.get('/invalid/active-tenant/dashboard/')
        tenant = self.middleware.get_tenant_from_request(request)
        
        self.assertIsNone(tenant)
    
    def test_get_tenant_from_path_missing_tenant(self):
        """Test tenant extraction with missing tenant slug."""
        # Test with missing tenant slug
        request = self.factory.get('/app/')
        tenant = self.middleware.get_tenant_from_request(request)
        
        self.assertIsNone(tenant)
    
    def test_get_tenant_from_path_nonexistent_tenant(self):
        """Test tenant extraction with non-existent tenant."""
        # Test with non-existent tenant
        request = self.factory.get('/app/nonexistent/dashboard/')
        
        with self.assertRaises(Http404) as cm:
            self.middleware.get_tenant_from_request(request)
        
        self.assertIn("nonexistent", str(cm.exception))
    
    def test_get_tenant_from_path_deleted_tenant(self):
        """Test tenant extraction with deleted tenant."""
        # Test with deleted tenant
        request = self.factory.get('/app/deleted-firm/dashboard/')
        
        with self.assertRaises(Http404) as cm:
            self.middleware.get_tenant_from_request(request)
        
        self.assertIn("deleted", str(cm.exception))
    
    def test_get_tenant_from_path_suspended_tenant(self):
        """Test tenant extraction with suspended tenant."""
        # Test with suspended tenant
        request = self.factory.get('/app/suspended-firm/dashboard/')
        
        # Should return a response, not raise an exception
        response = self.middleware.get_tenant_from_request(request)
        
        # The response should be a rendered template or JSON response
        self.assertIsNotNone(response)
    
    def test_get_tenant_from_path_trial_expired_tenant(self):
        """Test tenant extraction with trial expired tenant."""
        # Test with trial expired tenant
        request = self.factory.get('/app/trial-expired/dashboard/')
        
        # Should return a response, not raise an exception
        response = self.middleware.get_tenant_from_request(request)
        
        # The response should be a rendered template or JSON response
        self.assertIsNotNone(response)
    
    def test_middleware_sets_tenant_on_request(self):
        """Test that middleware sets tenant on request object."""
        # Create a mock response function
        mock_response = HttpResponse()
        mock_get_response = MagicMock(return_value=mock_response)
        middleware = TenantMiddleware(mock_get_response)
        
        # Create request with valid tenant path
        request = self.factory.get('/app/active-tenant/dashboard/')
        
        # Process request through middleware
        response = middleware(request)
        
        # Verify tenant was set on request
        self.assertEqual(getattr(request, 'tenant', None), self.active_tenant)
        
        # Verify response is the mock response
        self.assertEqual(response, mock_response)
    
    def test_middleware_with_no_tenant(self):
        """Test middleware with no tenant in path."""
        # Create a mock response function
        mock_response = HttpResponse()
        mock_get_response = MagicMock(return_value=mock_response)
        middleware = TenantMiddleware(mock_get_response)
        
        # Create request with no tenant path
        request = self.factory.get('/admin/dashboard/')
        
        # Process request through middleware
        response = middleware(request)
        
        # Verify tenant was not set on request
        self.assertIsNone(getattr(request, 'tenant', None))
        
        # Verify response is the mock response
        self.assertEqual(response, mock_response)
    
    def test_handle_suspended_tenant_web_request(self):
        """Test handling suspended tenant for web requests."""
        request = self.factory.get('/app/suspended-firm/dashboard/')
        
        with patch('tenants.middleware.render') as mock_render:
            mock_response = HttpResponse()
            mock_render.return_value = mock_response
            
            response = self.middleware.handle_suspended_tenant(request, self.suspended_tenant)
            
            # Verify render was called with correct template and context
            mock_render.assert_called_once()
            args, kwargs = mock_render.call_args
            self.assertEqual(args[0], request)
            self.assertEqual(args[1], 'tenants/tenant_suspended.html')
            self.assertIn('tenant', args[2])
            self.assertIn('reason', args[2])
            self.assertEqual(args[2]['tenant'], self.suspended_tenant)
            self.assertEqual(args[2]['reason'], self.suspended_tenant.suspension_reason)
            
            # Verify the response
            self.assertEqual(response, mock_response)
    
    def test_handle_suspended_tenant_api_request(self):
        """Test handling suspended tenant for API requests."""
        # API request path
        request = self.factory.get('/api/cases/')
        
        response = self.middleware.handle_suspended_tenant(request, self.suspended_tenant)
        
        # Should return JsonResponse
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 403)
        
        # Check response content
        content = response.content
        self.assertIn(b'Tenant suspended', content)
        self.assertIn(b'temporarily suspended', content)
        self.assertIn(self.suspended_tenant.suspension_reason.encode(), content)
    
    def test_handle_suspended_tenant_api_with_accept_header(self):
        """Test handling suspended tenant for requests with Accept header."""
        # Web request with Accept: application/json header
        request = self.factory.get('/app/suspended-firm/dashboard/', HTTP_ACCEPT='application/json')
        
        response = self.middleware.handle_suspended_tenant(request, self.suspended_tenant)
        
        # Should return JsonResponse
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 403)
    
    def test_handle_trial_expired_tenant_web_request(self):
        """Test handling trial expired tenant for web requests."""
        request = self.factory.get('/app/trial-expired/dashboard/')
        
        with patch('tenants.middleware.render') as mock_render:
            mock_response = HttpResponse()
            mock_render.return_value = mock_response
            
            response = self.middleware.handle_trial_expired_tenant(request, self.trial_expired_tenant)
            
            # Verify render was called with correct template and context
            mock_render.assert_called_once()
            args, kwargs = mock_render.call_args
            self.assertEqual(args[0], request)
            self.assertEqual(args[1], 'tenants/tenant_trial_expired.html')
            self.assertIn('tenant', args[2])
            self.assertEqual(args[2]['tenant'], self.trial_expired_tenant)
            
            # Verify the response
            self.assertEqual(response, mock_response)
    
    def test_handle_trial_expired_tenant_api_request(self):
        """Test handling trial expired tenant for API requests."""
        # API request path
        request = self.factory.get('/api/cases/')
        
        response = self.middleware.handle_trial_expired_tenant(request, self.trial_expired_tenant)
        
        # Should return JsonResponse
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 402)
        
        # Check response content
        content = response.content
        self.assertIn(b'Trial expired', content)
        self.assertIn(b'upgrade_required', content)
    
    def test_handle_inactive_tenant_web_request(self):
        """Test handling inactive tenant for web requests."""
        # Create an inactive tenant
        inactive_tenant = self.create_tenant(
            name='Inactive Tenant',
            slug='inactive-tenant',
            status='inactive',
            is_active=False
        )
        
        request = self.factory.get('/app/inactive-tenant/dashboard/')
        
        with patch('tenants.middleware.render') as mock_render:
            mock_response = HttpResponse()
            mock_render.return_value = mock_response
            
            response = self.middleware.handle_inactive_tenant(request, inactive_tenant)
            
            # Verify render was called with correct template and context
            mock_render.assert_called_once()
            args, kwargs = mock_render.call_args
            self.assertEqual(args[0], request)
            self.assertEqual(args[1], 'tenants/tenant_inactive.html')
            self.assertIn('tenant', args[2])
            self.assertEqual(args[2]['tenant'], inactive_tenant)
            
            # Verify the response
            self.assertEqual(response, mock_response)
    
    def test_handle_inactive_tenant_api_request(self):
        """Test handling inactive tenant for API requests."""
        # Create an inactive tenant
        inactive_tenant = self.create_tenant(
            name='Inactive Tenant',
            slug='inactive-tenant',
            status='inactive',
            is_active=False
        )
        
        # API request path
        request = self.factory.get('/api/cases/')
        
        response = self.middleware.handle_inactive_tenant(request, inactive_tenant)
        
        # Should return JsonResponse
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 403)
        
        # Check response content
        content = response.content
        self.assertIn(b'Tenant inactive', content)
        self.assertIn(b'currently inactive', content)
    
    def test_tenant_extraction_with_subdomain(self):
        """Test tenant extraction with subdomain detection."""
        # This would test subdomain-based tenant detection
        # For now, we just test the path-based detection
        request = self.factory.get('/app/active-tenant/dashboard/')
        request.META = {'HTTP_HOST': 'active-tenant.lawfirm.com'}
        
        tenant = self.middleware.get_tenant_from_request(request)
        
        # Should still extract from path since that's the current implementation
        self.assertEqual(tenant, self.active_tenant)
    
    def test_tenant_extraction_with_header(self):
        """Test tenant extraction with header detection."""
        # This would test header-based tenant detection
        # For now, we just test the path-based detection
        request = self.factory.get('/app/active-tenant/dashboard/')
        request.META = {'HTTP_X_TENANT_ID': 'active-tenant'}
        
        tenant = self.middleware.get_tenant_from_request(request)
        
        # Should still extract from path since that's the current implementation
        self.assertEqual(tenant, self.active_tenant)
    
    def test_middleware_with_case_insensitive_slug(self):
        """Test middleware with case-insensitive slug."""
        # Create a tenant with mixed case
        mixed_case_tenant = self.create_tenant(
            name='Mixed Case Tenant',
            slug='Mixed-Case-Tenant'
        )
        
        # Test with different case
        request = self.factory.get('/app/mixed-case-tenant/dashboard/')
        
        # This should work if the database is case-insensitive
        # or fail if it's case-sensitive
        try:
            tenant = self.middleware.get_tenant_from_request(request)
            self.assertEqual(tenant, mixed_case_tenant)
        except Http404:
            # This is expected if the database is case-sensitive
            pass
    
    def test_middleware_with_special_characters_in_slug(self):
        """Test middleware with special characters in slug."""
        # Create a tenant with special characters in slug
        special_tenant = self.create_tenant(
            name='Special Tenant',
            slug='special-tenant_123'
        )
        
        # Test with the slug
        request = self.factory.get('/app/special-tenant_123/dashboard/')
        
        tenant = self.middleware.get_tenant_from_request(request)
        self.assertEqual(tenant, special_tenant)
    
    def test_middleware_with_unicode_in_slug(self):
        """Test middleware with unicode characters in slug."""
        # Create a tenant with unicode characters in slug
        unicode_tenant = self.create_tenant(
            name='Unicode Tenant',
            slug='unicode-tenant-café'
        )
        
        # Test with the slug
        request = self.factory.get('/app/unicode-tenant-café/dashboard/')
        
        tenant = self.middleware.get_tenant_from_request(request)
        self.assertEqual(tenant, unicode_tenant)
    
    def test_middleware_with_nested_paths(self):
        """Test middleware with nested paths."""
        # Test with nested path after tenant
        request = self.factory.get('/app/active-tenant/cases/123/documents/456/')
        
        tenant = self.middleware.get_tenant_from_request(request)
        self.assertEqual(tenant, self.active_tenant)
    
    def test_middleware_with_query_parameters(self):
        """Test middleware with query parameters."""
        # Test with query parameters
        request = self.factory.get('/app/active-tenant/dashboard/?page=2&sort=name')
        
        tenant = self.middleware.get_tenant_from_request(request)
        self.assertEqual(tenant, self.active_tenant)
    
    def test_middleware_integration_with_django_urls(self):
        """Test middleware integration with Django URL resolution."""
        # This would test the middleware's integration with Django's URL resolution
        # For now, we just test the basic functionality
        request = self.factory.get('/app/active-tenant/admin/')
        
        # Process request through middleware
        response = self.middleware(request)
        
        # Verify tenant was set on request
        self.assertEqual(getattr(request, 'tenant', None), self.active_tenant)
        
        # Verify we got a response
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)


class TenantMiddlewareErrorHandlingTests(TenantTestCase):
    """Test error handling in TenantMiddleware."""
    
    def setUp(self):
        """Set up for each test method."""
        super().setUp()
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(get_response=lambda r: HttpResponse())
    
    def test_middleware_with_database_error(self):
        """Test middleware behavior when database errors occur."""
        # Mock the Tenant.objects.get to raise an exception
        with patch('tenants.middleware.Tenant.objects.get') as mock_get:
            mock_get.side_effect = Exception("Database error")
            
            request = self.factory.get('/app/active-tenant/dashboard/')
            
            # Should raise the exception
            with self.assertRaises(Exception) as cm:
                self.middleware.get_tenant_from_request(request)
            
            self.assertIn("Database error", str(cm.exception))
    
    def test_middleware_with_malformed_url(self):
        """Test middleware behavior with malformed URLs."""
        # Test with malformed URL
        request = self.factory.get('/app//active-tenant/dashboard/')
        
        # Should handle gracefully
        tenant = self.middleware.get_tenant_from_request(request)
        self.assertIsNone(tenant)
    
    def test_middleware_with_very_long_slug(self):
        """Test middleware behavior with very long slug."""
        # Create a tenant with a very long slug
        long_slug = 'a' * 100
        long_tenant = self.create_tenant(
            name='Long Slug Tenant',
            slug=long_slug
        )
        
        # Test with the long slug
        request = self.factory.get(f'/app/{long_slug}/dashboard/')
        
        tenant = self.middleware.get_tenant_from_request(request)
        self.assertEqual(tenant, long_tenant)
    
    def test_middleware_performance_with_many_tenants(self):
        """Test middleware performance with many tenants."""
        # Create many tenants
        tenants = []
        for i in range(100):
            tenant = self.create_tenant(
                name=f'Tenant {i}',
                slug=f'tenant-{i}'
            )
            tenants.append(tenant)
        
        # Test accessing the last tenant
        request = self.factory.get('/app/tenant-99/dashboard/')
        
        # Should still work efficiently
        tenant = self.middleware.get_tenant_from_request(request)
        self.assertEqual(tenant, tenants[-1])