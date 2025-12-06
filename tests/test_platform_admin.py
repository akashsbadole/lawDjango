import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory, TransactionTestCase
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.utils import timezone
try:
    from rest_framework.test import APITestCase
    HAS_REST_FRAMEWORK = True
except ImportError:
    # Fallback for when Django REST framework is not available
    from django.test import TestCase as APITestCase
    HAS_REST_FRAMEWORK = False

from tenants.models import Tenant, TenantSettings
from accounts.models import CustomUser
from subscriptions.models import TenantSubscription, SubscriptionPlan, Invoice, Payment
from clients.models import Client
from cases.models import Case
from documents.models import Document
from billing.models import Invoice as BillingInvoice
from platform_admin.models import (
    SystemSettings, PlatformMetrics, AdminNote, SystemAnnouncement,
    SystemHealthCheck, AdminActivityLog
)
from platform_admin.views import (
    SuperAdminDashboardView, TenantListView, TenantDetailView, TenantEditView,
    UserListView, SystemSettingsView, AdminNoteListView, AdminNoteCreateView,
    SystemAnnouncementListView, SystemAnnouncementCreateView, SystemHealthView,
    RevenueReportView, ActivityLogView, bulk_tenant_action, export_data,
    api_system_status, api_tenant_metrics
)
from platform_admin.middleware import (
    SuperAdminAccessMiddleware, SuperAdminActivityMiddleware,
    SuperAdminSecurityHeadersMiddleware
)

User = get_user_model()


class SystemSettingsModelTest(TestCase):
    """Test cases for SystemSettings model."""
    
    def setUp(self):
        self.settings = SystemSettings.objects.create(
            platform_name="Test Platform",
            platform_version="1.0.0",
            support_email="support@test.com",
            allow_public_registration=True,
            require_admin_approval=False,
            default_trial_days=14,
            max_tenants=100,
            max_users_per_tenant=50,
            enforce_2fa_for_admins=False,
            session_timeout_minutes=60,
            auto_backup_enabled=True,
            backup_retention_days=30,
            system_alerts_enabled=True,
            email_notifications_enabled=True,
            maintenance_mode=False
        )
    
    def test_system_settings_creation(self):
        """Test creating system settings."""
        self.assertEqual(self.settings.platform_name, "Test Platform")
        self.assertEqual(self.settings.platform_version, "1.0.0")
        self.assertEqual(self.settings.support_email, "support@test.com")
        self.assertTrue(self.settings.allow_public_registration)
        self.assertFalse(self.settings.require_admin_approval)
        self.assertEqual(self.settings.default_trial_days, 14)
        self.assertEqual(self.settings.max_tenants, 100)
        self.assertEqual(self.settings.max_users_per_tenant, 50)
        self.assertFalse(self.settings.enforce_2fa_for_admins)
        self.assertEqual(self.settings.session_timeout_minutes, 60)
        self.assertTrue(self.settings.auto_backup_enabled)
        self.assertEqual(self.settings.backup_retention_days, 30)
        self.assertTrue(self.settings.system_alerts_enabled)
        self.assertTrue(self.settings.email_notifications_enabled)
        self.assertFalse(self.settings.maintenance_mode)
    
    def test_system_settings_str_representation(self):
        """Test string representation of system settings."""
        self.assertEqual(str(self.settings), "System Settings - Test Platform")
    
    def test_system_settings_get_settings(self):
        """Test get_settings class method."""
        # Test getting existing settings
        settings = SystemSettings.get_settings()
        self.assertEqual(settings.id, self.settings.id)
        
        # Test creating new settings if none exist
        SystemSettings.objects.all().delete()
        settings = SystemSettings.get_settings()
        self.assertIsNotNone(settings.id)
        self.assertEqual(settings.platform_name, "Law Firm Management Platform")


class PlatformMetricsModelTest(TestCase):
    """Test cases for PlatformMetrics model."""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10
        )
        self.metrics = PlatformMetrics.objects.create(
            metric_type="daily",
            date=timezone.now().date(),
            total_tenants=10,
            active_tenants=8,
            new_tenants=2,
            churned_tenants=1,
            total_users=100,
            active_users=80,
            new_users=15,
            total_subscriptions=10,
            active_subscriptions=8,
            trial_subscriptions=2,
            expired_subscriptions=1,
            total_revenue=1000.00,
            monthly_recurring_revenue=800.00,
            average_revenue_per_tenant=100.00,
            total_storage_used_mb=5000.00,
            average_storage_per_tenant_mb=500.00,
            average_response_time_ms=250.50,
            uptime_percentage=99.95,
            error_rate_percentage=0.05,
            documents_created=50,
            cases_created=25,
            clients_created=15,
            invoices_generated=20
        )
    
    def test_platform_metrics_creation(self):
        """Test creating platform metrics."""
        self.assertEqual(self.metrics.metric_type, "daily")
        self.assertEqual(self.metrics.total_tenants, 10)
        self.assertEqual(self.metrics.active_tenants, 8)
        self.assertEqual(self.metrics.new_tenants, 2)
        self.assertEqual(self.metrics.churned_tenants, 1)
        self.assertEqual(self.metrics.total_users, 100)
        self.assertEqual(self.metrics.active_users, 80)
        self.assertEqual(self.metrics.new_users, 15)
        self.assertEqual(self.metrics.total_subscriptions, 10)
        self.assertEqual(self.metrics.active_subscriptions, 8)
        self.assertEqual(self.metrics.trial_subscriptions, 2)
        self.assertEqual(self.metrics.expired_subscriptions, 1)
        self.assertEqual(float(self.metrics.total_revenue), 1000.00)
        self.assertEqual(float(self.metrics.monthly_recurring_revenue), 800.00)
        self.assertEqual(float(self.metrics.average_revenue_per_tenant), 100.00)
        self.assertEqual(float(self.metrics.total_storage_used_mb), 5000.00)
        self.assertEqual(float(self.metrics.average_storage_per_tenant_mb), 500.00)
        self.assertEqual(float(self.metrics.average_response_time_ms), 250.50)
        self.assertEqual(float(self.metrics.uptime_percentage), 99.95)
        self.assertEqual(float(self.metrics.error_rate_percentage), 0.05)
        self.assertEqual(self.metrics.documents_created, 50)
        self.assertEqual(self.metrics.cases_created, 25)
        self.assertEqual(self.metrics.clients_created, 15)
        self.assertEqual(self.metrics.invoices_generated, 20)
    
    def test_platform_metrics_str_representation(self):
        """Test string representation of platform metrics."""
        expected = f"{self.metrics.get_metric_type_display()} Metrics - {self.metrics.date}"
        self.assertEqual(str(self.metrics), expected)
    
    def test_platform_metrics_unique_constraint(self):
        """Test unique constraint on metric_type and date."""
        # Try to create duplicate metrics
        with self.assertRaises(Exception):
            PlatformMetrics.objects.create(
                metric_type="daily",
                date=self.metrics.date,
                total_tenants=5
            )


class AdminNoteModelTest(TestCase):
    """Test cases for AdminNote model."""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10
        )
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass",
            is_superuser=True
        )
        self.target_user = User.objects.create_user(
            username="target",
            email="target@example.com",
            password="targetpass",
            tenant=self.tenant
        )
        self.note = AdminNote.objects.create(
            tenant=self.tenant,
            admin_user=self.admin_user,
            note_type="general",
            title="Test Note",
            content="This is a test note",
            is_private=False,
            is_resolved=False,
            requires_follow_up=True,
            follow_up_date=timezone.now() + timedelta(days=1),
            related_user=self.target_user
        )
    
    def test_admin_note_creation(self):
        """Test creating an admin note."""
        self.assertEqual(self.note.tenant, self.tenant)
        self.assertEqual(self.note.admin_user, self.admin_user)
        self.assertEqual(self.note.note_type, "general")
        self.assertEqual(self.note.title, "Test Note")
        self.assertEqual(self.note.content, "This is a test note")
        self.assertFalse(self.note.is_private)
        self.assertFalse(self.note.is_resolved)
        self.assertTrue(self.note.requires_follow_up)
        self.assertIsNotNone(self.note.follow_up_date)
        self.assertEqual(self.note.related_user, self.target_user)
    
    def test_admin_note_str_representation(self):
        """Test string representation of admin note."""
        expected = "General Note: Test Note - Test Tenant"
        self.assertEqual(str(self.note), expected)
    
    def test_admin_note_is_overdue_property(self):
        """Test is_overdue property."""
        # Test with future follow-up date
        self.assertFalse(self.note.is_overdue)
        
        # Test with past follow-up date
        self.note.follow_up_date = timezone.now() - timedelta(days=1)
        self.note.save()
        self.assertTrue(self.note.is_overdue)
        
        # Test with resolved note
        self.note.is_resolved = True
        self.note.save()
        self.assertFalse(self.note.is_overdue)
        
        # Test with no follow-up required
        self.note.is_resolved = False
        self.note.requires_follow_up = False
        self.note.follow_up_date = timezone.now() - timedelta(days=1)
        self.note.save()
        self.assertFalse(self.note.is_overdue)


class SystemAnnouncementModelTest(TestCase):
    """Test cases for SystemAnnouncement model."""
    
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass",
            is_superuser=True
        )
        self.tenant1 = Tenant.objects.create(
            name="Tenant 1",
            slug="tenant-1",
            plan="basic",
            max_users=10
        )
        self.tenant2 = Tenant.objects.create(
            name="Tenant 2",
            slug="tenant-2",
            plan="basic",
            max_users=10
        )
        self.announcement = SystemAnnouncement.objects.create(
            title="Test Announcement",
            content="This is a test announcement",
            announcement_type="info",
            target_all_tenants=False,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=7),
            show_on_login=True,
            show_on_dashboard=True,
            show_as_banner=False,
            is_dismissible=True,
            priority=50,
            created_by=self.admin_user
        )
        self.announcement.target_tenants.add(self.tenant1)
    
    def test_system_announcement_creation(self):
        """Test creating a system announcement."""
        self.assertEqual(self.announcement.title, "Test Announcement")
        self.assertEqual(self.announcement.content, "This is a test announcement")
        self.assertEqual(self.announcement.announcement_type, "info")
        self.assertFalse(self.announcement.target_all_tenants)
        self.assertTrue(self.announcement.show_on_login)
        self.assertTrue(self.announcement.show_on_dashboard)
        self.assertFalse(self.announcement.show_as_banner)
        self.assertTrue(self.announcement.is_dismissible)
        self.assertEqual(self.announcement.priority, 50)
        self.assertEqual(self.announcement.created_by, self.admin_user)
    
    def test_system_announcement_str_representation(self):
        """Test string representation of system announcement."""
        expected = "Information: Test Announcement"
        self.assertEqual(str(self.announcement), expected)
    
    def test_system_announcement_is_current_property(self):
        """Test is_current property."""
        # Test with active announcement
        self.assertTrue(self.announcement.is_current)
        
        # Test with inactive announcement
        self.announcement.is_active = False
        self.announcement.save()
        self.assertFalse(self.announcement.is_current)
        
        # Test with future start date
        self.announcement.is_active = True
        self.announcement.start_date = timezone.now() + timedelta(days=1)
        self.announcement.save()
        self.assertFalse(self.announcement.is_current)
        
        # Test with past end date
        self.announcement.start_date = timezone.now() - timedelta(days=1)
        self.announcement.end_date = timezone.now() - timedelta(days=1)
        self.announcement.save()
        self.assertFalse(self.announcement.is_current)


class SystemHealthCheckModelTest(TestCase):
    """Test cases for SystemHealthCheck model."""
    
    def setUp(self):
        self.health_check = SystemHealthCheck.objects.create(
            check_type="database",
            status="healthy",
            message="Database is running normally",
            details={"connection_time": "5ms", "query_time": "10ms"},
            check_duration_ms=15,
            next_check_due=timezone.now() + timedelta(minutes=5)
        )
    
    def test_system_health_check_creation(self):
        """Test creating a system health check."""
        self.assertEqual(self.health_check.check_type, "database")
        self.assertEqual(self.health_check.status, "healthy")
        self.assertEqual(self.health_check.message, "Database is running normally")
        self.assertEqual(self.health_check.details["connection_time"], "5ms")
        self.assertEqual(self.health_check.check_duration_ms, 15)
        self.assertIsNotNone(self.health_check.next_check_due)
    
    def test_system_health_check_str_representation(self):
        """Test string representation of system health check."""
        expected = "Database: Healthy"
        self.assertEqual(str(self.health_check), expected)


class AdminActivityLogModelTest(TestCase):
    """Test cases for AdminActivityLog model."""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10
        )
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass",
            is_superuser=True
        )
        self.target_user = User.objects.create_user(
            username="target",
            email="target@example.com",
            password="targetpass",
            tenant=self.tenant
        )
        self.activity_log = AdminActivityLog.objects.create(
            admin_user=self.admin_user,
            action_type="create",
            action_description="Created new tenant",
            tenant=self.tenant,
            target_user=self.target_user,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
            details={"view_name": "TenantCreateView", "path": "/platform-admin/tenants/"}
        )
    
    def test_admin_activity_log_creation(self):
        """Test creating an admin activity log."""
        self.assertEqual(self.activity_log.admin_user, self.admin_user)
        self.assertEqual(self.activity_log.action_type, "create")
        self.assertEqual(self.activity_log.action_description, "Created new tenant")
        self.assertEqual(self.activity_log.tenant, self.tenant)
        self.assertEqual(self.activity_log.target_user, self.target_user)
        self.assertEqual(self.activity_log.ip_address, "192.168.1.1")
        self.assertEqual(self.activity_log.user_agent, "Mozilla/5.0")
        self.assertEqual(self.activity_log.details["view_name"], "TenantCreateView")
    
    def test_admin_activity_log_str_representation(self):
        """Test string representation of admin activity log."""
        expected = f"{self.admin_user.email} - Create: Created new tenant"
        self.assertEqual(str(self.activity_log), expected)


class SuperAdminAccessMiddlewareTest(TestCase):
    """Test cases for SuperAdminAccessMiddleware."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SuperAdminAccessMiddleware(get_response=lambda r: HttpResponse())
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
        self.regular_user = User.objects.create_user(
            username="regular",
            email="regular@example.com",
            password="regularpass"
        )
    
    def test_middleware_allows_superuser(self):
        """Test middleware allows superuser access."""
        request = self.factory.get('/platform-admin/')
        request.user = self.superuser
        
        response = self.middleware.process_request(request)
        self.assertIsNone(response)
    
    def test_middleware_blocks_unauthenticated_user(self):
        """Test middleware blocks unauthenticated user."""
        request = self.factory.get('/platform-admin/')
        request.user = Mock()
        request.user.is_authenticated = False
        
        with patch('platform_admin.middleware.redirect') as mock_redirect:
            self.middleware.process_request(request)
            mock_redirect.assert_called_once()
    
    def test_middleware_blocks_regular_user(self):
        """Test middleware blocks regular user."""
        request = self.factory.get('/platform-admin/')
        request.user = self.regular_user
        
        with patch('platform_admin.middleware.redirect') as mock_redirect:
            self.middleware.process_request(request)
            mock_redirect.assert_called_once()
    
    def test_middleware_ignores_non_admin_urls(self):
        """Test middleware ignores non-admin URLs."""
        request = self.factory.get('/regular-page/')
        request.user = self.regular_user
        
        response = self.middleware.process_request(request)
        self.assertIsNone(response)


class SuperAdminActivityMiddlewareTest(TestCase):
    """Test cases for SuperAdminActivityMiddleware."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SuperAdminActivityMiddleware(get_response=lambda r: HttpResponse())
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10
        )
    
    def test_middleware_logs_superuser_activity(self):
        """Test middleware logs superuser activity."""
        request = self.factory.post('/platform-admin/tenants/')
        request.user = self.superuser
        request.META = {'HTTP_USER_AGENT': 'Test Browser'}
        
        view_func = Mock()
        view_func.__name__ = 'TenantCreateView'
        
        # Process view
        self.middleware.process_view(request, view_func, [], {})
        
        # Check that activity info was added to request
        self.assertTrue(hasattr(request, 'admin_activity'))
        self.assertEqual(request.admin_activity['action_type'], 'create')
        self.assertEqual(request.admin_activity['view_name'], 'TenantCreateView')
    
    def test_middleware_ignores_regular_user(self):
        """Test middleware ignores regular user."""
        request = self.factory.get('/platform-admin/')
        request.user = User.objects.create_user(
            username="regular",
            email="regular@example.com",
            password="regularpass"
        )
        
        view_func = Mock()
        view_func.__name__ = 'DashboardView'
        
        # Process view
        response = self.middleware.process_view(request, view_func, [], {})
        
        # Check that no activity info was added
        self.assertFalse(hasattr(request, 'admin_activity'))
    
    def test_middleware_ignores_non_admin_urls(self):
        """Test middleware ignores non-admin URLs."""
        request = self.factory.get('/regular-page/')
        request.user = self.superuser
        
        view_func = Mock()
        view_func.__name__ = 'RegularView'
        
        # Process view
        response = self.middleware.process_view(request, view_func, [], {})
        
        # Check that no activity info was added
        self.assertFalse(hasattr(request, 'admin_activity'))
    
    def test_middleware_creates_activity_log(self):
        """Test middleware creates activity log on response."""
        request = self.factory.post('/platform-admin/tenants/1/')
        request.user = self.superuser
        request.META = {'HTTP_USER_AGENT': 'Test Browser', 'REMOTE_ADDR': '127.0.0.1'}
        
        # Add activity info to request
        request.admin_activity = {
            'action_type': 'update',
            'view_name': 'TenantUpdateView',
            'path': '/platform-admin/tenants/1/',
            'method': 'POST'
        }
        
        response = HttpResponse(status=200)
        
        # Process response
        with patch('platform_admin.middleware.AdminActivityLog.objects.create') as mock_create:
            self.middleware.process_response(request, response)
            mock_create.assert_called_once()
    
    def test_middleware_gets_action_type(self):
        """Test action type determination."""
        # Test GET request
        request = self.factory.get('/platform-admin/tenants/')
        request.method = 'GET'
        
        view_func = Mock()
        view_func.__name__ = 'TenantListView'
        
        action_type = self.middleware._get_action_type(request, view_func)
        self.assertEqual(action_type, 'view')
        
        # Test POST request
        request.method = 'POST'
        view_func.__name__ = 'TenantCreateView'
        
        action_type = self.middleware._get_action_type(request, view_func)
        self.assertEqual(action_type, 'create')
        
        # Test DELETE request
        request.method = 'DELETE'
        view_func.__name__ = 'TenantDeleteView'
        
        action_type = self.middleware._get_action_type(request, view_func)
        self.assertEqual(action_type, 'delete')
    
    def test_middleware_gets_action_description(self):
        """Test action description generation."""
        activity = {
            'action_type': 'view',
            'path': '/platform-admin/tenants/',
            'view_name': 'TenantListView'
        }
        
        request = self.factory.get('/platform-admin/tenants/')
        
        description = self.middleware._get_action_description(request, activity)
        self.assertEqual(description, 'Viewed Tenant list')
        
        # Test create action
        activity['action_type'] = 'create'
        activity['path'] = '/platform-admin/tenants/new/'
        activity['view_name'] = 'TenantCreateView'
        
        description = self.middleware._get_action_description(request, activity)
        self.assertEqual(description, 'Created Tenant')
    
    def test_middleware_gets_client_ip(self):
        """Test client IP extraction."""
        # Test with X-Forwarded-For header
        request = self.factory.get('/platform-admin/')
        request.META = {'HTTP_X_FORWARDED_FOR': '192.168.1.1, 10.0.0.1'}
        
        ip = self.middleware._get_client_ip(request)
        self.assertEqual(ip, '192.168.1.1')
        
        # Test with REMOTE_ADDR
        request.META = {'REMOTE_ADDR': '192.168.1.2'}
        
        ip = self.middleware._get_client_ip(request)
        self.assertEqual(ip, '192.168.1.2')


class SuperAdminSecurityHeadersMiddlewareTest(TestCase):
    """Test cases for SuperAdminSecurityHeadersMiddleware."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SuperAdminSecurityHeadersMiddleware(get_response=lambda r: HttpResponse())
    
    def test_middleware_adds_security_headers(self):
        """Test middleware adds security headers to admin responses."""
        request = self.factory.get('/platform-admin/')
        response = HttpResponse()
        
        # Process response
        response = self.middleware.process_response(request, response)
        
        # Check security headers
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['X-XSS-Protection'], '1; mode=block')
        self.assertEqual(response['Referrer-Policy'], 'strict-origin-when-cross-origin')
    
    def test_middleware_adds_cache_headers_to_sensitive_pages(self):
        """Test middleware adds cache headers to sensitive pages."""
        request = self.factory.get('/platform-admin/login/')
        response = HttpResponse()
        
        # Process response
        response = self.middleware.process_response(request, response)
        
        # Check cache headers
        self.assertEqual(response['Cache-Control'], 'no-store, no-cache, must-revalidate, max-age=0')
        self.assertEqual(response['Pragma'], 'no-cache')
        self.assertEqual(response['Expires'], '0')
    
    def test_middleware_ignores_non_admin_urls(self):
        """Test middleware ignores non-admin URLs."""
        request = self.factory.get('/regular-page/')
        response = HttpResponse()
        
        # Process response
        response = self.middleware.process_response(request, response)
        
        # Check that no security headers were added
        self.assertNotIn('X-Frame-Options', response)
        self.assertNotIn('X-Content-Type-Options', response)


class SuperAdminDashboardViewTest(TestCase):
    """Test cases for SuperAdminDashboardView."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass",
            tenant=self.tenant
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            code="basic",
            price=10.00,
            max_users=10
        )
        self.subscription = TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status="active"
        )
        self.payment = Payment.objects.create(
            invoice=self.subscription.invoices.first(),
            amount=10.00,
            status="completed",
            payment_date=timezone.now()
        )
        self.metrics = PlatformMetrics.objects.create(
            metric_type="daily",
            date=timezone.now().date(),
            total_tenants=1,
            active_tenants=1,
            total_users=1,
            active_users=1
        )
        self.system_settings = SystemSettings.objects.create(
            platform_name="Test Platform"
        )
        self.health_check = SystemHealthCheck.objects.create(
            check_type="database",
            status="healthy"
        )
        self.note = AdminNote.objects.create(
            admin_user=self.superuser,
            note_type="general",
            title="Test Note",
            content="Test content",
            requires_follow_up=True,
            is_resolved=False
        )
        self.announcement = SystemAnnouncement.objects.create(
            title="Test Announcement",
            content="Test content",
            announcement_type="info",
            is_active=True,
            start_date=timezone.now(),
            created_by=self.superuser
        )
    
    def test_dashboard_view_queryset(self):
        """Test dashboard view queryset."""
        view = SuperAdminDashboardView()
        
        request = self.factory.get('/platform-admin/')
        request.user = self.superuser
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().metric_type, "daily")
    
    def test_dashboard_view_context_data(self):
        """Test dashboard view context data."""
        view = SuperAdminDashboardView()
        
        request = self.factory.get('/platform-admin/')
        request.user = self.superuser
        view.request = request
        
        context = view.get_context_data()
        
        # Check system settings
        self.assertEqual(context['system_settings'].platform_name, "Test Platform")
        
        # Check tenant statistics
        self.assertEqual(context['total_tenants'], 1)
        self.assertEqual(context['active_tenants'], 1)
        self.assertEqual(context['new_tenants_month'], 1)
        
        # Check user statistics
        self.assertEqual(context['total_users'], 2)  # superuser + regular user
        self.assertEqual(context['active_users'], 2)
        self.assertEqual(context['new_users_month'], 2)
        
        # Check subscription statistics
        self.assertEqual(context['total_subscriptions'], 1)
        self.assertEqual(context['active_subscriptions'], 1)
        self.assertEqual(context['trial_subscriptions'], 0)
        
        # Check revenue statistics
        self.assertEqual(float(context['monthly_revenue']), 10.00)
        
        # Check recent activity
        self.assertEqual(len(context['recent_activity']), 1)
        
        # Check system health
        self.assertEqual(len(context['health_checks']), 1)
        
        # Check pending notes
        self.assertEqual(context['pending_notes'], 1)
        
        # Check active announcements
        self.assertEqual(context['active_announcements'], 1)


class TenantListViewTest(TestCase):
    """Test cases for TenantListView."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
        self.tenant1 = Tenant.objects.create(
            name="Tenant 1",
            slug="tenant-1",
            plan="basic",
            max_users=10
        )
        self.tenant2 = Tenant.objects.create(
            name="Tenant 2",
            slug="tenant-2",
            plan="premium",
            max_users=50
        )
        self.user1 = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            password="user1pass",
            tenant=self.tenant1
        )
        self.user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="user2pass",
            tenant=self.tenant2
        )
    
    def test_tenant_list_view_queryset(self):
        """Test tenant list view queryset."""
        view = TenantListView()
        
        request = self.factory.get('/platform-admin/tenants/')
        request.user = self.superuser
        request.GET = {}
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 2)
    
    def test_tenant_list_view_search(self):
        """Test tenant list view search functionality."""
        view = TenantListView()
        
        request = self.factory.get('/platform-admin/tenants/?search=Tenant 1')
        request.user = self.superuser
        request.GET = {'search': 'Tenant 1'}
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().name, "Tenant 1")
    
    def test_tenant_list_view_filter_by_status(self):
        """Test tenant list view status filtering."""
        view = TenantListView()
        
        # Deactivate one tenant
        self.tenant2.is_active = False
        self.tenant2.save()
        
        request = self.factory.get('/platform-admin/tenants/?status=active')
        request.user = self.superuser
        request.GET = {'status': 'active'}
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().name, "Tenant 1")
    
    def test_tenant_list_view_filter_by_plan(self):
        """Test tenant list view plan filtering."""
        view = TenantListView()
        
        request = self.factory.get('/platform-admin/tenants/?plan=basic')
        request.user = self.superuser
        request.GET = {'plan': 'basic'}
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().name, "Tenant 1")
    
    def test_tenant_list_view_context_data(self):
        """Test tenant list view context data."""
        view = TenantListView()
        
        request = self.factory.get('/platform-admin/tenants/')
        request.user = self.superuser
        request.GET = {}
        view.request = request
        
        context = view.get_context_data()
        
        self.assertEqual(context['search_query'], '')
        self.assertEqual(context['status_filter'], '')
        self.assertEqual(context['plan_filter'], '')
        self.assertEqual(context['order_by'], '-created_at')
        self.assertIn('plan_choices', context)


class TenantDetailViewTest(TestCase):
    """Test cases for TenantDetailView."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass",
            tenant=self.tenant
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            code="basic",
            price=10.00,
            max_users=10
        )
        self.subscription = TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status="active"
        )
        self.note = AdminNote.objects.create(
            tenant=self.tenant,
            admin_user=self.superuser,
            note_type="general",
            title="Test Note",
            content="Test content"
        )
    
    def test_tenant_detail_view_object(self):
        """Test tenant detail view object retrieval."""
        view = TenantDetailView()
        
        request = self.factory.get(f'/platform-admin/tenants/{self.tenant.id}/')
        request.user = self.superuser
        view.request = request
        view.kwargs = {'pk': self.tenant.id}
        
        obj = view.get_object()
        self.assertEqual(obj.id, self.tenant.id)
    
    def test_tenant_detail_view_context_data(self):
        """Test tenant detail view context data."""
        view = TenantDetailView()
        
        request = self.factory.get(f'/platform-admin/tenants/{self.tenant.id}/')
        request.user = self.superuser
        view.request = request
        view.kwargs = {'pk': self.tenant.id}
        
        context = view.get_context_data()
        
        # Check tenant
        self.assertEqual(context['tenant'].id, self.tenant.id)
        
        # Check tenant settings
        self.assertIn('tenant_settings', context)
        
        # Check subscription
        self.assertEqual(context['subscription'].id, self.subscription.id)
        
        # Check user count
        self.assertEqual(context['user_count'], 1)
        
        # Check recent users
        self.assertEqual(len(context['recent_users']), 1)
        
        # Check admin notes
        self.assertEqual(len(context['admin_notes']), 1)
        
        # Check storage usage
        self.assertIn('storage_used', context)
        self.assertIn('storage_limit', context)


class UserListViewTest(TestCase):
    """Test cases for UserListView."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
        self.tenant1 = Tenant.objects.create(
            name="Tenant 1",
            slug="tenant-1",
            plan="basic",
            max_users=10
        )
        self.tenant2 = Tenant.objects.create(
            name="Tenant 2",
            slug="tenant-2",
            plan="premium",
            max_users=50
        )
        self.user1 = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            password="user1pass",
            first_name="John",
            last_name="Doe",
            tenant=self.tenant1
        )
        self.user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="user2pass",
            first_name="Jane",
            last_name="Smith",
            tenant=self.tenant2
        )
    
    def test_user_list_view_queryset(self):
        """Test user list view queryset."""
        view = UserListView()
        
        request = self.factory.get('/platform-admin/users/')
        request.user = self.superuser
        request.GET = {}
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 3)  # superuser + user1 + user2
    
    def test_user_list_view_search(self):
        """Test user list view search functionality."""
        view = UserListView()
        
        request = self.factory.get('/platform-admin/users/?search=John')
        request.user = self.superuser
        request.GET = {'search': 'John'}
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().first_name, "John")
    
    def test_user_list_view_filter_by_role(self):
        """Test user list view role filtering."""
        view = UserListView()
        
        request = self.factory.get('/platform-admin/users/?role=admin')
        request.user = self.superuser
        request.GET = {'role': 'admin'}
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().role, "admin")
    
    def test_user_list_view_filter_by_tenant(self):
        """Test user list view tenant filtering."""
        view = UserListView()
        
        request = self.factory.get(f'/platform-admin/users/?tenant={self.tenant1.id}')
        request.user = self.superuser
        request.GET = {'tenant': str(self.tenant1.id)}
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().tenant.id, self.tenant1.id)
    
    def test_user_list_view_context_data(self):
        """Test user list view context data."""
        view = UserListView()
        
        request = self.factory.get('/platform-admin/users/')
        request.user = self.superuser
        request.GET = {}
        view.request = request
        
        context = view.get_context_data()
        
        self.assertEqual(context['search_query'], '')
        self.assertEqual(context['role_filter'], '')
        self.assertEqual(context['tenant_filter'], '')
        self.assertEqual(context['status_filter'], '')
        self.assertEqual(context['order_by'], '-date_joined')
        self.assertIn('role_choices', context)
        self.assertIn('tenant_choices', context)


class SystemSettingsViewTest(TestCase):
    """Test cases for SystemSettingsView."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
        self.system_settings = SystemSettings.objects.create(
            platform_name="Test Platform",
            platform_version="1.0.0"
        )
    
    def test_system_settings_view_get_object(self):
        """Test system settings view object retrieval."""
        view = SystemSettingsView()
        
        request = self.factory.get('/platform-admin/settings/')
        request.user = self.superuser
        view.request = request
        
        obj = view.get_object()
        self.assertEqual(obj.id, self.system_settings.id)
    
    def test_system_settings_view_get_success_url(self):
        """Test system settings view success URL."""
        view = SystemSettingsView()
        
        with patch('platform_admin.views.reverse', return_value='/platform-admin/settings/'):
            url = view.get_success_url()
            self.assertEqual(url, '/platform-admin/settings/')


class AdminNoteListViewTest(TestCase):
    """Test cases for AdminNoteListView."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
        self.tenant1 = Tenant.objects.create(
            name="Tenant 1",
            slug="tenant-1",
            plan="basic",
            max_users=10
        )
        self.tenant2 = Tenant.objects.create(
            name="Tenant 2",
            slug="tenant-2",
            plan="premium",
            max_users=50
        )
        self.note1 = AdminNote.objects.create(
            tenant=self.tenant1,
            admin_user=self.superuser,
            note_type="general",
            title="Note 1",
            content="Content 1"
        )
        self.note2 = AdminNote.objects.create(
            tenant=self.tenant2,
            admin_user=self.superuser,
            note_type="warning",
            title="Note 2",
            content="Content 2"
        )
    
    def test_admin_note_list_view_queryset(self):
        """Test admin note list view queryset."""
        view = AdminNoteListView()
        
        request = self.factory.get('/platform-admin/notes/')
        request.user = self.superuser
        request.GET = {}
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 2)
    
    def test_admin_note_list_view_filter_by_tenant(self):
        """Test admin note list view tenant filtering."""
        view = AdminNoteListView()
        
        request = self.factory.get(f'/platform-admin/notes/?tenant={self.tenant1.id}')
        request.user = self.superuser
        request.GET = {'tenant': str(self.tenant1.id)}
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().tenant.id, self.tenant1.id)
    
    def test_admin_note_list_view_filter_by_note_type(self):
        """Test admin note list view note type filtering."""
        view = AdminNoteListView()
        
        request = self.factory.get('/platform-admin/notes/?note_type=warning')
        request.user = self.superuser
        request.GET = {'note_type': 'warning'}
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().note_type, "warning")
    
    def test_admin_note_list_view_filter_by_status(self):
        """Test admin note list view status filtering."""
        view = AdminNoteListView()
        
        # Mark one note as resolved
        self.note2.is_resolved = True
        self.note2.save()
        
        request = self.factory.get('/platform-admin/notes/?status=unresolved')
        request.user = self.superuser
        request.GET = {'status': 'unresolved'}
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().is_resolved, False)
    
    def test_admin_note_list_view_context_data(self):
        """Test admin note list view context data."""
        view = AdminNoteListView()
        
        request = self.factory.get('/platform-admin/notes/')
        request.user = self.superuser
        request.GET = {}
        view.request = request
        
        context = view.get_context_data()
        
        self.assertEqual(context['tenant_filter'], '')
        self.assertEqual(context['note_type_filter'], '')
        self.assertEqual(context['status_filter'], '')
        self.assertIn('note_type_choices', context)
        self.assertIn('tenant_choices', context)


class AdminNoteCreateViewTest(TestCase):
    """Test cases for AdminNoteCreateView."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10
        )
    
    def test_admin_note_create_view_get_form_kwargs(self):
        """Test admin note create view form kwargs."""
        view = AdminNoteCreateView()
        
        request = self.factory.get('/platform-admin/notes/new/')
        request.user = self.superuser
        view.request = request
        
        kwargs = view.get_form_kwargs()
        self.assertEqual(kwargs['user'], self.superuser)
    
    def test_admin_note_create_view_form_valid(self):
        """Test admin note create view form validation."""
        view = AdminNoteCreateView()
        
        request = self.factory.post('/platform-admin/notes/new/')
        request.user = self.superuser
        view.request = request
        
        form = Mock()
        form.instance = Mock()
        
        with patch('platform_admin.views.messages.success') as mock_messages:
            with patch.object(view, 'get_success_url', return_value='/platform-admin/notes/'):
                response = view.form_valid(form)
                
                # Check that admin user was set
                self.assertEqual(form.instance.admin_user, self.superuser)
                
                # Check that success message was added
                mock_messages.assert_called_once()
    
    def test_admin_note_create_view_get_success_url(self):
        """Test admin note create view success URL."""
        view = AdminNoteCreateView()
        
        with patch('platform_admin.views.reverse', return_value='/platform-admin/notes/'):
            url = view.get_success_url()
            self.assertEqual(url, '/platform-admin/notes/')


class SystemAnnouncementListViewTest(TestCase):
    """Test cases for SystemAnnouncementListView."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
        self.announcement1 = SystemAnnouncement.objects.create(
            title="Announcement 1",
            content="Content 1",
            announcement_type="info",
            priority=50,
            created_by=self.superuser
        )
        self.announcement2 = SystemAnnouncement.objects.create(
            title="Announcement 2",
            content="Content 2",
            announcement_type="warning",
            priority=100,
            created_by=self.superuser
        )
    
    def test_system_announcement_list_view_queryset(self):
        """Test system announcement list view queryset."""
        view = SystemAnnouncementListView()
        
        request = self.factory.get('/platform-admin/announcements/')
        request.user = self.superuser
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 2)
        # Check ordering by priority
        self.assertEqual(queryset.first().title, "Announcement 2")  # Higher priority


class SystemAnnouncementCreateViewTest(TestCase):
    """Test cases for SystemAnnouncementCreateView."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
    
    def test_system_announcement_create_view_get_form_kwargs(self):
        """Test system announcement create view form kwargs."""
        view = SystemAnnouncementCreateView()
        
        request = self.factory.get('/platform-admin/announcements/new/')
        request.user = self.superuser
        view.request = request
        
        kwargs = view.get_form_kwargs()
        self.assertEqual(kwargs['user'], self.superuser)
    
    def test_system_announcement_create_view_form_valid(self):
        """Test system announcement create view form validation."""
        view = SystemAnnouncementCreateView()
        
        request = self.factory.post('/platform-admin/announcements/new/')
        request.user = self.superuser
        view.request = request
        
        form = Mock()
        form.instance = Mock()
        
        with patch('platform_admin.views.messages.success') as mock_messages:
            with patch.object(view, 'get_success_url', return_value='/platform-admin/announcements/'):
                response = view.form_valid(form)
                
                # Check that created by was set
                self.assertEqual(form.instance.created_by, self.superuser)
                
                # Check that success message was added
                mock_messages.assert_called_once()
    
    def test_system_announcement_create_view_get_success_url(self):
        """Test system announcement create view success URL."""
        view = SystemAnnouncementCreateView()
        
        with patch('platform_admin.views.reverse', return_value='/platform-admin/announcements/'):
            url = view.get_success_url()
            self.assertEqual(url, '/platform-admin/announcements/')


class SystemHealthViewTest(TestCase):
    """Test cases for SystemHealthView."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
        self.health_check1 = SystemHealthCheck.objects.create(
            check_type="database",
            status="healthy"
        )
        self.health_check2 = SystemHealthCheck.objects.create(
            check_type="storage",
            status="warning"
        )
        self.health_check3 = SystemHealthCheck.objects.create(
            check_type="database",
            status="critical"
        )
    
    def test_system_health_view_queryset(self):
        """Test system health view queryset."""
        view = SystemHealthView()
        
        request = self.factory.get('/platform-admin/health/')
        request.user = self.superuser
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 3)
    
    def test_system_health_view_context_data(self):
        """Test system health view context data."""
        view = SystemHealthView()
        
        request = self.factory.get('/platform-admin/health/')
        request.user = self.superuser
        view.request = request
        
        context = view.get_context_data()
        
        # Check health checks grouped by type
        self.assertIn('health_by_type', context)
        self.assertIn('database', context['health_by_type'])
        self.assertEqual(len(context['health_by_type']['database']), 2)
        self.assertIn('storage', context['health_by_type'])
        self.assertEqual(len(context['health_by_type']['storage']), 1)
        
        # Check latest checks
        self.assertIn('latest_checks', context)
        self.assertIn('database', context['latest_checks'])
        self.assertEqual(context['latest_checks']['database'].status, 'critical')  # Latest database check


class RevenueReportViewTest(TestCase):
    """Test cases for RevenueReportView."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            code="basic",
            price=10.00
        )
        self.subscription = TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status="active"
        )
        self.payment1 = Payment.objects.create(
            invoice=self.subscription.invoices.first(),
            amount=10.00,
            status="completed",
            payment_date=timezone.now() - timedelta(days=5)
        )
        self.payment2 = Payment.objects.create(
            invoice=self.subscription.invoices.first(),
            amount=20.00,
            status="completed",
            payment_date=timezone.now() - timedelta(days=35)
        )
    
    def test_revenue_report_view_queryset(self):
        """Test revenue report view queryset."""
        view = RevenueReportView()
        
        request = self.factory.get('/platform-admin/revenue/')
        request.user = self.superuser
        request.GET = {}
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 2)
    
    def test_revenue_report_view_filter_by_date_range(self):
        """Test revenue report view date range filtering."""
        view = RevenueReportView()
        
        # Filter to last 30 days
        date_from = (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        request = self.factory.get(f'/platform-admin/revenue/?date_from={date_from}')
        request.user = self.superuser
        request.GET = {'date_from': date_from}
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 1)  # Only payment1 is within 30 days
    
    def test_revenue_report_view_context_data(self):
        """Test revenue report view context data."""
        view = RevenueReportView()
        
        request = self.factory.get('/platform-admin/revenue/')
        request.user = self.superuser
        request.GET = {}
        view.request = request
        
        context = view.get_context_data()
        
        # Check total revenue
        self.assertEqual(float(context['total_revenue']), 30.00)
        
        # Check monthly revenue
        self.assertEqual(float(context['monthly_revenue']), 10.00)
        
        # Check revenue by tenant
        self.assertIn('revenue_by_tenant', context)
        self.assertEqual(len(context['revenue_by_tenant']), 1)
        self.assertEqual(float(context['revenue_by_tenant'][0]['total']), 30.00)
        
        # Check revenue by month
        self.assertIn('revenue_by_month', context)


class ActivityLogViewTest(TestCase):
    """Test cases for ActivityLogView."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10
        )
        self.log1 = AdminActivityLog.objects.create(
            admin_user=self.superuser,
            action_type="create",
            action_description="Created tenant",
            tenant=self.tenant
        )
        self.log2 = AdminActivityLog.objects.create(
            admin_user=self.superuser,
            action_type="update",
            action_description="Updated settings"
        )
    
    def test_activity_log_view_queryset(self):
        """Test activity log view queryset."""
        view = ActivityLogView()
        
        request = self.factory.get('/platform-admin/activity/')
        request.user = self.superuser
        request.GET = {}
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 2)
    
    def test_activity_log_view_filter_by_admin(self):
        """Test activity log view admin filtering."""
        view = ActivityLogView()
        
        request = self.factory.get(f'/platform-admin/activity/?admin={self.superuser.id}')
        request.user = self.superuser
        request.GET = {'admin': str(self.superuser.id)}
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 2)
    
    def test_activity_log_view_filter_by_action(self):
        """Test activity log view action filtering."""
        view = ActivityLogView()
        
        request = self.factory.get('/platform-admin/activity/?action=create')
        request.user = self.superuser
        request.GET = {'action': 'create'}
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().action_type, "create")
    
    def test_activity_log_view_filter_by_tenant(self):
        """Test activity log view tenant filtering."""
        view = ActivityLogView()
        
        request = self.factory.get(f'/platform-admin/activity/?tenant={self.tenant.id}')
        request.user = self.superuser
        request.GET = {'tenant': str(self.tenant.id)}
        view.request = request
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().tenant.id, self.tenant.id)
    
    def test_activity_log_view_context_data(self):
        """Test activity log view context data."""
        view = ActivityLogView()
        
        request = self.factory.get('/platform-admin/activity/')
        request.user = self.superuser
        request.GET = {}
        view.request = request
        
        context = view.get_context_data()
        
        self.assertEqual(context['admin_filter'], '')
        self.assertEqual(context['action_filter'], '')
        self.assertEqual(context['tenant_filter'], '')
        self.assertEqual(context['date_from'], '')
        self.assertEqual(context['date_to'], '')
        self.assertIn('action_choices', context)
        self.assertIn('admin_choices', context)
        self.assertIn('tenant_choices', context)


class BulkTenantActionViewTest(TestCase):
    """Test cases for bulk_tenant_action view."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
        self.tenant1 = Tenant.objects.create(
            name="Tenant 1",
            slug="tenant-1",
            plan="basic",
            max_users=10
        )
        self.tenant2 = Tenant.objects.create(
            name="Tenant 2",
            slug="tenant-2",
            plan="premium",
            max_users=50
        )
    
    def test_bulk_tenant_action_enable(self):
        """Test bulk enable tenant action."""
        # Deactivate tenants
        self.tenant1.is_active = False
        self.tenant1.save()
        self.tenant2.is_active = False
        self.tenant2.save()
        
        request = self.factory.post('/platform-admin/tenants/bulk/', {
            'action': 'enable',
            'tenant_ids': [str(self.tenant1.id), str(self.tenant2.id)]
        })
        request.user = self.superuser
        
        with patch('platform_admin.views.messages.success') as mock_messages:
            with patch('platform_admin.views.redirect') as mock_redirect:
                response = bulk_tenant_action(request)
                
                # Check that tenants were enabled
                self.tenant1.refresh_from_db()
                self.tenant2.refresh_from_db()
                self.assertTrue(self.tenant1.is_active)
                self.assertTrue(self.tenant2.is_active)
                
                # Check that success message was added
                mock_messages.assert_called_once()
                
                # Check that redirect was called
                mock_redirect.assert_called_once()
                
                # Check that activity log was created
                log = AdminActivityLog.objects.latest('created_at')
                self.assertEqual(log.action_type, 'bulk_operation')
                self.assertEqual(log.action_description, 'Bulk enabled 2 tenants')
    
    def test_bulk_tenant_action_disable(self):
        """Test bulk disable tenant action."""
        request = self.factory.post('/platform-admin/tenants/bulk/', {
            'action': 'disable',
            'tenant_ids': [str(self.tenant1.id), str(self.tenant2.id)]
        })
        request.user = self.superuser
        
        with patch('platform_admin.views.messages.success') as mock_messages:
            with patch('platform_admin.views.redirect') as mock_redirect:
                response = bulk_tenant_action(request)
                
                # Check that tenants were disabled
                self.tenant1.refresh_from_db()
                self.tenant2.refresh_from_db()
                self.assertFalse(self.tenant1.is_active)
                self.assertFalse(self.tenant2.is_active)
                
                # Check that success message was added
                mock_messages.assert_called_once()
                
                # Check that redirect was called
                mock_redirect.assert_called_once()
                
                # Check that activity log was created
                log = AdminActivityLog.objects.latest('created_at')
                self.assertEqual(log.action_type, 'bulk_operation')
                self.assertEqual(log.action_description, 'Bulk disabled 2 tenants')
    
    def test_bulk_tenant_action_delete(self):
        """Test bulk delete tenant action."""
        request = self.factory.post('/platform-admin/tenants/bulk/', {
            'action': 'delete',
            'tenant_ids': [str(self.tenant1.id)]
        })
        request.user = self.superuser
        
        with patch('platform_admin.views.messages.success') as mock_messages:
            with patch('platform_admin.views.redirect') as mock_redirect:
                response = bulk_tenant_action(request)
                
                # Check that tenant was soft deleted
                self.tenant1.refresh_from_db()
                self.assertTrue(self.tenant1.is_deleted)
                
                # Check that success message was added
                mock_messages.assert_called_once()
                
                # Check that redirect was called
                mock_redirect.assert_called_once()
                
                # Check that activity log was created
                log = AdminActivityLog.objects.latest('created_at')
                self.assertEqual(log.action_type, 'bulk_operation')
                self.assertEqual(log.action_description, 'Bulk deleted 1 tenants')
    
    def test_bulk_tenant_action_no_selection(self):
        """Test bulk tenant action with no selection."""
        request = self.factory.post('/platform-admin/tenants/bulk/', {
            'action': 'enable',
            'tenant_ids': []
        })
        request.user = self.superuser
        
        with patch('platform_admin.views.messages.error') as mock_messages:
            with patch('platform_admin.views.redirect') as mock_redirect:
                response = bulk_tenant_action(request)
                
                # Check that error message was added
                mock_messages.assert_called_once()
                
                # Check that redirect was called
                mock_redirect.assert_called_once()
    
    def test_bulk_tenant_action_no_action(self):
        """Test bulk tenant action with no action."""
        request = self.factory.post('/platform-admin/tenants/bulk/', {
            'tenant_ids': [str(self.tenant1.id)]
        })
        request.user = self.superuser
        
        with patch('platform_admin.views.messages.error') as mock_messages:
            with patch('platform_admin.views.redirect') as mock_redirect:
                response = bulk_tenant_action(request)
                
                # Check that error message was added
                mock_messages.assert_called_once()
                
                # Check that redirect was called
                mock_redirect.assert_called_once()


class ExportDataViewTest(TestCase):
    """Test cases for export_data view."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
        self.tenant1 = Tenant.objects.create(
            name="Tenant 1",
            slug="tenant-1",
            plan="basic",
            max_users=10
        )
        self.tenant2 = Tenant.objects.create(
            name="Tenant 2",
            slug="tenant-2",
            plan="premium",
            max_users=50
        )
        self.user1 = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            password="user1pass",
            first_name="John",
            last_name="Doe",
            tenant=self.tenant1
        )
        self.user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="user2pass",
            first_name="Jane",
            last_name="Smith",
            tenant=self.tenant2
        )
    
    def test_export_data_tenants_csv(self):
        """Test exporting tenants as CSV."""
        request = self.factory.get('/platform-admin/export/?type=tenants&format=csv')
        request.user = self.superuser
        
        response = export_data(request)
        
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="tenants.csv"', response['Content-Disposition'])
    
    def test_export_data_users_csv(self):
        """Test exporting users as CSV."""
        request = self.factory.get('/platform-admin/export/?type=users&format=csv')
        request.user = self.superuser
        
        response = export_data(request)
        
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="users.csv"', response['Content-Disposition'])
    
    def test_export_data_invalid_type(self):
        """Test exporting with invalid type."""
        request = self.factory.get('/platform-admin/export/?type=invalid&format=csv')
        request.user = self.superuser
        
        with patch('platform_admin.views.messages.error') as mock_messages:
            with patch('platform_admin.views.redirect') as mock_redirect:
                response = export_data(request)
                
                # Check that error message was added
                mock_messages.assert_called_once()
                
                # Check that redirect was called
                mock_redirect.assert_called_once()


class APISystemStatusViewTest(TestCase):
    """Test cases for api_system_status view."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass",
            tenant=self.tenant
        )
        self.health_check = SystemHealthCheck.objects.create(
            check_type="database",
            status="healthy"
        )
    
    def test_api_system_status(self):
        """Test API system status endpoint."""
        request = self.factory.get('/platform-admin/api/status/')
        request.user = self.superuser
        
        response = api_system_status(request)
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertIn('timestamp', data)
        self.assertIn('tenants', data)
        self.assertIn('users', data)
        self.assertIn('subscriptions', data)
        self.assertIn('health', data)
        
        # Check tenant stats
        self.assertEqual(data['tenants']['total'], 1)
        self.assertEqual(data['tenants']['active'], 1)
        self.assertEqual(data['tenants']['new_this_month'], 1)
        
        # Check user stats
        self.assertEqual(data['users']['total'], 2)  # superuser + regular user
        self.assertEqual(data['users']['new_this_month'], 2)
        
        # Check health data
        self.assertIn('database', data['health'])
        self.assertEqual(data['health']['database']['status'], 'healthy')
    
    def test_api_system_status_caching(self):
        """Test API system status endpoint caching."""
        request = self.factory.get('/platform-admin/api/status/')
        request.user = self.superuser
        
        # Clear cache
        cache.clear()
        
        # First call should query database
        with patch('platform_admin.views.Tenant.objects.count', return_value=1) as mock_count:
            response1 = api_system_status(request)
            mock_count.assert_called_once()
        
        # Second call should use cache
        with patch('platform_admin.views.Tenant.objects.count') as mock_count:
            response2 = api_system_status(request)
            mock_count.assert_not_called()
        
        # Both responses should be the same
        self.assertEqual(response1.content, response2.content)


class APITenantMetricsViewTest(TestCase):
    """Test cases for api_tenant_metrics view."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass",
            tenant=self.tenant
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            code="basic",
            price=10.00
        )
        self.subscription = TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status="active"
        )
    
    def test_api_tenant_metrics(self):
        """Test API tenant metrics endpoint."""
        request = self.factory.get(f'/platform-admin/api/tenant-metrics/?tenant_id={self.tenant.id}')
        request.user = self.superuser
        
        response = api_tenant_metrics(request)
        
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertIn('tenant', data)
        self.assertIn('users', data)
        self.assertIn('storage', data)
        self.assertIn('subscription', data)
        
        # Check tenant data
        self.assertEqual(data['tenant']['id'], self.tenant.id)
        self.assertEqual(data['tenant']['name'], self.tenant.name)
        self.assertEqual(data['tenant']['plan'], self.tenant.plan)
        
        # Check subscription data
        self.assertIsNotNone(data['subscription'])
        self.assertEqual(data['subscription']['status'], 'active')
        self.assertEqual(data['subscription']['plan'], 'Basic Plan')
    
    def test_api_tenant_metrics_missing_id(self):
        """Test API tenant metrics endpoint with missing tenant ID."""
        request = self.factory.get('/platform-admin/api/tenant-metrics/')
        request.user = self.superuser
        
        response = api_tenant_metrics(request)
        
        self.assertEqual(response.status_code, 400)
        
        data = json.loads(response.content)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Tenant ID required')
    
    def test_api_tenant_metrics_not_found(self):
        """Test API tenant metrics endpoint with non-existent tenant ID."""
        request = self.factory.get('/platform-admin/api/tenant-metrics/?tenant_id=999')
        request.user = self.superuser
        
        response = api_tenant_metrics(request)
        
        self.assertEqual(response.status_code, 404)
        
        data = json.loads(response.content)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Tenant not found')


class SuperAdminIntegrationTest(TransactionTestCase):
    """Integration tests for super admin functionality."""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass",
            is_superuser=True
        )
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass",
            tenant=self.tenant
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            code="basic",
            price=10.00
        )
        self.subscription = TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status="active"
        )
        self.payment = Payment.objects.create(
            invoice=self.subscription.invoices.first(),
            amount=10.00,
            status="completed",
            payment_date=timezone.now()
        )
        self.system_settings = SystemSettings.objects.create(
            platform_name="Test Platform"
        )
        self.health_check = SystemHealthCheck.objects.create(
            check_type="database",
            status="healthy"
        )
        self.note = AdminNote.objects.create(
            tenant=self.tenant,
            admin_user=self.superuser,
            note_type="general",
            title="Test Note",
            content="Test content"
        )
        self.announcement = SystemAnnouncement.objects.create(
            title="Test Announcement",
            content="Test content",
            announcement_type="info",
            is_active=True,
            start_date=timezone.now(),
            created_by=self.superuser
        )
    
    def test_super_admin_workflow(self):
        """Test complete super admin workflow."""
        # 1. View dashboard
        request = self.factory.get('/platform-admin/')
        request.user = self.superuser
        
        view = SuperAdminDashboardView()
        view.request = request
        view.setup(request)
        
        response = view.get(request)
        self.assertEqual(response.status_code, 200)
        
        context = view.get_context_data()
        self.assertEqual(context['total_tenants'], 1)
        self.assertEqual(context['total_users'], 2)
        self.assertEqual(context['total_subscriptions'], 1)
        
        # 2. View tenant list
        request = self.factory.get('/platform-admin/tenants/')
        request.user = self.superuser
        
        view = TenantListView()
        view.request = request
        view.setup(request)
        
        response = view.get(request)
        self.assertEqual(response.status_code, 200)
        
        queryset = view.get_queryset()
        self.assertEqual(queryset.count(), 1)
        
        # 3. View tenant details
        request = self.factory.get(f'/platform-admin/tenants/{self.tenant.id}/')
        request.user = self.superuser
        
        view = TenantDetailView()
        view.request = request
        view.kwargs = {'pk': self.tenant.id}
        view.setup(request)
        
        response = view.get(request)
        self.assertEqual(response.status_code, 200)
        
        context = view.get_context_data()
        self.assertEqual(context['tenant'].id, self.tenant.id)
        
        # 4. Create admin note
        request = self.factory.post('/platform-admin/notes/new/', {
            'tenant': self.tenant.id,
            'note_type': 'general',
            'title': 'Integration Test Note',
            'content': 'This is an integration test note'
        })
        request.user = self.superuser
        request._messages = FallbackStorage(request)
        
        view = AdminNoteCreateView()
        view.request = request
        view.setup(request)
        
        # Mock form validation
        form = Mock()
        form.is_valid.return_value = True
        form.save.return_value = AdminNote(
            tenant=self.tenant,
            admin_user=self.superuser,
            note_type='general',
            title='Integration Test Note',
            content='This is an integration test note'
        )
        
        with patch.object(view, 'get_form', return_value=form):
            response = view.post(request)
            self.assertEqual(response.status_code, 302)  # Redirect on success
        
        # Check that note was created
        notes = AdminNote.objects.filter(title='Integration Test Note')
        self.assertEqual(notes.count(), 1)
        
        # 5. Create system announcement
        request = self.factory.post('/platform-admin/announcements/new/', {
            'title': 'Integration Test Announcement',
            'content': 'This is an integration test announcement',
            'announcement_type': 'info',
            'target_all_tenants': True,
            'is_active': True,
            'show_on_login': True,
            'show_on_dashboard': True
        })
        request.user = self.superuser
        request._messages = FallbackStorage(request)
        
        view = SystemAnnouncementCreateView()
        view.request = request
        view.setup(request)
        
        # Mock form validation
        form = Mock()
        form.is_valid.return_value = True
        form.save.return_value = SystemAnnouncement(
            title='Integration Test Announcement',
            content='This is an integration test announcement',
            announcement_type='info',
            target_all_tenants=True,
            is_active=True,
            show_on_login=True,
            show_on_dashboard=True,
            created_by=self.superuser
        )
        
        with patch.object(view, 'get_form', return_value=form):
            response = view.post(request)
            self.assertEqual(response.status_code, 302)  # Redirect on success
        
        # Check that announcement was created
        announcements = SystemAnnouncement.objects.filter(title='Integration Test Announcement')
        self.assertEqual(announcements.count(), 1)
        
        # 6. Check activity logs
        request = self.factory.get('/platform-admin/activity/')
        request.user = self.superuser
        
        view = ActivityLogView()
        view.request = request
        view.setup(request)
        
        response = view.get(request)
        self.assertEqual(response.status_code, 200)
        
        queryset = view.get_queryset()
        self.assertGreater(queryset.count(), 0)
        
        # 7. Check API status
        request = self.factory.get('/platform-admin/api/status/')
        request.user = self.superuser
        
        response = api_system_status(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertIn('tenants', data)
        self.assertIn('users', data)
        self.assertIn('subscriptions', data)
        
        # 8. Check tenant metrics API
        request = self.factory.get(f'/platform-admin/api/tenant-metrics/?tenant_id={self.tenant.id}')
        request.user = self.superuser
        
        response = api_tenant_metrics(request)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertIn('tenant', data)
        self.assertIn('users', data)
        self.assertIn('storage', data)
        self.assertIn('subscription', data)