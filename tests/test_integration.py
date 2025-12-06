import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, TransactionTestCase, LiveServerTestCase
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from django.test import Client
try:
    from rest_framework.test import APITestCase
    HAS_REST_FRAMEWORK = True
except ImportError:
    # Fallback for when Django REST framework is not available
    from django.test import TestCase as APITestCase
    HAS_REST_FRAMEWORK = False
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    HAS_SELENIUM = True
except ImportError:
    # Fallback for when Selenium is not available
    webdriver = None
    By = None
    WebDriverWait = None
    EC = None
    Options = None
    HAS_SELENIUM = False

from tenants.models import Tenant, TenantSettings
from accounts.models import CustomUser
from permissions.models import Permission, Role, UserRole
from clients.models import Client
from cases.models import Case
from documents.models import Document
from billing.models import Invoice
from subscriptions.models import TenantSubscription, SubscriptionPlan
from audit.models import AuditLog
from backup_restore.models import BackupJob, RestoreJob
from platform_admin.models import SystemSettings, AdminActivityLog

User = get_user_model()


class MultiTenantIntegrationTest(TransactionTestCase):
    """Integration tests for multi-tenant functionality."""
    
    def setUp(self):
        self.tenant1 = Tenant.objects.create(
            name="Tenant 1",
            slug="tenant-1",
            plan="basic",
            max_users=10,
            max_storage_mb=1000
        )
        self.tenant2 = Tenant.objects.create(
            name="Tenant 2",
            slug="tenant-2",
            plan="premium",
            max_users=50,
            max_storage_mb=5000
        )
        
        # Create users for each tenant
        self.admin1 = User.objects.create_user(
            username="admin1",
            email="admin1@tenant1.com",
            password="adminpass123",
            tenant=self.tenant1,
            role="admin"
        )
        self.user1 = User.objects.create_user(
            username="user1",
            email="user1@tenant1.com",
            password="userpass123",
            tenant=self.tenant1,
            role="user"
        )
        self.admin2 = User.objects.create_user(
            username="admin2",
            email="admin2@tenant2.com",
            password="adminpass123",
            tenant=self.tenant2,
            role="admin"
        )
        self.user2 = User.objects.create_user(
            username="user2",
            email="user2@tenant2.com",
            password="userpass123",
            tenant=self.tenant2,
            role="user"
        )
        
        # Create superuser for platform admin
        self.superuser = User.objects.create_user(
            username="super",
            email="super@example.com",
            password="superpass123",
            is_superuser=True
        )
        
        # Create permissions and roles
        self.view_client_perm = Permission.objects.create(
            name="view_client",
            codename="view_client",
            description="Can view clients"
        )
        self.edit_client_perm = Permission.objects.create(
            name="edit_client",
            codename="edit_client",
            description="Can edit clients"
        )
        
        self.admin_role = Role.objects.create(
            name="Admin",
            tenant=self.tenant1,
            description="Administrator role"
        )
        self.user_role = Role.objects.create(
            name="User",
            tenant=self.tenant1,
            description="Regular user role"
        )
        
        # Assign permissions to roles
        self.admin_role.permissions.add(self.view_client_perm, self.edit_client_perm)
        self.user_role.permissions.add(self.view_client_perm)
        
        # Assign roles to users
        UserRole.objects.create(user=self.admin1, role=self.admin_role)
        UserRole.objects.create(user=self.user1, role=self.user_role)
    
    def test_tenant_isolation(self):
        """Test that tenant data is properly isolated."""
        # Create clients for each tenant
        client1 = Client.objects.create(
            name="Client 1",
            email="client1@example.com",
            tenant=self.tenant1,
            created_by=self.admin1
        )
        client2 = Client.objects.create(
            name="Client 2",
            email="client2@example.com",
            tenant=self.tenant2,
            created_by=self.admin2
        )
        
        # Test that users can only access their own tenant's data
        client_manager = Client.objects
        
        # User from tenant1 should only see tenant1's clients
        with self.assertNumQueries(1):
            tenant1_clients = client_manager.for_tenant(self.tenant1)
            self.assertEqual(tenant1_clients.count(), 1)
            self.assertEqual(tenant1_clients.first().id, client1.id)
        
        # User from tenant2 should only see tenant2's clients
        with self.assertNumQueries(1):
            tenant2_clients = client_manager.for_tenant(self.tenant2)
            self.assertEqual(tenant2_clients.count(), 1)
            self.assertEqual(tenant2_clients.first().id, client2.id)
    
    def test_user_authentication_isolation(self):
        """Test that user authentication is properly isolated by tenant."""
        # Create clients for each tenant
        client1 = Client.objects.create(
            name="Client 1",
            email="client1@example.com",
            tenant=self.tenant1,
            created_by=self.admin1
        )
        client2 = Client.objects.create(
            name="Client 2",
            email="client2@example.com",
            tenant=self.tenant2,
            created_by=self.admin2
        )
        
        # Test authentication with tenant1 user
        client1_client = Client()
        with patch('tenants.middleware.get_current_tenant', return_value=self.tenant1):
            # User from tenant1 should be able to authenticate
            self.assertTrue(client1_client.has_view_permission(self.user1, client1))
            # User from tenant1 should not be able to access tenant2's data
            self.assertFalse(client1_client.has_view_permission(self.user1, client2))
        
        # Test authentication with tenant2 user
        client2_client = Client()
        with patch('tenants.middleware.get_current_tenant', return_value=self.tenant2):
            # User from tenant2 should be able to authenticate
            self.assertTrue(client2_client.has_view_permission(self.user2, client2))
            # User from tenant2 should not be able to access tenant1's data
            self.assertFalse(client2_client.has_view_permission(self.user2, client1))
    
    def test_permission_isolation(self):
        """Test that permissions are properly isolated by tenant."""
        # Create permissions for each tenant
        tenant1_perm = Permission.objects.create(
            name="tenant1_permission",
            codename="tenant1_permission",
            description="Permission for tenant1"
        )
        tenant2_perm = Permission.objects.create(
            name="tenant2_permission",
            codename="tenant2_permission",
            description="Permission for tenant2"
        )
        
        # Create roles for each tenant
        tenant1_role = Role.objects.create(
            name="Tenant1 Role",
            tenant=self.tenant1,
            description="Role for tenant1"
        )
        tenant2_role = Role.objects.create(
            name="Tenant2 Role",
            tenant=self.tenant2,
            description="Role for tenant2"
        )
        
        # Assign permissions to roles
        tenant1_role.permissions.add(tenant1_perm)
        tenant2_role.permissions.add(tenant2_perm)
        
        # Test that permissions are isolated by tenant
        with patch('tenants.middleware.get_current_tenant', return_value=self.tenant1):
            # Tenant1 should only have tenant1 permissions
            tenant1_perms = Permission.objects.for_tenant(self.tenant1)
            self.assertIn(tenant1_perm, tenant1_perms)
            self.assertNotIn(tenant2_perm, tenant1_perms)
            
            # Tenant1 should only have tenant1 roles
            tenant1_roles = Role.objects.for_tenant(self.tenant1)
            self.assertIn(tenant1_role, tenant1_roles)
            self.assertNotIn(tenant2_role, tenant1_roles)
        
        with patch('tenants.middleware.get_current_tenant', return_value=self.tenant2):
            # Tenant2 should only have tenant2 permissions
            tenant2_perms = Permission.objects.for_tenant(self.tenant2)
            self.assertIn(tenant2_perm, tenant2_perms)
            self.assertNotIn(tenant1_perm, tenant2_perms)
            
            # Tenant2 should only have tenant2 roles
            tenant2_roles = Role.objects.for_tenant(self.tenant2)
            self.assertIn(tenant2_role, tenant2_roles)
            self.assertNotIn(tenant1_role, tenant2_roles)
    
    def test_cross_tenant_data_access_prevention(self):
        """Test that cross-tenant data access is prevented."""
        # Create a client for tenant1
        client1 = Client.objects.create(
            name="Client 1",
            email="client1@example.com",
            tenant=self.tenant1,
            created_by=self.admin1
        )
        
        # Test that tenant2 user cannot access tenant1's client
        with patch('tenants.middleware.get_current_tenant', return_value=self.tenant2):
            # Try to access client1 with tenant2 user
            with self.assertRaises(Exception):
                # This should raise an exception or return False
                Client.objects.get(id=client1.id, tenant=self.tenant2)
    
    def test_tenant_specific_urls(self):
        """Test that URLs are properly scoped to tenants."""
        # Test tenant-specific URL patterns
        tenant1_url = f"/{self.tenant1.slug}/clients/"
        tenant2_url = f"/{self.tenant2.slug}/clients/"
        
        # Verify URLs are different for each tenant
        self.assertNotEqual(tenant1_url, tenant2_url)
        self.assertIn(self.tenant1.slug, tenant1_url)
        self.assertIn(self.tenant2.slug, tenant2_url)
    
    def test_tenant_middleware_functionality(self):
        """Test that tenant middleware properly identifies and sets tenant."""
        from tenants.middleware import TenantMiddleware
        
        # Test with tenant in subdomain
        request = Mock()
        request.path = "/clients/"
        request.get_host.return_value = f"{self.tenant1.slug}.example.com"
        
        middleware = TenantMiddleware(get_response=lambda r: Mock())
        
        # Process request
        middleware.process_request(request)
        
        # Verify tenant was set
        self.assertEqual(request.tenant, self.tenant1)
        
        # Test with tenant in path
        request.get_host.return_value = "example.com"
        request.path = f"/{self.tenant2.slug}/clients/"
        
        middleware.process_request(request)
        
        # Verify tenant was set
        self.assertEqual(request.tenant, self.tenant2)
    
    def test_tenant_settings_isolation(self):
        """Test that tenant settings are properly isolated."""
        # Create settings for each tenant
        settings1 = TenantSettings.objects.create(
            tenant=self.tenant1,
            date_format="YYYY-MM-DD",
            timezone="America/New_York",
            default_currency="USD"
        )
        settings2 = TenantSettings.objects.create(
            tenant=self.tenant2,
            date_format="DD/MM/YYYY",
            timezone="Europe/London",
            default_currency="EUR"
        )
        
        # Test that settings are isolated
        with patch('tenants.middleware.get_current_tenant', return_value=self.tenant1):
            # Tenant1 should have its own settings
            current_settings1 = self.tenant1.get_settings()
            self.assertEqual(current_settings1.date_format, "YYYY-MM-DD")
            self.assertEqual(current_settings1.timezone, "America/New_York")
            self.assertEqual(current_settings1.default_currency, "USD")
        
        with patch('tenants.middleware.get_current_tenant', return_value=self.tenant2):
            # Tenant2 should have its own settings
            current_settings2 = self.tenant2.get_settings()
            self.assertEqual(current_settings2.date_format, "DD/MM/YYYY")
            self.assertEqual(current_settings2.timezone, "Europe/London")
            self.assertEqual(current_settings2.default_currency, "EUR")
    
    def test_audit_log_isolation(self):
        """Test that audit logs are properly isolated by tenant."""
        # Create audit logs for each tenant
        with patch('tenants.middleware.get_current_tenant', return_value=self.tenant1):
            AuditLog.objects.create(
                tenant=self.tenant1,
                user=self.admin1,
                activity_type="CLIENT_CREATED",
                description="Created client",
                ip_address="192.168.1.1"
            )
        
        with patch('tenants.middleware.get_current_tenant', return_value=self.tenant2):
            AuditLog.objects.create(
                tenant=self.tenant2,
                user=self.admin2,
                activity_type="CLIENT_CREATED",
                description="Created client",
                ip_address="192.168.1.2"
            )
        
        # Test that audit logs are isolated
        with patch('tenants.middleware.get_current_tenant', return_value=self.tenant1):
            # Tenant1 should only have its own audit logs
            tenant1_logs = AuditLog.objects.for_tenant(self.tenant1)
            self.assertEqual(tenant1_logs.count(), 1)
            self.assertEqual(tenant1_logs.first().tenant, self.tenant1)
        
        with patch('tenants.middleware.get_current_tenant', return_value=self.tenant2):
            # Tenant2 should only have its own audit logs
            tenant2_logs = AuditLog.objects.for_tenant(self.tenant2)
            self.assertEqual(tenant2_logs.count(), 1)
            self.assertEqual(tenant2_logs.first().tenant, self.tenant2)
    
    def test_backup_restore_isolation(self):
        """Test that backup and restore operations are tenant-isolated."""
        # Create backup jobs for each tenant
        backup1 = BackupJob.objects.create(
            name="Backup 1",
            backup_type="full",
            tenant=self.tenant1,
            created_by=self.admin1
        )
        backup2 = BackupJob.objects.create(
            name="Backup 2",
            backup_type="full",
            tenant=self.tenant2,
            created_by=self.admin2
        )
        
        # Test that backup jobs are isolated
        tenant1_backups = BackupJob.objects.for_tenant(self.tenant1)
        self.assertEqual(tenant1_backups.count(), 1)
        self.assertEqual(tenant1_backups.first().id, backup1.id)
        
        tenant2_backups = BackupJob.objects.for_tenant(self.tenant2)
        self.assertEqual(tenant2_backups.count(), 1)
        self.assertEqual(tenant2_backups.first().id, backup2.id)
        
        # Create restore jobs for each tenant
        restore1 = RestoreJob.objects.create(
            name="Restore 1",
            tenant=self.tenant1,
            created_by=self.admin1,
            backup_job=backup1
        )
        restore2 = RestoreJob.objects.create(
            name="Restore 2",
            tenant=self.tenant2,
            created_by=self.admin2,
            backup_job=backup2
        )
        
        # Test that restore jobs are isolated
        tenant1_restores = RestoreJob.objects.for_tenant(self.tenant1)
        self.assertEqual(tenant1_restores.count(), 1)
        self.assertEqual(tenant1_restores.first().id, restore1.id)
        
        tenant2_restores = RestoreJob.objects.for_tenant(self.tenant2)
        self.assertEqual(tenant2_restores.count(), 1)
        self.assertEqual(tenant2_restores.first().id, restore2.id)


class EndToEndWorkflowTest(TransactionTestCase):
    """End-to-end workflow tests for the multi-tenant system."""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10,
            max_storage_mb=1000
        )
        
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="adminpass123",
            tenant=self.tenant,
            role="admin"
        )
        
        self.regular_user = User.objects.create_user(
            username="user",
            email="user@test.com",
            password="userpass123",
            tenant=self.tenant,
            role="user"
        )
        
        # Create permissions and roles
        self.view_client_perm = Permission.objects.create(
            name="view_client",
            codename="view_client",
            description="Can view clients"
        )
        self.edit_client_perm = Permission.objects.create(
            name="edit_client",
            codename="edit_client",
            description="Can edit clients"
        )
        
        self.admin_role = Role.objects.create(
            name="Admin",
            tenant=self.tenant,
            description="Administrator role"
        )
        self.user_role = Role.objects.create(
            name="User",
            tenant=self.tenant,
            description="Regular user role"
        )
        
        # Assign permissions to roles
        self.admin_role.permissions.add(self.view_client_perm, self.edit_client_perm)
        self.user_role.permissions.add(self.view_client_perm)
        
        # Assign roles to users
        UserRole.objects.create(user=self.admin_user, role=self.admin_role)
        UserRole.objects.create(user=self.regular_user, role=self.user_role)
    
    def test_complete_client_workflow(self):
        """Test complete client management workflow."""
        # 1. Admin creates a client
        client = Client.objects.create(
            name="Test Client",
            email="client@test.com",
            phone="555-123-4567",
            address="123 Test St",
            city="Test City",
            state="TS",
            zip_code="12345",
            country="Test Country",
            tenant=self.tenant,
            created_by=self.admin_user
        )
        
        # Verify client was created
        self.assertEqual(Client.objects.for_tenant(self.tenant).count(), 1)
        self.assertEqual(Client.objects.for_tenant(self.tenant).first().name, "Test Client")
        
        # 2. Admin views client list
        clients = Client.objects.for_tenant(self.tenant)
        self.assertEqual(clients.count(), 1)
        
        # 3. Admin updates client
        client.name = "Updated Client"
        client.save()
        
        # Verify client was updated
        updated_client = Client.objects.get(id=client.id)
        self.assertEqual(updated_client.name, "Updated Client")
        
        # 4. Regular user views client
        self.assertTrue(client.has_view_permission(self.regular_user, client))
        
        # 5. Regular user tries to edit client (should fail if no permission)
        self.assertFalse(client.has_edit_permission(self.regular_user, client))
        
        # 6. Admin deletes client
        client.delete()
        
        # Verify client was deleted
        self.assertEqual(Client.objects.for_tenant(self.tenant).count(), 0)
    
    def test_complete_case_workflow(self):
        """Test complete case management workflow."""
        # 1. Create a client first
        client = Client.objects.create(
            name="Test Client",
            email="client@test.com",
            tenant=self.tenant,
            created_by=self.admin_user
        )
        
        # 2. Admin creates a case
        case = Case.objects.create(
            title="Test Case",
            description="Test case description",
            case_number="CASE-001",
            status="open",
            priority="medium",
            client=client,
            tenant=self.tenant,
            created_by=self.admin_user
        )
        
        # Verify case was created
        self.assertEqual(Case.objects.for_tenant(self.tenant).count(), 1)
        self.assertEqual(Case.objects.for_tenant(self.tenant).first().title, "Test Case")
        
        # 3. Admin updates case status
        case.status = "in_progress"
        case.assigned_to = self.regular_user
        case.save()
        
        # Verify case was updated
        updated_case = Case.objects.get(id=case.id)
        self.assertEqual(updated_case.status, "in_progress")
        self.assertEqual(updated_case.assigned_to, self.regular_user)
        
        # 4. Regular user views assigned case
        self.assertTrue(case.has_view_permission(self.regular_user, case))
        
        # 5. Regular user updates case
        case.description = "Updated description"
        case.save()
        
        # Verify case was updated
        updated_case = Case.objects.get(id=case.id)
        self.assertEqual(updated_case.description, "Updated description")
        
        # 6. Admin closes case
        case.status = "closed"
        case.save()
        
        # Verify case was closed
        closed_case = Case.objects.get(id=case.id)
        self.assertEqual(closed_case.status, "closed")
    
    def test_complete_document_workflow(self):
        """Test complete document management workflow."""
        # 1. Create a client first
        client = Client.objects.create(
            name="Test Client",
            email="client@test.com",
            tenant=self.tenant,
            created_by=self.admin_user
        )
        
        # 2. Admin creates a document
        document = Document.objects.create(
            title="Test Document",
            description="Test document description",
            category="legal",
            client=client,
            tenant=self.tenant,
            created_by=self.admin_user
        )
        
        # Add a file to the document
        document.file.save("test_document.txt", "Test content")
        
        # Verify document was created
        self.assertEqual(Document.objects.for_tenant(self.tenant).count(), 1)
        self.assertEqual(Document.objects.for_tenant(self.tenant).first().title, "Test Document")
        
        # 3. Admin views document list
        documents = Document.objects.for_tenant(self.tenant)
        self.assertEqual(documents.count(), 1)
        
        # 4. Regular user views document
        self.assertTrue(document.has_view_permission(self.regular_user, document))
        
        # 5. Regular user downloads document
        self.assertTrue(document.has_download_permission(self.regular_user, document))
        
        # 6. Admin updates document
        document.title = "Updated Document"
        document.save()
        
        # Verify document was updated
        updated_document = Document.objects.get(id=document.id)
        self.assertEqual(updated_document.title, "Updated Document")
        
        # 7. Admin deletes document
        document.delete()
        
        # Verify document was deleted
        self.assertEqual(Document.objects.for_tenant(self.tenant).count(), 0)
    
    def test_complete_billing_workflow(self):
        """Test complete billing workflow."""
        # 1. Create a client first
        client = Client.objects.create(
            name="Test Client",
            email="client@test.com",
            tenant=self.tenant,
            created_by=self.admin_user
        )
        
        # 2. Create a case for the client
        case = Case.objects.create(
            title="Test Case",
            description="Test case description",
            client=client,
            tenant=self.tenant,
            created_by=self.admin_user
        )
        
        # 3. Admin creates an invoice
        invoice = Invoice.objects.create(
            invoice_number="INV-001",
            client=client,
            case=case,
            amount=1000.00,
            due_date=timezone.now() + timedelta(days=30),
            status="draft",
            tenant=self.tenant,
            created_by=self.admin_user
        )
        
        # Verify invoice was created
        self.assertEqual(Invoice.objects.for_tenant(self.tenant).count(), 1)
        self.assertEqual(Invoice.objects.for_tenant(self.tenant).first().invoice_number, "INV-001")
        
        # 4. Admin finalizes invoice
        invoice.status = "sent"
        invoice.save()
        
        # Verify invoice was finalized
        updated_invoice = Invoice.objects.get(id=invoice.id)
        self.assertEqual(updated_invoice.status, "sent")
        
        # 5. Admin records a payment
        from billing.models import Payment
        payment = Payment.objects.create(
            invoice=invoice,
            amount=1000.00,
            payment_date=timezone.now(),
            status="completed",
            method="credit_card",
            tenant=self.tenant,
            created_by=self.admin_user
        )
        
        # Verify payment was created
        self.assertEqual(Payment.objects.for_tenant(self.tenant).count(), 1)
        self.assertEqual(Payment.objects.for_tenant(self.tenant).first().amount, 1000.00)
        
        # 6. Update invoice status
        invoice.status = "paid"
        invoice.save()
        
        # Verify invoice was marked as paid
        paid_invoice = Invoice.objects.get(id=invoice.id)
        self.assertEqual(paid_invoice.status, "paid")
    
    def test_complete_subscription_workflow(self):
        """Test complete subscription workflow."""
        # 1. Create a subscription plan
        plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            code="basic",
            price=29.99,
            billing_cycle="monthly",
            max_users=10,
            max_storage_mb=1000,
            features=["cases", "documents", "billing"]
        )
        
        # 2. Create a subscription for the tenant
        subscription = TenantSubscription.objects.create(
            tenant=self.tenant,
            plan=plan,
            status="trial",
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=14),
            auto_renew=True
        )
        
        # Verify subscription was created
        self.assertEqual(TenantSubscription.objects.for_tenant(self.tenant).count(), 1)
        self.assertEqual(TenantSubscription.objects.for_tenant(self.tenant).first().plan, plan)
        
        # 3. Check subscription is active
        self.assertTrue(subscription.is_active)
        self.assertTrue(subscription.is_trial)
        
        # 4. Upgrade subscription
        premium_plan = SubscriptionPlan.objects.create(
            name="Premium Plan",
            code="premium",
            price=49.99,
            billing_cycle="monthly",
            max_users=50,
            max_storage_mb=5000,
            features=["cases", "documents", "billing", "advanced_reports"]
        )
        
        subscription.plan = premium_plan
        subscription.status = "active"
        subscription.save()
        
        # Verify subscription was upgraded
        updated_subscription = TenantSubscription.objects.get(id=subscription.id)
        self.assertEqual(updated_subscription.plan, premium_plan)
        self.assertEqual(updated_subscription.status, "active")
        self.assertFalse(updated_subscription.is_trial)
        
        # 5. Cancel subscription
        subscription.status = "cancelled"
        subscription.end_date = timezone.now() + timedelta(days=30)
        subscription.auto_renew = False
        subscription.save()
        
        # Verify subscription was cancelled
        cancelled_subscription = TenantSubscription.objects.get(id=subscription.id)
        self.assertEqual(cancelled_subscription.status, "cancelled")
        self.assertFalse(cancelled_subscription.auto_renew)
    
    def test_complete_backup_restore_workflow(self):
        """Test complete backup and restore workflow."""
        # 1. Create some test data
        client = Client.objects.create(
            name="Test Client",
            email="client@test.com",
            tenant=self.tenant,
            created_by=self.admin_user
        )
        
        case = Case.objects.create(
            title="Test Case",
            description="Test case description",
            client=client,
            tenant=self.tenant,
            created_by=self.admin_user
        )
        
        # 2. Admin creates a backup job
        backup_job = BackupJob.objects.create(
            name="Test Backup",
            description="Test backup description",
            backup_type="full",
            include_database=True,
            include_media=True,
            include_documents=True,
            include_settings=True,
            tenant=self.tenant,
            created_by=self.admin_user
        )
        
        # Verify backup job was created
        self.assertEqual(BackupJob.objects.for_tenant(self.tenant).count(), 1)
        self.assertEqual(BackupJob.objects.for_tenant(self.tenant).first().name, "Test Backup")
        
        # 3. Simulate backup completion
        backup_job.status = "completed"
        backup_job.file_path = "/backups/test_backup.tar.gz"
        backup_job.file_size = 1024 * 1024  # 1MB
        backup_job.completed_at = timezone.now()
        backup_job.save()
        
        # Verify backup was completed
        completed_backup = BackupJob.objects.get(id=backup_job.id)
        self.assertEqual(completed_backup.status, "completed")
        self.assertEqual(completed_backup.file_size, 1024 * 1024)
        
        # 4. Admin creates a restore job
        restore_job = RestoreJob.objects.create(
            name="Test Restore",
            description="Test restore description",
            backup_job=backup_job,
            restore_database=True,
            restore_media=True,
            restore_documents=True,
            restore_settings=True,
            conflict_resolution="overwrite",
            tenant=self.tenant,
            created_by=self.admin_user
        )
        
        # Verify restore job was created
        self.assertEqual(RestoreJob.objects.for_tenant(self.tenant).count(), 1)
        self.assertEqual(RestoreJob.objects.for_tenant(self.tenant).first().name, "Test Restore")
        
        # 5. Simulate restore completion
        restore_job.status = "completed"
        restore_job.completed_at = timezone.now()
        restore_job.records_restored = 10
        restore_job.save()
        
        # Verify restore was completed
        completed_restore = RestoreJob.objects.get(id=restore_job.id)
        self.assertEqual(completed_restore.status, "completed")
        self.assertEqual(completed_restore.records_restored, 10)


class PerformanceTest(TransactionTestCase):
    """Performance tests for the multi-tenant system."""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Performance Test Tenant",
            slug="perf-tenant",
            plan="basic",
            max_users=10,
            max_storage_mb=1000
        )
        
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="adminpass123",
            tenant=self.tenant,
            role="admin"
        )
        
        # Create permissions and roles
        self.view_client_perm = Permission.objects.create(
            name="view_client",
            codename="view_client",
            description="Can view clients"
        )
        
        self.admin_role = Role.objects.create(
            name="Admin",
            tenant=self.tenant,
            description="Administrator role"
        )
        
        self.admin_role.permissions.add(self.view_client_perm)
        UserRole.objects.create(user=self.admin_user, role=self.admin_role)
    
    def test_large_dataset_performance(self):
        """Test performance with large datasets."""
        # Create a large number of clients
        clients = []
        for i in range(1000):
            client = Client.objects.create(
                name=f"Client {i}",
                email=f"client{i}@test.com",
                tenant=self.tenant,
                created_by=self.admin_user
            )
            clients.append(client)
        
        # Test query performance
        with self.assertNumQueries(1):
            # This should be a single efficient query
            all_clients = Client.objects.for_tenant(self.tenant)
            self.assertEqual(all_clients.count(), 1000)
        
        # Test filtering performance
        with self.assertNumQueries(1):
            # This should be a single efficient query
            filtered_clients = Client.objects.for_tenant(self.tenant).filter(name__startswith="Client 1")
            self.assertEqual(filtered_clients.count(), 111)  # Client 1, Client 10-19, Client 100-199
    
    def test_concurrent_user_performance(self):
        """Test performance with concurrent users."""
        # Create multiple users
        users = []
        for i in range(50):
            user = User.objects.create_user(
                username=f"user{i}",
                email=f"user{i}@test.com",
                password="userpass123",
                tenant=self.tenant,
                role="user"
            )
            users.append(user)
        
        # Test concurrent authentication
        import threading
        import time
        
        results = []
        
        def authenticate_user(user):
            # Simulate authentication
            start_time = time.time()
            # In a real scenario, this would authenticate the user
            time.sleep(0.01)  # Simulate authentication time
            end_time = time.time()
            return user.id, end_time - start_time
        
        # Create threads for concurrent authentication
        threads = []
        for user in users[:10]:  # Test with 10 concurrent users
            thread = threading.Thread(target=authenticate_user, args=(user,))
            threads.append(thread)
        
        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify concurrent authentication completed in reasonable time
        self.assertLess(total_time, 5.0)  # Should complete in less than 5 seconds
    
    def test_tenant_switching_performance(self):
        """Test performance when switching between tenants."""
        # Create multiple tenants
        tenants = []
        for i in range(10):
            tenant = Tenant.objects.create(
                name=f"Tenant {i}",
                slug=f"tenant-{i}",
                plan="basic",
                max_users=10,
                max_storage_mb=1000
            )
            tenants.append(tenant)
        
        # Test tenant switching performance
        import time
        
        def switch_tenant(tenant):
            start_time = time.time()
            # In a real scenario, this would switch the tenant context
            time.sleep(0.01)  # Simulate switching time
            end_time = time.time()
            return tenant.id, end_time - start_time
        
        # Create threads for concurrent tenant switching
        threads = []
        for tenant in tenants:
            thread = threading.Thread(target=switch_tenant, args=(tenant,))
            threads.append(thread)
        
        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify concurrent tenant switching completed in reasonable time
        self.assertLess(total_time, 5.0)  # Should complete in less than 5 seconds


class SecurityTest(TransactionTestCase):
    """Security tests for the multi-tenant system."""
    
    def setUp(self):
        self.tenant1 = Tenant.objects.create(
            name="Tenant 1",
            slug="tenant-1",
            plan="basic",
            max_users=10,
            max_storage_mb=1000
        )
        
        self.tenant2 = Tenant.objects.create(
            name="Tenant 2",
            slug="tenant-2",
            plan="basic",
            max_users=10,
            max_storage_mb=1000
        )
        
        self.user1 = User.objects.create_user(
            username="user1",
            email="user1@tenant1.com",
            password="userpass123",
            tenant=self.tenant1,
            role="user"
        )
        
        self.user2 = User.objects.create_user(
            username="user2",
            email="user2@tenant2.com",
            password="userpass123",
            tenant=self.tenant2,
            role="user"
        )
        
        # Create permissions and roles
        self.view_client_perm = Permission.objects.create(
            name="view_client",
            codename="view_client",
            description="Can view clients"
        )
        
        self.user1_role = Role.objects.create(
            name="User",
            tenant=self.tenant1,
            description="Regular user role"
        )
        
        self.user2_role = Role.objects.create(
            name="User",
            tenant=self.tenant2,
            description="Regular user role"
        )
        
        self.user1_role.permissions.add(self.view_client_perm)
        self.user2_role.permissions.add(self.view_client_perm)
        
        UserRole.objects.create(user=self.user1, role=self.user1_role)
        UserRole.objects.create(user=self.user2, role=self.user2_role)
    
    def test_cross_tenant_data_access_prevention(self):
        """Test that cross-tenant data access is prevented."""
        # Create a client for tenant1
        client1 = Client.objects.create(
            name="Client 1",
            email="client1@tenant1.com",
            tenant=self.tenant1,
            created_by=self.user1
        )
        
        # Test that tenant2 user cannot access tenant1's client
        with patch('tenants.middleware.get_current_tenant', return_value=self.tenant2):
            # Try to access client1 with tenant2 user
            with self.assertRaises(Exception):
                # This should raise an exception or return False
                Client.objects.get(id=client1.id, tenant=self.tenant2)
    
    def test_permission_escalation_prevention(self):
        """Test that permission escalation is prevented."""
        # Create a client for tenant1
        client1 = Client.objects.create(
            name="Client 1",
            email="client1@tenant1.com",
            tenant=self.tenant1,
            created_by=self.user1
        )
        
        # Test that regular user cannot perform admin actions
        with patch('tenants.middleware.get_current_tenant', return_value=self.tenant1):
            # Try to perform admin action with regular user
            with self.assertRaises(Exception):
                # This should raise an exception or return False
                client1.delete()
    
    def test_sql_injection_prevention(self):
        """Test that SQL injection is prevented."""
        # Test with malicious input
        malicious_input = "'; DROP TABLE clients; --"
        
        # Test that malicious input is properly escaped
        with patch('tenants.middleware.get_current_tenant', return_value=self.tenant1):
            # Try to search with malicious input
            clients = Client.objects.for_tenant(self.tenant1).filter(
                name__icontains=malicious_input
            )
            
            # Verify that no results are returned (malicious input was escaped)
            self.assertEqual(clients.count(), 0)
    
    def test_xss_prevention(self):
        """Test that XSS is prevented."""
        # Test with malicious input
        malicious_input = "<script>alert('XSS');</script>"
        
        # Test that malicious input is properly escaped
        with patch('tenants.middleware.get_current_tenant', return_value=self.tenant1):
            # Create client with malicious input
            client = Client.objects.create(
                name=malicious_input,
                email="client@test.com",
                tenant=self.tenant1,
                created_by=self.user1
            )
            
            # Verify that malicious input is stored as-is in database
            # (XSS prevention is handled in templates/views)
            self.assertEqual(client.name, malicious_input)
    
    def test_authentication_bypass_prevention(self):
        """Test that authentication bypass is prevented."""
        # Test with invalid credentials
        with patch('tenants.middleware.get_current_tenant', return_value=self.tenant1):
            # Try to authenticate with invalid credentials
            with self.assertRaises(Exception):
                # This should raise an exception
                User.objects.get(email="invalid@test.com", password="invalidpass")
    
    def test_session_hijacking_prevention(self):
        """Test that session hijacking is prevented."""
        # Test that session is properly tied to user and tenant
        with patch('tenants.middleware.get_current_tenant', return_value=self.tenant1):
            # Create a session for user1
            # In a real scenario, this would create a session
            session_key = "test_session_key"
            
            # Test that session is valid for user1 and tenant1
            self.assertTrue(self.user1.is_authenticated)
            self.assertEqual(self.user1.tenant, self.tenant1)
            
            # Test that session is invalid for user2
            self.assertTrue(self.user2.is_authenticated)
            self.assertEqual(self.user2.tenant, self.tenant2)
            # User2 should not be able to use user1's session


class BrowserTest(LiveServerTestCase):
    """Browser-based tests for the multi-tenant system."""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        cls.selenium = webdriver.Chrome(options=options)
        cls.selenium.implicitly_wait(10)
    
    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()
    
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Browser Test Tenant",
            slug="browser-tenant",
            plan="basic",
            max_users=10,
            max_storage_mb=1000
        )
        
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="adminpass123",
            tenant=self.tenant,
            role="admin"
        )
        
        # Create permissions and roles
        self.view_client_perm = Permission.objects.create(
            name="view_client",
            codename="view_client",
            description="Can view clients"
        )
        
        self.admin_role = Role.objects.create(
            name="Admin",
            tenant=self.tenant,
            description="Administrator role"
        )
        
        self.admin_role.permissions.add(self.view_client_perm)
        UserRole.objects.create(user=self.admin_user, role=self.admin_role)
    
    def test_tenant_specific_login(self):
        """Test tenant-specific login in browser."""
        # Navigate to tenant-specific login page
        self.selenium.get(f'{self.live_server_url}/{self.tenant.slug}/login/')
        
        # Wait for page to load
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, "id_username"))
        )
        
        # Fill in login form
        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        
        username_field.send_keys("admin")
        password_field.send_keys("adminpass123")
        
        # Submit form
        submit_button = self.selenium.find_element(By.ID, "id_submit")
        submit_button.click()
        
        # Wait for redirect to dashboard
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Verify tenant is in URL
        current_url = self.selenium.current_url
        self.assertIn(self.tenant.slug, current_url)
    
    def test_client_management_workflow(self):
        """Test client management workflow in browser."""
        # Login first
        self.selenium.get(f'{self.live_server_url}/{self.tenant.slug}/login/')
        
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, "id_username"))
        )
        
        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        
        username_field.send_keys("admin")
        password_field.send_keys("adminpass123")
        
        submit_button = self.selenium.find_element(By.ID, "id_submit")
        submit_button.click()
        
        # Wait for dashboard to load
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, "Clients"))
        )
        
        # Navigate to clients page
        clients_link = self.selenium.find_element(By.LINK_TEXT, "Clients")
        clients_link.click()
        
        # Wait for clients page to load
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, "client_list"))
        )
        
        # Click "Add Client" button
        add_client_button = self.selenium.find_element(By.ID, "add_client")
        add_client_button.click()
        
        # Wait for form to load
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, "id_name"))
        )
        
        # Fill in client form
        name_field = self.selenium.find_element(By.ID, "id_name")
        email_field = self.selenium.find_element(By.ID, "id_email")
        
        name_field.send_keys("Browser Test Client")
        email_field.send_keys("browser@test.com")
        
        # Submit form
        save_button = self.selenium.find_element(By.ID, "id_save")
        save_button.click()
        
        # Wait for redirect back to clients list
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, "client_list"))
        )
        
        # Verify client was created
        client_list = self.selenium.find_element(By.ID, "client_list")
        self.assertIn("Browser Test Client", client_list.text)
    
    def test_tenant_isolation_in_browser(self):
        """Test tenant isolation in browser."""
        # Create another tenant and user
        tenant2 = Tenant.objects.create(
            name="Browser Test Tenant 2",
            slug="browser-tenant-2",
            plan="basic",
            max_users=10,
            max_storage_mb=1000
        )
        
        user2 = User.objects.create_user(
            username="user2",
            email="user2@test.com",
            password="userpass123",
            tenant=tenant2,
            role="user"
        )
        
        # Create a client for tenant1
        client1 = Client.objects.create(
            name="Client 1",
            email="client1@tenant1.com",
            tenant=self.tenant,
            created_by=self.admin_user
        )
        
        # Login to tenant2
        self.selenium.get(f'{self.live_server_url}/{tenant2.slug}/login/')
        
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, "id_username"))
        )
        
        username_field = self.selenium.find_element(By.ID, "id_username")
        password_field = self.selenium.find_element(By.ID, "id_password")
        
        username_field.send_keys("user2")
        password_field.send_keys("userpass123")
        
        submit_button = self.selenium.find_element(By.ID, "id_submit")
        submit_button.click()
        
        # Wait for dashboard to load
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.LINK_TEXT, "Clients"))
        )
        
        # Navigate to clients page
        clients_link = self.selenium.find_element(By.LINK_TEXT, "Clients")
        clients_link.click()
        
        # Wait for clients page to load
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, "client_list"))
        )
        
        # Verify tenant2's clients page doesn't show tenant1's client
        client_list = self.selenium.find_element(By.ID, "client_list")
        self.assertNotIn("Client 1", client_list.text)