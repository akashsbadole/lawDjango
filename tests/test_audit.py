"""
Tests for audit module in multi-tenant context.
"""

from django.test import TestCase, TransactionTestCase
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal
from django.contrib.auth import get_user_model

from audit.models import AuditLog, LoginLog, ActivityLog, SecurityEvent
from clients.models import Client
from cases.models import Case
from tenants.models import Tenant
from tests.utils import TenantTestCase, MultiTenantTestCase, TenantMixinTestMixin

User = get_user_model()


class AuditLogModelTests(TenantTestCase):
    """Test AuditLog model."""
    
    def test_audit_log_creation(self):
        """Test basic audit log creation."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        # Get content type for the client
        content_type = ContentType.objects.get_for_model(Client)
        
        audit_log = AuditLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            action='create',
            model_name='Client',
            object_id=str(client.pk),
            object_repr=str(client),
            content_type=content_type,
            content_object=client,
            old_values=None,
            new_values={
                'first_name': 'Test',
                'last_name': 'Client',
                'email': 'client@example.com'
            },
            changed_fields=['first_name', 'last_name', 'email'],
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            session_key='test_session_key',
            request_path='/clients/create/',
            request_method='POST',
            additional_data={'source': 'web'}
        )
        
        self.assertEqual(audit_log.tenant, self.active_tenant)
        self.assertEqual(audit_log.user, self.admin_user)
        self.assertEqual(audit_log.action, 'create')
        self.assertEqual(audit_log.model_name, 'Client')
        self.assertEqual(audit_log.object_id, str(client.pk))
        self.assertEqual(audit_log.object_repr, str(client))
        self.assertEqual(audit_log.content_type, content_type)
        self.assertEqual(audit_log.content_object, client)
        # Ensure new_values is not None
        self.assertIsNotNone(audit_log.new_values)
        # Ensure additional_data is not None
        self.assertIsNotNone(audit_log.additional_data)
        self.assertEqual(audit_log.new_values['first_name'], 'Test')
        self.assertEqual(audit_log.changed_fields, ['first_name', 'last_name', 'email'])
        self.assertEqual(audit_log.ip_address, '192.168.1.1')
        self.assertEqual(audit_log.user_agent, 'Mozilla/5.0')
        self.assertEqual(audit_log.session_key, 'test_session_key')
        self.assertEqual(audit_log.request_path, '/clients/create/')
        self.assertEqual(audit_log.request_method, 'POST')
        self.assertEqual(audit_log.additional_data['source'], 'web')
    
    def test_audit_log_str_representation(self):
        """Test audit log string representation."""
        audit_log = AuditLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            action='create',
            model_name='Client',
            object_id='123',
            object_repr='Test Client'
        )
        
        expected = f"{self.admin_user} create Client at {audit_log.timestamp}"
        self.assertEqual(str(audit_log), expected)
    
    def test_audit_log_str_representation_anonymous(self):
        """Test audit log string representation with anonymous user."""
        audit_log = AuditLog.objects.create(
            tenant=self.active_tenant,
            user=None,
            action='view',
            model_name='Client',
            object_id='123',
            object_repr='Test Client'
        )
        
        expected = f"Anonymous view Client at {audit_log.timestamp}"
        self.assertEqual(str(audit_log), expected)
    
    def test_audit_log_changes_summary_property(self):
        """Test changes_summary property."""
        # Create action
        create_log = AuditLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            action='create',
            model_name='Client',
            object_id='123',
            object_repr='Test Client'
        )
        
        self.assertEqual(create_log.changes_summary, "Created new Client: Test Client")
        
        # Delete action
        delete_log = AuditLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            action='delete',
            model_name='Client',
            object_id='123',
            object_repr='Test Client'
        )
        
        self.assertEqual(delete_log.changes_summary, "Deleted Client: Test Client")
        
        # Update action with changed fields
        update_log = AuditLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            action='update',
            model_name='Client',
            object_id='123',
            object_repr='Test Client',
            changed_fields=['first_name', 'email']
        )
        
        self.assertEqual(update_log.changes_summary, "Updated Client: first_name, email")
        
        # Update action without changed fields
        update_log_no_fields = AuditLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            action='update',
            model_name='Client',
            object_id='123',
            object_repr='Test Client'
        )
        
        self.assertEqual(update_log_no_fields.changes_summary, "Update Client")
    
    def test_audit_log_ordering(self):
        """Test audit log ordering by timestamp."""
        # Create logs in random order
        log3 = AuditLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            action='create',
            model_name='Client',
            object_id='3'
        )
        
        log1 = AuditLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            action='create',
            model_name='Client',
            object_id='1'
        )
        
        log2 = AuditLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            action='create',
            model_name='Client',
            object_id='2'
        )
        
        # Verify ordering (newest first)
        logs = list(AuditLog.objects.all())
        self.assertEqual(logs[0], log3)  # Most recent
        self.assertEqual(logs[1], log2)  # Middle
        self.assertEqual(logs[2], log1)  # Oldest


class LoginLogModelTests(TenantTestCase):
    """Test LoginLog model."""
    
    def test_login_log_creation(self):
        """Test basic login log creation."""
        login_log = LoginLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            login_time=timezone.now(),
            logout_time=timezone.now() + timedelta(hours=8),
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            session_key='test_session_key',
            login_successful=True,
            device_info={
                'device_type': 'desktop',
                'os': 'Windows',
                'browser': 'Chrome'
            },
            location_info={
                'country': 'United States',
                'city': 'New York'
            }
        )
        
        self.assertEqual(login_log.tenant, self.active_tenant)
        self.assertEqual(login_log.user, self.admin_user)
        self.assertIsNotNone(login_log.login_time)
        self.assertIsNotNone(login_log.logout_time)
        self.assertEqual(login_log.ip_address, '192.168.1.1')
        self.assertEqual(login_log.user_agent, 'Mozilla/5.0')
        self.assertEqual(login_log.session_key, 'test_session_key')
        # Ensure device_info is not None
        self.assertIsNotNone(login_log.device_info)
        # Ensure location_info is not None
        self.assertIsNotNone(login_log.location_info)
        self.assertTrue(login_log.login_successful)
        self.assertEqual(login_log.device_info['device_type'], 'desktop')
        self.assertEqual(login_log.location_info['country'], 'United States')
    
    def test_login_log_creation_failed_login(self):
        """Test login log creation for failed login."""
        login_log = LoginLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            login_time=timezone.now(),
            login_successful=False,
            failure_reason='Invalid password',
            ip_address='192.168.1.100'
        )
        
        self.assertFalse(login_log.login_successful)
        self.assertEqual(login_log.failure_reason, 'Invalid password')
        self.assertEqual(login_log.ip_address, '192.168.1.100')
        self.assertIsNone(login_log.logout_time)
    
    def test_login_log_str_representation(self):
        """Test login log string representation."""
        # Successful login
        successful_login = LoginLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            login_time=timezone.now(),
            login_successful=True
        )
        
        expected = f"{self.admin_user} - Successful login at {successful_login.login_time}"
        self.assertEqual(str(successful_login), expected)
        
        # Failed login
        failed_login = LoginLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            login_time=timezone.now(),
            login_successful=False
        )
        
        expected = f"{self.admin_user} - Failed login at {failed_login.login_time}"
        self.assertEqual(str(failed_login), expected)
    
    def test_login_log_session_duration_property(self):
        """Test session_duration property."""
        # Login with logout
        login_with_logout = LoginLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            login_time=timezone.now(),
            logout_time=timezone.now() + timedelta(hours=8, minutes=30)
        )
        
        expected_duration = timedelta(hours=8, minutes=30)
        self.assertEqual(login_with_logout.session_duration, expected_duration)
        
        # Login without logout
        login_without_logout = LoginLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            login_time=timezone.now()
        )
        
        self.assertIsNone(login_without_logout.session_duration)
    
    def test_login_log_ordering(self):
        """Test login log ordering by login_time."""
        # Create logs in random order
        log3 = LoginLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            login_time=timezone.now() - timedelta(days=2)
        )
        
        log1 = LoginLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            login_time=timezone.now() - timedelta(days=6)
        )
        
        log2 = LoginLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            login_time=timezone.now() - timedelta(days=4)
        )
        
        # Verify ordering (newest first)
        logs = list(LoginLog.objects.all())
        self.assertEqual(logs[0], log3)  # Most recent (2 days ago)
        self.assertEqual(logs[1], log2)  # Middle (4 days ago)
        self.assertEqual(logs[2], log1)  # Oldest (6 days ago)


class ActivityLogModelTests(TenantTestCase):
    """Test ActivityLog model."""
    
    def test_activity_log_creation(self):
        """Test basic activity log creation."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        content_type = ContentType.objects.get_for_model(Client)
        
        activity_log = ActivityLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            activity_type='document_access',
            description='Accessed client document "Contract.pdf"',
            related_content_type=content_type,
            related_object_id=str(client.pk),
            related_object=client,
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            request_path='/clients/1/documents/contract.pdf',
            metadata={
                'document_name': 'Contract.pdf',
                'document_size': '2.5MB',
                'access_duration': '5 minutes'
            }
        )
        
        self.assertEqual(activity_log.tenant, self.active_tenant)
        self.assertEqual(activity_log.user, self.admin_user)
        self.assertEqual(activity_log.activity_type, 'document_access')
        self.assertEqual(activity_log.description, 'Accessed client document "Contract.pdf"')
        self.assertEqual(activity_log.related_content_type, content_type)
        # Ensure metadata is not None
        self.assertIsNotNone(activity_log.metadata)
        self.assertEqual(activity_log.related_object_id, str(client.pk))
        self.assertEqual(activity_log.related_object, client)
        self.assertEqual(activity_log.ip_address, '192.168.1.1')
        self.assertEqual(activity_log.user_agent, 'Mozilla/5.0')
        self.assertEqual(activity_log.request_path, '/clients/1/documents/contract.pdf')
        self.assertEqual(activity_log.metadata['document_name'], 'Contract.pdf')
    
    def test_activity_log_creation_system_user(self):
        """Test activity log creation with system user."""
        activity_log = ActivityLog.objects.create(
            tenant=self.active_tenant,
            user=None,
            activity_type='system_config',
            description='System configuration updated',
            ip_address='127.0.0.1',
            metadata={'config_key': 'backup_schedule'}
        )
        
        self.assertIsNone(activity_log.user)
        self.assertEqual(activity_log.activity_type, 'system_config')
        self.assertEqual(activity_log.ip_address, '127.0.0.1')
    
    def test_activity_log_str_representation(self):
        """Test activity log string representation."""
        # User activity
        user_activity = ActivityLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            activity_type='case_view',
            description='Viewed case details'
        )
        
        expected = f"{self.admin_user} - case_view at {user_activity.timestamp}"
        self.assertEqual(str(user_activity), expected)
        
        # System activity
        system_activity = ActivityLog.objects.create(
            tenant=self.active_tenant,
            user=None,
            activity_type='system_config',
            description='System configuration updated'
        )
        
        expected = f"System - system_config at {system_activity.timestamp}"
        self.assertEqual(str(system_activity), expected)
    
    def test_activity_log_ordering(self):
        """Test activity log ordering by timestamp."""
        # Create logs in random order
        log3 = ActivityLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            activity_type='document_access',
            description='Accessed document 3'
        )
        
        log1 = ActivityLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            activity_type='document_access',
            description='Accessed document 1'
        )
        
        log2 = ActivityLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            activity_type='document_access',
            description='Accessed document 2'
        )
        
        # Verify ordering (newest first)
        logs = list(ActivityLog.objects.all())
        self.assertEqual(logs[0], log3)  # Most recent
        self.assertEqual(logs[1], log2)  # Middle
        self.assertEqual(logs[2], log1)  # Oldest


class SecurityEventModelTests(TenantTestCase):
    """Test SecurityEvent model."""
    
    def test_security_event_creation(self):
        """Test basic security event creation."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        content_type = ContentType.objects.get_for_model(Client)
        
        security_event = SecurityEvent.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            event_type='failed_login',
            description='Multiple failed login attempts detected',
            severity='high',
            source_ip='192.168.1.100',
            target_ip='192.168.1.1',
            user_agent='Mozilla/5.0',
            request_path='/login/',
            request_method='POST',
            related_content_type=content_type,
            related_object_id=str(client.pk),
            related_object=client,
            resolved=False,
            event_data={
                'attempt_count': 5,
                'timeframe': '10 minutes',
                'usernames_tried': ['admin', 'root', 'test']
            }
        )
        
        self.assertEqual(security_event.tenant, self.active_tenant)
        self.assertEqual(security_event.user, self.admin_user)
        self.assertEqual(security_event.event_type, 'failed_login')
        self.assertEqual(security_event.description, 'Multiple failed login attempts detected')
        self.assertEqual(security_event.severity, 'high')
        self.assertEqual(security_event.source_ip, '192.168.1.100')
        self.assertEqual(security_event.target_ip, '192.168.1.1')
        # Ensure event_data is not None
        self.assertIsNotNone(security_event.event_data)
        self.assertEqual(security_event.user_agent, 'Mozilla/5.0')
        self.assertEqual(security_event.request_path, '/login/')
        self.assertEqual(security_event.request_method, 'POST')
        self.assertEqual(security_event.related_content_type, content_type)
        self.assertEqual(security_event.related_object_id, str(client.pk))
        self.assertEqual(security_event.related_object, client)
        self.assertFalse(security_event.resolved)
        self.assertEqual(security_event.event_data['attempt_count'], 5)
    
    def test_security_event_creation_anonymous(self):
        """Test security event creation with anonymous user."""
        security_event = SecurityEvent.objects.create(
            tenant=self.active_tenant,
            user=None,
            event_type='unauthorized_access',
            description='Unauthorized access attempt to admin panel',
            severity='critical',
            source_ip='192.168.1.200',
            request_path='/admin/',
            request_method='GET'
        )
        
        self.assertIsNone(security_event.user)
        self.assertEqual(security_event.event_type, 'unauthorized_access')
        self.assertEqual(security_event.severity, 'critical')
        self.assertEqual(security_event.source_ip, '192.168.1.200')
    
    def test_security_event_str_representation(self):
        """Test security event string representation."""
        security_event = SecurityEvent.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            event_type='suspicious_activity',
            description='Suspicious activity detected',
            severity='medium'
        )
        
        expected = f"suspicious_activity - MEDIUM at {security_event.timestamp}"
        self.assertEqual(str(security_event), expected)
    
    def test_security_event_resolve_method(self):
        """Test resolve method."""
        security_event = SecurityEvent.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            event_type='failed_login',
            description='Failed login attempt',
            severity='medium',
            resolved=False
        )
        
        # Verify initial state
        self.assertFalse(security_event.resolved)
        self.assertIsNone(security_event.resolved_by)
        self.assertIsNone(security_event.resolved_at)
        self.assertIsNone(security_event.resolution_notes)
        
        # Resolve the event
        now = timezone.now()
        security_event.resolve(
        # Ensure resolved_at is not None
        self.assertIsNotNone(security_event.resolved_at)
            user=self.admin_user,
            notes="User contacted and password reset was completed"
        )
        
        # Verify resolved state
        security_event.refresh_from_db()
        self.assertTrue(security_event.resolved)
        self.assertEqual(security_event.resolved_by, self.admin_user)
        self.assertIsNotNone(security_event.resolved_at)
        self.assertGreaterEqual(security_event.resolved_at, now)
        self.assertEqual(security_event.resolution_notes, "User contacted and password reset was completed")
    
    def test_security_event_ordering(self):
        """Test security event ordering by timestamp."""
        # Create events in random order
        event3 = SecurityEvent.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            event_type='failed_login',
            description='Failed login 3',
            severity='low'
        )
        
        event1 = SecurityEvent.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            event_type='failed_login',
            description='Failed login 1',
            severity='low'
        )
        
        event2 = SecurityEvent.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            event_type='failed_login',
            description='Failed login 2',
            severity='low'
        )
        
        # Verify ordering (newest first)
        events = list(SecurityEvent.objects.all())
        self.assertEqual(events[0], event3)  # Most recent
        self.assertEqual(events[1], event2)  # Middle
        self.assertEqual(events[2], event1)  # Oldest


class AuditTenantIsolationTests(MultiTenantTestCase, TenantMixinTestMixin):
    """Test audit isolation between tenants."""
    
    def test_audit_logs_isolated_by_tenant(self):
        """Test that audit logs are properly isolated by tenant."""
        # Create audit logs for different tenants
        log1 = AuditLog.objects.create(
            tenant=self.tenant1,
            user=self.tenant1_admin,
            action='create',
            model_name='Client',
            object_id='1'
        )
        
        log2 = AuditLog.objects.create(
            tenant=self.tenant2,
            user=self.tenant2_admin,
            action='create',
            model_name='Client',
            object_id='2'
        )
        
        # Test isolation
        self.assertTenantIsolation(
            AuditLog,
            self.tenant1,
            self.tenant2,
            {'action': 'create'},
            {'action': 'create'}
        )
    
    def test_login_logs_isolated_by_tenant(self):
        """Test that login logs are properly isolated by tenant."""
        # Create login logs for different tenants
        log1 = LoginLog.objects.create(
            tenant=self.tenant1,
            user=self.tenant1_admin,
            login_time=timezone.now(),
            login_successful=True
        )
        
        log2 = LoginLog.objects.create(
            tenant=self.tenant2,
            user=self.tenant2_admin,
            login_time=timezone.now(),
            login_successful=True
        )
        
        # Test isolation
        self.assertTenantIsolation(
            LoginLog,
            self.tenant1,
            self.tenant2,
            {'login_successful': True},
            {'login_successful': True}
        )
    
    def test_activity_logs_isolated_by_tenant(self):
        """Test that activity logs are properly isolated by tenant."""
        # Create activity logs for different tenants
        log1 = ActivityLog.objects.create(
            tenant=self.tenant1,
            user=self.tenant1_admin,
            activity_type='document_access',
            description='Accessed document 1'
        )
        
        log2 = ActivityLog.objects.create(
            tenant=self.tenant2,
            user=self.tenant2_admin,
            activity_type='document_access',
            description='Accessed document 2'
        )
        
        # Test isolation
        self.assertTenantIsolation(
            ActivityLog,
            self.tenant1,
            self.tenant2,
            {'activity_type': 'document_access'},
            {'activity_type': 'document_access'}
        )
    
    def test_security_events_isolated_by_tenant(self):
        """Test that security events are properly isolated by tenant."""
        # Create security events for different tenants
        event1 = SecurityEvent.objects.create(
            tenant=self.tenant1,
            user=self.tenant1_admin,
            event_type='failed_login',
            description='Failed login 1',
            severity='medium'
        )
        
        event2 = SecurityEvent.objects.create(
            tenant=self.tenant2,
            user=self.tenant2_admin,
            event_type='failed_login',
            description='Failed login 2',
            severity='medium'
        )
        
        # Test isolation
        self.assertTenantIsolation(
            SecurityEvent,
            self.tenant1,
            self.tenant2,
            {'event_type': 'failed_login'},
            {'event_type': 'failed_login'}
        )


class AuditTransactionTests(TransactionTestCase):
    """Test audit functionality with transactions."""
    
    def setUp(self):
        """Set up test data for transaction tests."""
        # Create a tenant
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant'
        )
        
        # Create a user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def test_audit_log_creation_rollback_on_error(self):
        """Test audit log creation rollback on error."""
        # Try to create an audit log with invalid data
        with self.assertRaises(Exception):  # IntegrityError or ValidationError
            AuditLog.objects.create(
                tenant=self.tenant,
                user=self.user,
                action='',  # Invalid: empty action
                model_name='Client'
            )
        
        # Verify tenant and user still exist (transaction rolled back)
        self.assertTrue(Tenant.objects.filter(slug='test-tenant').exists())
        self.assertTrue(User.objects.filter(username='testuser').exists())
    
    def test_security_event_resolution_transaction(self):
        """Test security event resolution in transaction."""
        # Create security event
        security_event = SecurityEvent.objects.create(
            tenant=self.tenant,
            user=self.user,
            event_type='failed_login',
            description='Failed login attempt',
            severity='medium',
            resolved=False
        )
        
        # Resolve the event
        security_event.resolve(
            user=self.user,
            notes="Issue resolved"
        )
        
        # Verify resolution
        security_event.refresh_from_db()
        self.assertTrue(security_event.resolved)
        self.assertEqual(security_event.resolved_by, self.user)
        self.assertIsNotNone(security_event.resolved_at)
        self.assertEqual(security_event.resolution_notes, "Issue resolved")


class AuditIntegrationTests(TenantTestCase):
    """Test audit integration with other modules."""
    
    def test_audit_log_client_relationship(self):
        """Test audit log-client relationship."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        content_type = ContentType.objects.get_for_model(Client)
        
        audit_log = AuditLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            action='create',
            model_name='Client',
            object_id=str(client.pk),
            object_repr=str(client),
            content_type=content_type,
            content_object=client
        )
        
        # Test relationship
        self.assertEqual(audit_log.content_object, client)
        self.assertEqual(audit_log.object_id, str(client.pk))
    
    def test_activity_log_case_relationship(self):
        """Test activity log-case relationship."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        case = Case.objects.create(
            tenant=self.active_tenant,
            title='Test Case',
            case_number='CASE-001',
            client=client
        )
        
        content_type = ContentType.objects.get_for_model(Case)
        
        activity_log = ActivityLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            activity_type='case_view',
            description='Viewed case details',
            related_content_type=content_type,
            related_object_id=str(case.pk),
            related_object=case
        )
        
        # Test relationship
        self.assertEqual(activity_log.related_object, case)
        self.assertEqual(activity_log.related_object_id, str(case.pk))
    
    def test_security_event_client_relationship(self):
        """Test security event-client relationship."""
        client = Client.objects.create(
            tenant=self.active_tenant,
            first_name='Test',
            last_name='Client',
            email='client@example.com'
        )
        
        content_type = ContentType.objects.get_for_model(Client)
        
        security_event = SecurityEvent.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            event_type='unauthorized_access',
            description='Unauthorized access attempt',
            severity='high',
            related_content_type=content_type,
            related_object_id=str(client.pk),
            related_object=client
        )
        
        # Test relationship
        self.assertEqual(security_event.related_object, client)
        self.assertEqual(security_event.related_object_id, str(client.pk))
    
    def test_audit_log_user_relationship(self):
        """Test audit log-user relationship."""
        audit_log = AuditLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            action='create',
            model_name='Client',
            object_id='123'
        )
        
        # Test relationship
        self.assertEqual(audit_log.user, self.admin_user)
        self.assertTrue(AuditLog.objects.filter(user=self.admin_user).exists())
    
    def test_login_log_user_relationship(self):
        """Test login log-user relationship."""
        login_log = LoginLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            login_time=timezone.now(),
            login_successful=True
        )
        
        # Test relationship
        self.assertEqual(login_log.user, self.admin_user)
        self.assertTrue(LoginLog.objects.filter(user=self.admin_user).exists())
    
    def test_activity_log_user_relationship(self):
        """Test activity log-user relationship."""
        activity_log = ActivityLog.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            activity_type='document_access',
            description='Accessed document'
        )
        
        # Test relationship
        self.assertEqual(activity_log.user, self.admin_user)
        self.assertTrue(ActivityLog.objects.filter(user=self.admin_user).exists())
    
    def test_security_event_user_relationship(self):
        """Test security event-user relationship."""
        security_event = SecurityEvent.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            event_type='failed_login',
            description='Failed login attempt',
            severity='medium'
        )
        
        # Test relationship
        self.assertEqual(security_event.user, self.admin_user)
        self.assertTrue(SecurityEvent.objects.filter(user=self.admin_user).exists())
    
    def test_security_event_resolved_by_relationship(self):
        """Test security event-resolved_by relationship."""
        security_event = SecurityEvent.objects.create(
            tenant=self.active_tenant,
            user=self.admin_user,
            event_type='failed_login',
            description='Failed login attempt',
            severity='medium',
            resolved=False
        )
        
        # Resolve the event
        security_event.resolve(user=self.lawyer_user, notes="Resolved")
        
        # Test relationship
        security_event.refresh_from_db()
        self.assertEqual(security_event.resolved_by, self.lawyer_user)
        self.assertTrue(SecurityEvent.objects.filter(resolved_by=self.lawyer_user).exists())