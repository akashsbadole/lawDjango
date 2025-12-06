"""
Test fixtures for the multi-tenant lawyer management system.

This module provides factory functions and helper utilities to create
test data for various components of the system.
"""

import os
import json
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

from tenants.models import Tenant, TenantSettings
from accounts.models import CustomUser
from permissions.models import Permission, Role, UserRole
from clients.models import Client
from cases.models import Case, CaseEvent
from documents.models import Document, DocumentVersion
from billing.models import Invoice, Payment, TimeEntry, BillingRate
from subscriptions.models import SubscriptionPlan, TenantSubscription
from audit.models import AuditLog
from backup_restore.models import BackupJob, RestoreJob, BackupSchedule
from platform_admin.models import SystemSettings, AdminNote, SystemAnnouncement

User = get_user_model()


def create_test_tenant(**kwargs):
    """
    Create a test tenant with default values.
    
    Args:
        **kwargs: Additional fields to override defaults
        
    Returns:
        Tenant: Created tenant instance
    """
    defaults = {
        'name': 'Test Tenant',
        'slug': 'test-tenant',
        'plan': 'basic',
        'max_users': 10,
        'max_storage_mb': 1000,
        'is_active': True,
        'trial_ends_at': timezone.now() + timedelta(days=14)
    }
    defaults.update(kwargs)
    return Tenant.objects.create(**defaults)


def create_test_tenant_settings(tenant, **kwargs):
    """
    Create test tenant settings with default values.
    
    Args:
        tenant: Tenant instance
        **kwargs: Additional fields to override defaults
        
    Returns:
        TenantSettings: Created tenant settings instance
    """
    defaults = {
        'tenant': tenant,
        'date_format': 'YYYY-MM-DD',
        'time_format': '24-hour',
        'timezone': 'UTC',
        'default_currency': 'USD',
        'tax_rate': Decimal('0.00'),
        'invoice_prefix': 'INV-',
        'payment_terms': 'Net 30',
        'email_notifications': True,
        'sms_notifications': False,
        'in_app_notifications': True,
        'password_policy': 'medium',
        'two_factor_required': False,
        'session_timeout': 60
    }
    defaults.update(kwargs)
    return TenantSettings.objects.create(**defaults)


def create_test_user(tenant, **kwargs):
    """
    Create a test user with default values.
    
    Args:
        tenant: Tenant instance
        **kwargs: Additional fields to override defaults
        
    Returns:
        CustomUser: Created user instance
    """
    defaults = {
        'username': 'testuser',
        'email': 'test@example.com',
        'first_name': 'Test',
        'last_name': 'User',
        'password': 'testpass123',
        'tenant': tenant,
        'role': 'user',
        'is_active': True,
        'is_staff': False,
        'is_superuser': False
    }
    defaults.update(kwargs)
    return CustomUser.objects.create_user(**defaults)


def create_test_admin_user(tenant, **kwargs):
    """
    Create a test admin user with default values.
    
    Args:
        tenant: Tenant instance
        **kwargs: Additional fields to override defaults
        
    Returns:
        CustomUser: Created admin user instance
    """
    defaults = {
        'username': 'testadmin',
        'email': 'admin@example.com',
        'first_name': 'Test',
        'last_name': 'Admin',
        'password': 'adminpass123',
        'tenant': tenant,
        'role': 'admin',
        'is_active': True,
        'is_staff': True,
        'is_superuser': False
    }
    defaults.update(kwargs)
    return CustomUser.objects.create_user(**defaults)


def create_test_superuser(**kwargs):
    """
    Create a test superuser with default values.
    
    Args:
        **kwargs: Additional fields to override defaults
        
    Returns:
        CustomUser: Created superuser instance
    """
    defaults = {
        'username': 'superuser',
        'email': 'super@example.com',
        'first_name': 'Super',
        'last_name': 'User',
        'password': 'superpass123',
        'role': 'admin',
        'is_active': True,
        'is_staff': True,
        'is_superuser': True
    }
    defaults.update(kwargs)
    return CustomUser.objects.create_user(**defaults)


def create_test_permission(**kwargs):
    """
    Create a test permission with default values.
    
    Args:
        **kwargs: Additional fields to override defaults
        
    Returns:
        Permission: Created permission instance
    """
    defaults = {
        'name': 'Test Permission',
        'codename': 'test_permission',
        'description': 'Test permission description'
    }
    defaults.update(kwargs)
    return Permission.objects.create(**defaults)


def create_test_role(tenant, **kwargs):
    """
    Create a test role with default values.
    
    Args:
        tenant: Tenant instance
        **kwargs: Additional fields to override defaults
        
    Returns:
        Role: Created role instance
    """
    defaults = {
        'name': 'Test Role',
        'tenant': tenant,
        'description': 'Test role description'
    }
    defaults.update(kwargs)
    return Role.objects.create(**defaults)


def create_test_user_role(user, role, **kwargs):
    """
    Create a test user role assignment.
    
    Args:
        user: CustomUser instance
        role: Role instance
        **kwargs: Additional fields to override defaults
        
    Returns:
        UserRole: Created user role instance
    """
    defaults = {
        'user': user,
        'role': role
    }
    defaults.update(kwargs)
    return UserRole.objects.create(**defaults)


def create_test_client(tenant, created_by, **kwargs):
    """
    Create a test client with default values.
    
    Args:
        tenant: Tenant instance
        created_by: User instance who created the client
        **kwargs: Additional fields to override defaults
        
    Returns:
        Client: Created client instance
    """
    defaults = {
        'name': 'Test Client',
        'email': 'client@example.com',
        'phone': '555-123-4567',
        'address': '123 Test St',
        'city': 'Test City',
        'state': 'TS',
        'zip_code': '12345',
        'country': 'Test Country',
        'website': 'https://example.com',
        'notes': 'Test notes',
        'tenant': tenant,
        'created_by': created_by
    }
    defaults.update(kwargs)
    return Client.objects.create(**defaults)


def create_test_case(tenant, client, created_by, **kwargs):
    """
    Create a test case with default values.
    
    Args:
        tenant: Tenant instance
        client: Client instance
        created_by: User instance who created the case
        **kwargs: Additional fields to override defaults
        
    Returns:
        Case: Created case instance
    """
    defaults = {
        'title': 'Test Case',
        'description': 'Test case description',
        'case_number': 'CASE-001',
        'status': 'open',
        'priority': 'medium',
        'client': client,
        'tenant': tenant,
        'created_by': created_by
    }
    defaults.update(kwargs)
    return Case.objects.create(**defaults)


def create_test_case_event(case, created_by, **kwargs):
    """
    Create a test case event with default values.
    
    Args:
        case: Case instance
        created_by: User instance who created the event
        **kwargs: Additional fields to override defaults
        
    Returns:
        CaseEvent: Created case event instance
    """
    defaults = {
        'case': case,
        'event_type': 'note',
        'description': 'Test case event',
        'tenant': case.tenant,
        'created_by': created_by
    }
    defaults.update(kwargs)
    return CaseEvent.objects.create(**defaults)


def create_test_document(tenant, created_by, **kwargs):
    """
    Create a test document with default values.
    
    Args:
        tenant: Tenant instance
        created_by: User instance who created the document
        **kwargs: Additional fields to override defaults
        
    Returns:
        Document: Created document instance
    """
    defaults = {
        'title': 'Test Document',
        'description': 'Test document description',
        'category': 'legal',
        'tenant': tenant,
        'created_by': created_by
    }
    defaults.update(kwargs)
    return Document.objects.create(**defaults)


def create_test_document_file():
    """
    Create a test document file for upload.
    
    Returns:
        SimpleUploadedFile: Test document file
    """
    content = b"Test document content"
    return SimpleUploadedFile(
        "test_document.txt",
        content,
        content_type="text/plain"
    )


def create_test_document_version(document, created_by, **kwargs):
    """
    Create a test document version with default values.
    
    Args:
        document: Document instance
        created_by: User instance who created the version
        **kwargs: Additional fields to override defaults
        
    Returns:
        DocumentVersion: Created document version instance
    """
    defaults = {
        'document': document,
        'version_number': '1.0',
        'change_description': 'Initial version',
        'tenant': document.tenant,
        'created_by': created_by
    }
    defaults.update(kwargs)
    return DocumentVersion.objects.create(**defaults)


def create_test_invoice(tenant, client, created_by, **kwargs):
    """
    Create a test invoice with default values.
    
    Args:
        tenant: Tenant instance
        client: Client instance
        created_by: User instance who created the invoice
        **kwargs: Additional fields to override defaults
        
    Returns:
        Invoice: Created invoice instance
    """
    defaults = {
        'invoice_number': 'INV-001',
        'client': client,
        'amount': Decimal('1000.00'),
        'due_date': timezone.now() + timedelta(days=30),
        'status': 'draft',
        'tenant': tenant,
        'created_by': created_by
    }
    defaults.update(kwargs)
    return Invoice.objects.create(**defaults)


def create_test_payment(invoice, created_by, **kwargs):
    """
    Create a test payment with default values.
    
    Args:
        invoice: Invoice instance
        created_by: User instance who created the payment
        **kwargs: Additional fields to override defaults
        
    Returns:
        Payment: Created payment instance
    """
    defaults = {
        'invoice': invoice,
        'amount': invoice.amount,
        'payment_date': timezone.now(),
        'status': 'completed',
        'method': 'credit_card',
        'tenant': invoice.tenant,
        'created_by': created_by
    }
    defaults.update(kwargs)
    return Payment.objects.create(**defaults)


def create_test_time_entry(invoice, created_by, **kwargs):
    """
    Create a test time entry with default values.
    
    Args:
        invoice: Invoice instance
        created_by: User instance who created the time entry
        **kwargs: Additional fields to override defaults
        
    Returns:
        TimeEntry: Created time entry instance
    """
    defaults = {
        'invoice': invoice,
        'date': timezone.now().date(),
        'hours': Decimal('2.5'),
        'description': 'Test time entry',
        'rate': Decimal('100.00'),
        'tenant': invoice.tenant,
        'created_by': created_by
    }
    defaults.update(kwargs)
    return TimeEntry.objects.create(**defaults)


def create_test_billing_rate(tenant, **kwargs):
    """
    Create a test billing rate with default values.
    
    Args:
        tenant: Tenant instance
        **kwargs: Additional fields to override defaults
        
    Returns:
        BillingRate: Created billing rate instance
    """
    defaults = {
        'name': 'Standard Rate',
        'description': 'Standard hourly rate',
        'rate': Decimal('100.00'),
        'activity_type': 'legal_work',
        'tenant': tenant
    }
    defaults.update(kwargs)
    return BillingRate.objects.create(**defaults)


def create_test_subscription_plan(**kwargs):
    """
    Create a test subscription plan with default values.
    
    Args:
        **kwargs: Additional fields to override defaults
        
    Returns:
        SubscriptionPlan: Created subscription plan instance
    """
    defaults = {
        'name': 'Basic Plan',
        'code': 'basic',
        'description': 'Basic subscription plan',
        'price': Decimal('29.99'),
        'billing_cycle': 'monthly',
        'max_users': 10,
        'max_storage_mb': 1000,
        'features': json.dumps(['cases', 'documents', 'billing'])
    }
    defaults.update(kwargs)
    return SubscriptionPlan.objects.create(**defaults)


def create_test_tenant_subscription(tenant, plan, **kwargs):
    """
    Create a test tenant subscription with default values.
    
    Args:
        tenant: Tenant instance
        plan: SubscriptionPlan instance
        **kwargs: Additional fields to override defaults
        
    Returns:
        TenantSubscription: Created tenant subscription instance
    """
    defaults = {
        'tenant': tenant,
        'plan': plan,
        'status': 'active',
        'start_date': timezone.now(),
        'auto_renew': True
    }
    defaults.update(kwargs)
    return TenantSubscription.objects.create(**defaults)


def create_test_audit_log(tenant, user, **kwargs):
    """
    Create a test audit log with default values.
    
    Args:
        tenant: Tenant instance
        user: User instance who performed the action
        **kwargs: Additional fields to override defaults
        
    Returns:
        AuditLog: Created audit log instance
    """
    defaults = {
        'tenant': tenant,
        'user': user,
        'activity_type': 'CLIENT_CREATED',
        'description': 'Created test client',
        'ip_address': '192.168.1.1'
    }
    defaults.update(kwargs)
    return AuditLog.objects.create(**defaults)


def create_test_backup_job(tenant, created_by, **kwargs):
    """
    Create a test backup job with default values.
    
    Args:
        tenant: Tenant instance
        created_by: User instance who created the backup job
        **kwargs: Additional fields to override defaults
        
    Returns:
        BackupJob: Created backup job instance
    """
    defaults = {
        'name': 'Test Backup',
        'description': 'Test backup description',
        'backup_type': 'full',
        'include_database': True,
        'include_media': True,
        'include_documents': True,
        'include_settings': True,
        'tenant': tenant,
        'created_by': created_by
    }
    defaults.update(kwargs)
    return BackupJob.objects.create(**defaults)


def create_test_restore_job(tenant, created_by, **kwargs):
    """
    Create a test restore job with default values.
    
    Args:
        tenant: Tenant instance
        created_by: User instance who created the restore job
        **kwargs: Additional fields to override defaults
        
    Returns:
        RestoreJob: Created restore job instance
    """
    defaults = {
        'name': 'Test Restore',
        'description': 'Test restore description',
        'restore_database': True,
        'restore_media': True,
        'restore_documents': True,
        'restore_settings': True,
        'conflict_resolution': 'overwrite',
        'tenant': tenant,
        'created_by': created_by
    }
    defaults.update(kwargs)
    return RestoreJob.objects.create(**defaults)


def create_test_backup_schedule(tenant, created_by, **kwargs):
    """
    Create a test backup schedule with default values.
    
    Args:
        tenant: Tenant instance
        created_by: User instance who created the backup schedule
        **kwargs: Additional fields to override defaults
        
    Returns:
        BackupSchedule: Created backup schedule instance
    """
    defaults = {
        'name': 'Daily Backup',
        'description': 'Daily backup schedule',
        'frequency': 'daily',
        'backup_type': 'full',
        'is_active': True,
        'run_at': timezone.now().time().replace(hour=2, minute=0),
        'include_database': True,
        'include_media': True,
        'include_documents': True,
        'include_settings': True,
        'compress': True,
        'encrypt': True,
        'retention_days': 30,
        'tenant': tenant,
        'created_by': created_by
    }
    defaults.update(kwargs)
    return BackupSchedule.objects.create(**defaults)


def create_test_system_settings(**kwargs):
    """
    Create test system settings with default values.
    
    Args:
        **kwargs: Additional fields to override defaults
        
    Returns:
        SystemSettings: Created system settings instance
    """
    defaults = {
        'platform_name': 'Test Platform',
        'platform_version': '1.0.0',
        'support_email': 'support@example.com',
        'support_phone': '555-123-4567',
        'allow_public_registration': True,
        'require_admin_approval': False,
        'default_trial_days': 14,
        'max_tenants': 100,
        'max_users_per_tenant': 50,
        'enforce_2fa_for_admins': False,
        'session_timeout_minutes': 60,
        'auto_backup_enabled': True,
        'backup_retention_days': 30,
        'system_alerts_enabled': True,
        'email_notifications_enabled': True,
        'maintenance_mode': False
    }
    defaults.update(kwargs)
    return SystemSettings.objects.create(**defaults)


def create_test_admin_note(tenant, admin_user, **kwargs):
    """
    Create a test admin note with default values.
    
    Args:
        tenant: Tenant instance
        admin_user: User instance who created the note
        **kwargs: Additional fields to override defaults
        
    Returns:
        AdminNote: Created admin note instance
    """
    defaults = {
        'tenant': tenant,
        'admin_user': admin_user,
        'note_type': 'general',
        'title': 'Test Note',
        'content': 'Test note content',
        'is_private': False,
        'is_resolved': False,
        'requires_follow_up': False
    }
    defaults.update(kwargs)
    return AdminNote.objects.create(**defaults)


def create_test_system_announcement(created_by, **kwargs):
    """
    Create a test system announcement with default values.
    
    Args:
        created_by: User instance who created the announcement
        **kwargs: Additional fields to override defaults
        
    Returns:
        SystemAnnouncement: Created system announcement instance
    """
    defaults = {
        'title': 'Test Announcement',
        'content': 'Test announcement content',
        'announcement_type': 'info',
        'target_all_tenants': True,
        'is_active': True,
        'start_date': timezone.now(),
        'show_on_login': True,
        'show_on_dashboard': True,
        'show_as_banner': False,
        'is_dismissible': True,
        'priority': 50,
        'created_by': created_by
    }
    defaults.update(kwargs)
    return SystemAnnouncement.objects.create(**defaults)


def create_sample_tenant_data():
    """
    Create a complete sample tenant with all related data.
    
    Returns:
        dict: Dictionary containing all created instances
    """
    with transaction.atomic():
        # Create tenant
        tenant = create_test_tenant(
            name='Sample Tenant',
            slug='sample-tenant',
            plan='premium'
        )
        
        # Create tenant settings
        settings = create_test_tenant_settings(tenant)
        
        # Create users
        admin_user = create_test_admin_user(
            tenant,
            username='sampleadmin',
            email='admin@sample.com'
        )
        regular_user = create_test_user(
            tenant,
            username='sampleuser',
            email='user@sample.com'
        )
        
        # Create permissions and roles
        view_perm = create_test_permission(
            name='View Client',
            codename='view_client'
        )
        edit_perm = create_test_permission(
            name='Edit Client',
            codename='edit_client'
        )
        
        admin_role = create_test_role(
            tenant,
            name='Administrator'
        )
        user_role = create_test_role(
            tenant,
            name='Regular User'
        )
        
        # Assign permissions to roles
        admin_role.permissions.add(view_perm, edit_perm)
        user_role.permissions.add(view_perm)
        
        # Assign roles to users
        create_test_user_role(admin_user, admin_role)
        create_test_user_role(regular_user, user_role)
        
        # Create clients
        client1 = create_test_client(
            tenant,
            admin_user,
            name='Sample Client 1',
            email='client1@sample.com'
        )
        client2 = create_test_client(
            tenant,
            admin_user,
            name='Sample Client 2',
            email='client2@sample.com'
        )
        
        # Create cases
        case1 = create_test_case(
            tenant,
            client1,
            admin_user,
            title='Sample Case 1',
            status='open'
        )
        case2 = create_test_case(
            tenant,
            client2,
            admin_user,
            title='Sample Case 2',
            status='in_progress'
        )
        
        # Create case events
        create_test_case_event(
            case1,
            admin_user,
            description='Initial consultation'
        )
        create_test_case_event(
            case2,
            regular_user,
            description='Document review'
        )
        
        # Create documents
        doc1 = create_test_document(
            tenant,
            admin_user,
            title='Sample Document 1',
            category='contract'
        )
        doc2 = create_test_document(
            tenant,
            regular_user,
            title='Sample Document 2',
            category='evidence'
        )
        
        # Create document versions
        create_test_document_version(
            doc1,
            admin_user,
            version_number='1.0',
            change_description='Initial version'
        )
        create_test_document_version(
            doc1,
            admin_user,
            version_number='1.1',
            change_description='Added signature page'
        )
        
        # Create billing data
        plan = create_test_subscription_plan(
            name='Premium Plan',
            code='premium',
            price=99.99
        )
        
        subscription = create_test_tenant_subscription(
            tenant,
            plan,
            status='active'
        )
        
        invoice1 = create_test_invoice(
            tenant,
            client1,
            admin_user,
            amount=5000.00
        )
        invoice2 = create_test_invoice(
            tenant,
            client2,
            admin_user,
            amount=3000.00
        )
        
        payment1 = create_test_payment(invoice1, admin_user)
        payment2 = create_test_payment(invoice2, admin_user)
        
        time_entry1 = create_test_time_entry(invoice1, admin_user, hours=10)
        time_entry2 = create_test_time_entry(invoice1, admin_user, hours=15)
        time_entry3 = create_test_time_entry(invoice2, admin_user, hours=8)
        
        # Create audit logs
        create_test_audit_log(
            tenant,
            admin_user,
            activity_type='CLIENT_CREATED'
        )
        create_test_audit_log(
            tenant,
            regular_user,
            activity_type='DOCUMENT_CREATED'
        )
        
        # Create backup jobs
        backup1 = create_test_backup_job(
            tenant,
            admin_user,
            name='Daily Backup'
        )
        backup2 = create_test_backup_job(
            tenant,
            admin_user,
            backup_type='incremental',
            parent_backup=backup1
        )
        
        # Create restore job
        restore1 = create_test_restore_job(
            tenant,
            admin_user,
            backup_job=backup1
        )
        
        # Create backup schedule
        schedule = create_test_backup_schedule(
            tenant,
            admin_user,
            frequency='daily'
        )
        
        # Create system settings
        system_settings = create_test_system_settings(
            platform_name='Sample Platform'
        )
        
        # Create admin notes
        note1 = create_test_admin_note(
            tenant,
            admin_user,
            title='Sample Note 1',
            note_type='general'
        )
        note2 = create_test_admin_note(
            tenant,
            admin_user,
            title='Sample Note 2',
            note_type='warning'
        )
        
        # Create system announcement
        announcement = create_test_system_announcement(
            admin_user,
            title='Sample Announcement'
        )
        
        return {
            'tenant': tenant,
            'settings': settings,
            'admin_user': admin_user,
            'regular_user': regular_user,
            'view_perm': view_perm,
            'edit_perm': edit_perm,
            'admin_role': admin_role,
            'user_role': user_role,
            'clients': [client1, client2],
            'cases': [case1, case2],
            'documents': [doc1, doc2],
            'plan': plan,
            'subscription': subscription,
            'invoices': [invoice1, invoice2],
            'payments': [payment1, payment2],
            'time_entries': [time_entry1, time_entry2, time_entry3],
            'audit_logs': [note1, note2],
            'backup_jobs': [backup1, backup2],
            'restore_job': restore1,
            'backup_schedule': schedule,
            'system_settings': system_settings,
            'announcement': announcement
        }


def create_multi_tenant_scenario():
    """
    Create a multi-tenant scenario with multiple tenants and data.
    
    Returns:
        dict: Dictionary containing all created instances
    """
    with transaction.atomic():
        # Create multiple tenants
        tenant1 = create_test_tenant(
            name='Multi Tenant 1',
            slug='multi-tenant-1',
            plan='basic'
        )
        tenant2 = create_test_tenant(
            name='Multi Tenant 2',
            slug='multi-tenant-2',
            plan='premium'
        )
        
        # Create users for each tenant
        admin1 = create_test_admin_user(
            tenant1,
            username='multiadmin1',
            email='admin1@multi1.com'
        )
        user1 = create_test_user(
            tenant1,
            username='multiuser1',
            email='user1@multi1.com'
        )
        
        admin2 = create_test_admin_user(
            tenant2,
            username='multiadmin2',
            email='admin2@multi2.com'
        )
        user2 = create_test_user(
            tenant2,
            username='multiuser2',
            email='user2@multi2.com'
        )
        
        # Create clients for each tenant
        client1 = create_test_client(
            tenant1,
            admin1,
            name='Multi Client 1',
            email='client1@multi1.com'
        )
        client2 = create_test_client(
            tenant2,
            admin2,
            name='Multi Client 2',
            email='client2@multi2.com'
        )
        
        # Create cases for each tenant
        case1 = create_test_case(
            tenant1,
            client1,
            admin1,
            title='Multi Case 1'
        )
        case2 = create_test_case(
            tenant2,
            client2,
            admin2,
            title='Multi Case 2'
        )
        
        # Create documents for each tenant
        doc1 = create_test_document(
            tenant1,
            admin1,
            title='Multi Document 1'
        )
        doc2 = create_test_document(
            tenant2,
            admin2,
            title='Multi Document 2'
        )
        
        # Create audit logs for each tenant
        audit1 = create_test_audit_log(
            tenant1,
            admin1,
            activity_type='CLIENT_CREATED'
        )
        audit2 = create_test_audit_log(
            tenant2,
            admin2,
            activity_type='CLIENT_CREATED'
        )
        
        # Create backup jobs for each tenant
        backup1 = create_test_backup_job(
            tenant1,
            admin1,
            name='Multi Backup 1'
        )
        backup2 = create_test_backup_job(
            tenant2,
            admin2,
            name='Multi Backup 2'
        )
        
        return {
            'tenant1': tenant1,
            'tenant2': tenant2,
            'admin1': admin1,
            'user1': user1,
            'admin2': admin2,
            'user2': user2,
            'client1': client1,
            'client2': client2,
            'case1': case1,
            'case2': case2,
            'doc1': doc1,
            'doc2': doc2,
            'audit1': audit1,
            'audit2': audit2,
            'backup1': backup1,
            'backup2': backup2
        }


def create_performance_test_data(tenant, user, num_records=100):
    """
    Create a large dataset for performance testing.
    
    Args:
        tenant: Tenant instance
        user: User instance
        num_records: Number of records to create
        
    Returns:
        dict: Dictionary containing created instances
    """
    with transaction.atomic():
        # Create many clients
        clients = []
        for i in range(num_records):
            client = create_test_client(
                tenant,
                user,
                name=f'Perf Client {i}',
                email=f'perfclient{i}@test.com'
            )
            clients.append(client)
        
        # Create many cases
        cases = []
        for i in range(num_records):
            client = clients[i % len(clients)]
            case = create_test_case(
                tenant,
                user,
                client,
                title=f'Perf Case {i}',
                case_number=f'CASE-{i:04d}'
            )
            cases.append(case)
        
        # Create many documents
        documents = []
        for i in range(num_records):
            doc = create_test_document(
                tenant,
                user,
                title=f'Perf Document {i}',
                category=f'category{i % 5}'
            )
            documents.append(doc)
        
        # Create many audit logs
        audit_logs = []
        for i in range(num_records):
            audit = create_test_audit_log(
                tenant,
                user,
                activity_type=f'PERF_TEST_{i}',
                description=f'Performance test {i}'
            )
            audit_logs.append(audit)
        
        return {
            'clients': clients,
            'cases': cases,
            'documents': documents,
            'audit_logs': audit_logs
        }


def create_security_test_data():
    """
    Create data for security testing.
    
    Returns:
        dict: Dictionary containing created instances
    """
    with transaction.atomic():
        # Create tenant
        tenant = create_test_tenant(
            name='Security Test Tenant',
            slug='security-tenant'
        )
        
        # Create users with different roles
        admin_user = create_test_admin_user(
            tenant,
            username='secadmin',
            email='admin@security.com'
        )
        regular_user = create_test_user(
            tenant,
            username='secuser',
            email='user@security.com'
        )
        
        # Create permissions
        view_perm = create_test_permission(
            name='View Sensitive',
            codename='view_sensitive'
        )
        edit_perm = create_test_permission(
            name='Edit Sensitive',
            codename='edit_sensitive'
        )
        
        # Create roles
        admin_role = create_test_role(
            tenant,
            name='Security Admin'
        )
        user_role = create_test_role(
            tenant,
            name='Security User'
        )
        
        # Assign permissions to roles
        admin_role.permissions.add(view_perm, edit_perm)
        user_role.permissions.add(view_perm)
        
        # Assign roles to users
        create_test_user_role(admin_user, admin_role)
        create_test_user_role(regular_user, user_role)
        
        # Create sensitive client
        client = create_test_client(
            tenant,
            admin_user,
            name='Sensitive Client',
            email='sensitive@security.com'
        )
        
        # Create sensitive case
        case = create_test_case(
            tenant,
            client,
            admin_user,
            title='Sensitive Case',
            description='Confidential information'
        )
        
        # Create sensitive document
        document = create_test_document(
            tenant,
            admin_user,
            title='Sensitive Document',
            category='confidential'
        )
        
        return {
            'tenant': tenant,
            'admin_user': admin_user,
            'regular_user': regular_user,
            'view_perm': view_perm,
            'edit_perm': edit_perm,
            'admin_role': admin_role,
            'user_role': user_role,
            'client': client,
            'case': case,
            'document': document
        }


def create_test_data_for_module(module_name, tenant=None, user=None):
    """
    Create test data for a specific module.
    
    Args:
        module_name: Name of the module ('tenants', 'users', 'clients', etc.)
        tenant: Tenant instance (optional)
        user: User instance (optional)
        
    Returns:
        dict: Dictionary containing created instances
    """
    # Create default tenant and user if not provided
    if tenant is None:
        tenant = create_test_tenant()
    
    if user is None:
        user = create_test_admin_user(tenant)
    
    data = {
        'tenant': tenant,
        'user': user
    }
    
    if module_name == 'tenants':
        data['settings'] = create_test_tenant_settings(tenant)
    
    elif module_name == 'users':
        # Create additional users
        regular_user = create_test_user(tenant)
        data['regular_user'] = regular_user
        
        # Create permissions and roles
        view_perm = create_test_permission(codename='view_client')
        edit_perm = create_test_permission(codename='edit_client')
        
        admin_role = create_test_role(tenant, name='Admin')
        user_role = create_test_role(tenant, name='User')
        
        admin_role.permissions.add(view_perm, edit_perm)
        user_role.permissions.add(view_perm)
        
        create_test_user_role(user, admin_role)
        create_test_user_role(regular_user, user_role)
        
        data['view_perm'] = view_perm
        data['edit_perm'] = edit_perm
        data['admin_role'] = admin_role
        data['user_role'] = user_role
    
    elif module_name == 'clients':
        client = create_test_client(tenant, user)
        data['client'] = client
        
        # Create multiple clients for list testing
        data['clients'] = [
            create_test_client(tenant, user, name=f'Client {i}')
            for i in range(5)
        ]
    
    elif module_name == 'cases':
        client = create_test_client(tenant, user)
        case = create_test_case(tenant, client, user)
        data['case'] = case
        data['client'] = client
        
        # Create multiple cases for list testing
        data['cases'] = [
            create_test_case(tenant, client, user, title=f'Case {i}')
            for i in range(5)
        ]
    
    elif module_name == 'documents':
        document = create_test_document(tenant, user)
        data['document'] = document
        
        # Create multiple documents for list testing
        data['documents'] = [
            create_test_document(tenant, user, title=f'Document {i}')
            for i in range(5)
        ]
    
    elif module_name == 'billing':
        client = create_test_client(tenant, user)
        invoice = create_test_invoice(tenant, client, user)
        payment = create_test_payment(invoice, user)
        time_entry = create_test_time_entry(invoice, user)
        billing_rate = create_test_billing_rate(tenant)
        
        data['client'] = client
        data['invoice'] = invoice
        data['payment'] = payment
        data['time_entry'] = time_entry
        data['billing_rate'] = billing_rate
        
        # Create multiple invoices for list testing
        data['invoices'] = [
            create_test_invoice(tenant, client, user, invoice_number=f'INV-{i:04d}')
            for i in range(5)
        ]
    
    elif module_name == 'subscriptions':
        plan = create_test_subscription_plan()
        subscription = create_test_tenant_subscription(tenant, plan)
        
        data['plan'] = plan
        data['subscription'] = subscription
        
        # Create multiple plans for list testing
        data['plans'] = [
            create_test_subscription_plan(name=f'Plan {i}', code=f'plan{i}')
            for i in range(3)
        ]
    
    elif module_name == 'audit':
        client = create_test_client(tenant, user)
        audit_log = create_test_audit_log(tenant, user)
        
        data['client'] = client
        data['audit_log'] = audit_log
        
        # Create multiple audit logs for list testing
        data['audit_logs'] = [
            create_test_audit_log(tenant, user, activity_type=f'TEST_{i}')
            for i in range(10)
        ]
    
    elif module_name == 'backup_restore':
        backup_job = create_test_backup_job(tenant, user)
        restore_job = create_test_restore_job(tenant, user)
        backup_schedule = create_test_backup_schedule(tenant, user)
        
        data['backup_job'] = backup_job
        data['restore_job'] = restore_job
        data['backup_schedule'] = backup_schedule
        
        # Create multiple backup jobs for list testing
        data['backup_jobs'] = [
            create_test_backup_job(tenant, user, name=f'Backup {i}')
            for i in range(3)
        ]
    
    elif module_name == 'platform_admin':
        system_settings = create_test_system_settings()
        admin_note = create_test_admin_note(tenant, user)
        system_announcement = create_test_system_announcement(user)
        
        data['system_settings'] = system_settings
        data['admin_note'] = admin_note
        data['system_announcement'] = system_announcement
        
        # Create multiple admin notes for list testing
        data['admin_notes'] = [
            create_test_admin_note(tenant, user, title=f'Note {i}')
            for i in range(5)
        ]
    
    return data