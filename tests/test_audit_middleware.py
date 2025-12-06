"""
Tests for audit middleware to ensure it handles requests without user attribute correctly.
"""

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from audit.middleware import AuditMiddleware
from unittest.mock import Mock, MagicMock

User = get_user_model()


class AuditMiddlewareTests(TestCase):
    """Test AuditMiddleware functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.factory = RequestFactory()
        self.get_response = Mock()
        self.get_response.return_value = MagicMock(status_code=200)
        
    def test_middleware_without_user_attribute(self):
        """
        Test that middleware handles requests without user attribute gracefully.
        This simulates the case where authentication middleware hasn't run yet.
        """
        # Create a request without user attribute
        request = self.factory.get('/test/')
        request.session = {}
        request.tenant = Mock()  # Mock tenant to avoid tenant-related errors
        
        # Create middleware instance
        middleware = AuditMiddleware(self.get_response)
        
        # Process the request - should not raise AttributeError
        response = middleware(request)
        
        # Verify response is returned without errors
        self.assertIsNotNone(response)
        self.get_response.assert_called_once_with(request)
        
    def test_middleware_with_authenticated_user(self):
        """
        Test that middleware works correctly with authenticated user.
        """
        # Create a user
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create a request with authenticated user
        request = self.factory.get('/test/')
        request.user = user
        request.user.is_authenticated = True
        request.session = Mock()
        request.session.session_key = 'test_session_key'
        request.tenant = Mock()  # Mock tenant to avoid tenant-related errors
        
        # Create middleware instance
        middleware = AuditMiddleware(self.get_response)
        
        # Process the request - should not raise AttributeError
        response = middleware(request)
        
        # Verify response is returned without errors
        self.assertIsNotNone(response)
        self.get_response.assert_called_once_with(request)
        
    def test_middleware_with_anonymous_user(self):
        """
        Test that middleware works correctly with anonymous user.
        """
        # Create a request with anonymous user
        request = self.factory.get('/test/')
        request.user = Mock()
        request.user.is_authenticated = False
        request.session = Mock()
        request.tenant = Mock()  # Mock tenant to avoid tenant-related errors
        
        # Create middleware instance
        middleware = AuditMiddleware(self.get_response)
        
        # Process the request - should not raise AttributeError
        response = middleware(request)
        
        # Verify response is returned without errors
        self.assertIsNotNone(response)
        self.get_response.assert_called_once_with(request)
        
    def test_middleware_with_user_but_no_is_authenticated(self):
        """
        Test that middleware handles user object without is_authenticated attribute.
        """
        # Create a request with user object but no is_authenticated attribute
        request = self.factory.get('/test/')
        request.user = Mock(spec=[])  # User with no attributes
        request.session = Mock()
        request.tenant = Mock()  # Mock tenant to avoid tenant-related errors
        
        # Create middleware instance
        middleware = AuditMiddleware(self.get_response)
        
        # Process the request - should not raise AttributeError
        response = middleware(request)
        
        # Verify response is returned without errors
        self.assertIsNotNone(response)
        self.get_response.assert_called_once_with(request)