import os
import json
import tempfile
import shutil
import zipfile
import tarfile
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from django.test import TestCase, TransactionTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import transaction
try:
    from rest_framework.test import APITestCase
    HAS_REST_FRAMEWORK = True
except ImportError:
    # Fallback for when Django REST framework is not available
    from django.test import TestCase as APITestCase
    HAS_REST_FRAMEWORK = False

from tenants.models import Tenant, TenantSettings
from backup_restore.models import BackupJob, RestoreJob, BackupSchedule
from backup_restore.managers import BackupJobManager, RestoreJobManager, BackupScheduleManager
from backup_restore.utils import BackupUtility, RestoreUtility, verify_backup_integrity, cleanup_old_backups
from backup_restore.views import (
    BackupJobListView, BackupJobDetailView, BackupJobCreateView,
    RestoreJobListView, RestoreJobDetailView, RestoreJobCreateView,
    BackupScheduleListView, BackupScheduleDetailView, BackupScheduleCreateView
)

User = get_user_model()


class BackupJobModelTest(TestCase):
    """Test cases for the BackupJob model."""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10,
            max_storage_mb=1000
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.backup_job = BackupJob.objects.create(
            name="Test Backup",
            description="Test backup description",
            backup_type="full",
            tenant=self.tenant,
            created_by=self.user
        )
    
    def test_backup_job_creation(self):
        """Test creating a backup job."""
        self.assertEqual(self.backup_job.name, "Test Backup")
        self.assertEqual(self.backup_job.backup_type, "full")
        self.assertEqual(self.backup_job.status, "pending")
        self.assertEqual(self.backup_job.tenant, self.tenant)
        self.assertEqual(self.backup_job.created_by, self.user)
        self.assertTrue(self.backup_job.include_database)
        self.assertTrue(self.backup_job.include_media)
        self.assertTrue(self.backup_job.include_documents)
        self.assertTrue(self.backup_job.include_settings)
    
    def test_backup_job_str_representation(self):
        """Test the string representation of a backup job."""
        self.assertEqual(str(self.backup_job), "Test Backup (Test Tenant)")
    
    def test_backup_job_properties(self):
        """Test backup job properties."""
        # Test is_running property
        self.backup_job.status = "running"
        self.backup_job.save()
        self.assertTrue(self.backup_job.is_running)
        
        # Test is_completed property
        self.backup_job.status = "completed"
        self.backup_job.save()
        self.assertTrue(self.backup_job.is_completed)
        
        # Test is_failed property
        self.backup_job.status = "failed"
        self.backup_job.save()
        self.assertTrue(self.backup_job.is_failed)
        
        # Test file_size_mb property
        self.backup_job.file_size = 1048576  # 1 MB in bytes
        self.backup_job.save()
        self.assertEqual(self.backup_job.file_size_mb, 1.0)
    
    def test_backup_job_status_transitions(self):
        """Test backup job status transitions."""
        # Test start_backup
        self.backup_job.start_backup()
        self.assertEqual(self.backup_job.status, "running")
        self.assertIsNotNone(self.backup_job.started_at)
        
        # Test complete_backup
        self.backup_job.complete_backup("/path/to/backup.tar.gz", 1048576)
        self.assertEqual(self.backup_job.status, "completed")
        self.assertEqual(self.backup_job.file_path, "/path/to/backup.tar.gz")
        self.assertEqual(self.backup_job.file_size, 1048576)
        self.assertEqual(self.backup_job.progress_percentage, 100)
        self.assertIsNotNone(self.backup_job.completed_at)
        
        # Test fail_backup
        self.backup_job.status = "running"
        self.backup_job.fail_backup("Test error message")
        self.assertEqual(self.backup_job.status, "failed")
        self.assertEqual(self.backup_job.error_message, "Test error message")
        self.assertIsNotNone(self.backup_job.completed_at)
        
        # Test cancel_backup
        self.backup_job.status = "running"
        self.backup_job.cancel_backup()
        self.assertEqual(self.backup_job.status, "cancelled")
        self.assertIsNotNone(self.backup_job.completed_at)
    
    def test_backup_job_progress_tracking(self):
        """Test backup job progress tracking."""
        # Test update_progress
        self.backup_job.update_progress(50, "Processing files")
        self.assertEqual(self.backup_job.progress_percentage, 50)
        self.assertEqual(self.backup_job.current_step, "Processing files")
        
        # Test add_log_entry
        self.backup_job.add_log_entry("info", "Test log message")
        self.assertEqual(len(self.backup_job.log_entries), 1)
        self.assertEqual(self.backup_job.log_entries[0]["level"], "info")
        self.assertEqual(self.backup_job.log_entries[0]["message"], "Test log message")
    
    def test_backup_job_encryption_key(self):
        """Test backup job encryption key generation."""
        # Test get_encryption_key when no key exists
        key = self.backup_job.get_encryption_key()
        self.assertIsNotNone(key)
        self.assertEqual(self.backup_job.encryption_key, key.decode())
        
        # Test get_encryption_key when key already exists
        existing_key = self.backup_job.get_encryption_key()
        self.assertEqual(key, existing_key)
    
    def test_backup_job_file_hash_calculation(self):
        """Test backup job file hash calculation."""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file_path = temp_file.name
        
        try:
            # Calculate hash
            hash_value = self.backup_job._calculate_file_hash(temp_file_path)
            self.assertEqual(len(hash_value), 64)  # SHA-256 hash length
            self.backup_job.file_hash = hash_value
            
            # Verify the hash
            with open(temp_file_path, 'rb') as f:
                content = f.read()
                expected_hash = hashlib.sha256(content).hexdigest()
                self.assertEqual(hash_value, expected_hash)
        finally:
            os.unlink(temp_file_path)


class RestoreJobModelTest(TestCase):
    """Test cases for the RestoreJob model."""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10,
            max_storage_mb=1000
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.backup_job = BackupJob.objects.create(
            name="Test Backup",
            backup_type="full",
            tenant=self.tenant,
            created_by=self.user
        )
        self.restore_job = RestoreJob.objects.create(
            name="Test Restore",
            description="Test restore description",
            tenant=self.tenant,
            created_by=self.user,
            backup_job=self.backup_job
        )
    
    def test_restore_job_creation(self):
        """Test creating a restore job."""
        self.assertEqual(self.restore_job.name, "Test Restore")
        self.assertEqual(self.restore_job.status, "pending")
        self.assertEqual(self.restore_job.tenant, self.tenant)
        self.assertEqual(self.restore_job.created_by, self.user)
        self.assertEqual(self.restore_job.backup_job, self.backup_job)
        self.assertTrue(self.restore_job.restore_database)
        self.assertTrue(self.restore_job.restore_media)
        self.assertTrue(self.restore_job.restore_documents)
        self.assertTrue(self.restore_job.restore_settings)
        self.assertEqual(self.restore_job.conflict_resolution, "manual")
    
    def test_restore_job_str_representation(self):
        """Test the string representation of a restore job."""
        self.assertEqual(str(self.restore_job), "Test Restore (Test Tenant)")
    
    def test_restore_job_properties(self):
        """Test restore job properties."""
        # Test is_running property
        self.restore_job.status = "running"
        self.restore_job.save()
        self.assertTrue(self.restore_job.is_running)
        
        # Test is_completed property
        self.restore_job.status = "completed"
        self.restore_job.save()
        self.assertTrue(self.restore_job.is_completed)
        
        # Test is_failed property
        self.restore_job.status = "failed"
        self.restore_job.save()
        self.assertTrue(self.restore_job.is_failed)
    
    def test_restore_job_status_transitions(self):
        """Test restore job status transitions."""
        # Test start_restore
        self.restore_job.start_restore()
        self.assertEqual(self.restore_job.status, "running")
        self.assertIsNotNone(self.restore_job.started_at)
        
        # Test complete_restore
        self.restore_job.complete_restore()
        self.assertEqual(self.restore_job.status, "completed")
        self.assertEqual(self.restore_job.progress_percentage, 100)
        self.assertIsNotNone(self.restore_job.completed_at)
        
        # Test fail_restore
        self.restore_job.status = "running"
        self.restore_job.fail_restore("Test error message")
        self.assertEqual(self.restore_job.status, "failed")
        self.assertEqual(self.restore_job.error_message, "Test error message")
        self.assertIsNotNone(self.restore_job.completed_at)
        
        # Test cancel_restore
        self.restore_job.status = "running"
        self.restore_job.cancel_restore()
        self.assertEqual(self.restore_job.status, "cancelled")
        self.assertIsNotNone(self.restore_job.completed_at)
    
    def test_restore_job_progress_tracking(self):
        """Test restore job progress tracking."""
        # Test update_progress
        self.restore_job.update_progress(50, "Processing files")
        self.assertEqual(self.restore_job.progress_percentage, 50)
        self.assertEqual(self.restore_job.current_step, "Processing files")
        
        # Test add_log_entry
        self.restore_job.add_log_entry("info", "Test log message")
        self.assertEqual(len(self.restore_job.log_entries), 1)
        self.assertEqual(self.restore_job.log_entries[0]["level"], "info")
        self.assertEqual(self.restore_job.log_entries[0]["message"], "Test log message")
        
        # Test statistics
        self.restore_job.records_restored = 100
        self.restore_job.records_skipped = 10
        self.restore_job.records_failed = 5
        self.restore_job.save()
        
        self.assertEqual(self.restore_job.records_restored, 100)
        self.assertEqual(self.restore_job.records_skipped, 10)
        self.assertEqual(self.restore_job.records_failed, 5)


class BackupScheduleModelTest(TestCase):
    """Test cases for the BackupSchedule model."""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10,
            max_storage_mb=1000
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.backup_schedule = BackupSchedule.objects.create(
            name="Daily Backup",
            description="Daily backup schedule",
            frequency="daily",
            backup_type="full",
            tenant=self.tenant,
            created_by=self.user
        )
    
    def test_backup_schedule_creation(self):
        """Test creating a backup schedule."""
        self.assertEqual(self.backup_schedule.name, "Daily Backup")
        self.assertEqual(self.backup_schedule.frequency, "daily")
        self.assertEqual(self.backup_schedule.backup_type, "full")
        self.assertEqual(self.backup_schedule.tenant, self.tenant)
        self.assertEqual(self.backup_schedule.created_by, self.user)
        self.assertTrue(self.backup_schedule.is_active)
        self.assertTrue(self.backup_schedule.include_database)
        self.assertTrue(self.backup_schedule.include_media)
        self.assertTrue(self.backup_schedule.include_documents)
        self.assertTrue(self.backup_schedule.include_settings)
        self.assertTrue(self.backup_schedule.compress)
        self.assertTrue(self.backup_schedule.encrypt)
        self.assertEqual(self.backup_schedule.retention_days, 30)
    
    def test_backup_schedule_str_representation(self):
        """Test the string representation of a backup schedule."""
        self.assertEqual(str(self.backup_schedule), "Daily Backup (Test Tenant)")
    
    def test_backup_schedule_is_due_property(self):
        """Test backup schedule is_due property."""
        # Test when next_run is None
        self.backup_schedule.next_run = None
        self.backup_schedule.save()
        self.assertTrue(self.backup_schedule.is_due)
        
        # Test when next_run is in the future
        self.backup_schedule.next_run = timezone.now() + timedelta(days=1)
        self.backup_schedule.save()
        self.assertFalse(self.backup_schedule.is_due)
        
        # Test when next_run is in the past
        self.backup_schedule.next_run = timezone.now() - timedelta(days=1)
        self.backup_schedule.save()
        self.assertTrue(self.backup_schedule.is_due)
        
        # Test when schedule is inactive
        self.backup_schedule.is_active = False
        self.backup_schedule.save()
        self.assertFalse(self.backup_schedule.is_due)
    
    def test_backup_schedule_calculate_next_run(self):
        """Test backup schedule calculate_next_run method."""
        # Test daily frequency
        self.backup_schedule.frequency = "daily"
        self.backup_schedule.run_at = timezone.now().time()
        next_run = self.backup_schedule.calculate_next_run()
        self.assertIsNotNone(next_run)
        self.assertGreater(next_run, timezone.now())
        
        # Test weekly frequency
        self.backup_schedule.frequency = "weekly"
        self.backup_schedule.run_weekday = 0  # Monday
        next_run = self.backup_schedule.calculate_next_run()
        self.assertIsNotNone(next_run)
        
        # Test monthly frequency
        self.backup_schedule.frequency = "monthly"
        self.backup_schedule.run_day = 15
        next_run = self.backup_schedule.calculate_next_run()
        self.assertIsNotNone(next_run)
    
    def test_backup_schedule_mark_as_run(self):
        """Test backup schedule mark_as_run method."""
        backup_job = BackupJob.objects.create(
            name="Test Backup",
            backup_type="full",
            tenant=self.tenant,
            created_by=self.user
        )
        
        # Mark schedule as run
        self.backup_schedule.mark_as_run(backup_job)
        
        # Verify the schedule was updated
        self.assertIsNotNone(self.backup_schedule.last_run)
        self.assertEqual(self.backup_schedule.last_backup_job, backup_job)
        self.assertIsNotNone(self.backup_schedule.next_run)
    
    def test_backup_schedule_email_recipients(self):
        """Test backup schedule email recipients."""
        # Test with no recipients
        self.backup_schedule.email_recipients = None
        self.backup_schedule.save()
        self.assertEqual(self.backup_schedule.get_email_recipients_list(), [])
        
        # Test with recipients
        self.backup_schedule.email_recipients = "user1@example.com, user2@example.com"
        self.backup_schedule.save()
        recipients = self.backup_schedule.get_email_recipients_list()
        self.assertEqual(len(recipients), 2)
        self.assertIn("user1@example.com", recipients)
        self.assertIn("user2@example.com", recipients)


class BackupJobManagerTest(TestCase):
    """Test cases for the BackupJobManager."""
    
    def setUp(self):
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
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant1
        )
        
        # Create backup jobs for different tenants
        self.backup1 = BackupJob.objects.create(
            name="Backup 1",
            backup_type="full",
            tenant=self.tenant1,
            created_by=self.user
        )
        self.backup2 = BackupJob.objects.create(
            name="Backup 2",
            backup_type="incremental",
            tenant=self.tenant1,
            created_by=self.user
        )
        self.backup3 = BackupJob.objects.create(
            name="Backup 3",
            backup_type="full",
            tenant=self.tenant2,
            created_by=self.user
        )
        
        # Set different statuses
        self.backup1.status = "completed"
        self.backup1.save()
        self.backup2.status = "failed"
        self.backup2.save()
        self.backup3.status = "running"
        self.backup3.save()
    
    def test_for_tenant_method(self):
        """Test the for_tenant method."""
        tenant1_backups = BackupJob.objects.for_tenant(self.tenant1)
        self.assertEqual(tenant1_backups.count(), 2)
        
        tenant2_backups = BackupJob.objects.for_tenant(self.tenant2)
        self.assertEqual(tenant2_backups.count(), 1)
    
    def test_active_method(self):
        """Test the active method."""
        active_backups = BackupJob.objects.active()
        self.assertEqual(active_backups.count(), 2)  # completed and running
        
        # Check that failed backup is not included
        backup_ids = list(active_backups.values_list('id', flat=True))
        self.assertNotIn(self.backup2.id, backup_ids)
    
    def test_completed_method(self):
        """Test the completed method."""
        completed_backups = BackupJob.objects.completed()
        self.assertEqual(completed_backups.count(), 1)
        self.assertEqual(completed_backups.first().id, self.backup1.id)
    
    def test_failed_method(self):
        """Test the failed method."""
        failed_backups = BackupJob.objects.failed()
        self.assertEqual(failed_backups.count(), 1)
        self.assertEqual(failed_backups.first().id, self.backup2.id)
    
    def test_running_method(self):
        """Test the running method."""
        running_backups = BackupJob.objects.running()
        self.assertEqual(running_backups.count(), 1)
        self.assertEqual(running_backups.first().id, self.backup3.id)
    
    def test_by_type_method(self):
        """Test the by_type method."""
        full_backups = BackupJob.objects.by_type("full")
        self.assertEqual(full_backups.count(), 2)
        
        incremental_backups = BackupJob.objects.by_type("incremental")
        self.assertEqual(incremental_backups.count(), 1)


class RestoreJobManagerTest(TestCase):
    """Test cases for the RestoreJobManager."""
    
    def setUp(self):
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
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant1
        )
        
        # Create restore jobs for different tenants
        self.restore1 = RestoreJob.objects.create(
            name="Restore 1",
            tenant=self.tenant1,
            created_by=self.user
        )
        self.restore2 = RestoreJob.objects.create(
            name="Restore 2",
            tenant=self.tenant1,
            created_by=self.user
        )
        self.restore3 = RestoreJob.objects.create(
            name="Restore 3",
            tenant=self.tenant2,
            created_by=self.user
        )
        
        # Set different statuses
        self.restore1.status = "completed"
        self.restore1.save()
        self.restore2.status = "failed"
        self.restore2.save()
        self.restore3.status = "running"
        self.restore3.save()
    
    def test_for_tenant_method(self):
        """Test the for_tenant method."""
        tenant1_restores = RestoreJob.objects.for_tenant(self.tenant1)
        self.assertEqual(tenant1_restores.count(), 2)
        
        tenant2_restores = RestoreJob.objects.for_tenant(self.tenant2)
        self.assertEqual(tenant2_restores.count(), 1)
    
    def test_active_method(self):
        """Test the active method."""
        active_restores = RestoreJob.objects.active()
        self.assertEqual(active_restores.count(), 2)  # completed and running
        
        # Check that failed restore is not included
        restore_ids = list(active_restores.values_list('id', flat=True))
        self.assertNotIn(self.restore2.id, restore_ids)
    
    def test_completed_method(self):
        """Test the completed method."""
        completed_restores = RestoreJob.objects.completed()
        self.assertEqual(completed_restores.count(), 1)
        self.assertEqual(completed_restores.first().id, self.restore1.id)
    
    def test_failed_method(self):
        """Test the failed method."""
        failed_restores = RestoreJob.objects.failed()
        self.assertEqual(failed_restores.count(), 1)
        self.assertEqual(failed_restores.first().id, self.restore2.id)
    
    def test_running_method(self):
        """Test the running method."""
        running_restores = RestoreJob.objects.running()
        self.assertEqual(running_restores.count(), 1)
        self.assertEqual(running_restores.first().id, self.restore3.id)
    
    def test_pending_method(self):
        """Test the pending method."""
        pending_restores = RestoreJob.objects.pending()
        self.assertEqual(pending_restores.count(), 0)
        
        # Create a pending restore
        restore4 = RestoreJob.objects.create(
            name="Restore 4",
            tenant=self.tenant1,
            created_by=self.user
        )
        
        pending_restores = RestoreJob.objects.pending()
        self.assertEqual(pending_restores.count(), 1)
        self.assertEqual(pending_restores.first().id, restore4.id)


class BackupScheduleManagerTest(TestCase):
    """Test cases for the BackupScheduleManager."""
    
    def setUp(self):
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
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant1
        )
        
        # Create backup schedules for different tenants
        self.schedule1 = BackupSchedule.objects.create(
            name="Schedule 1",
            frequency="daily",
            tenant=self.tenant1,
            created_by=self.user
        )
        self.schedule2 = BackupSchedule.objects.create(
            name="Schedule 2",
            frequency="weekly",
            tenant=self.tenant1,
            created_by=self.user,
            is_active=False
        )
        self.schedule3 = BackupSchedule.objects.create(
            name="Schedule 3",
            frequency="monthly",
            tenant=self.tenant2,
            created_by=self.user
        )
    
    def test_for_tenant_method(self):
        """Test the for_tenant method."""
        tenant1_schedules = BackupSchedule.objects.for_tenant(self.tenant1)
        self.assertEqual(tenant1_schedules.count(), 2)
        
        tenant2_schedules = BackupSchedule.objects.for_tenant(self.tenant2)
        self.assertEqual(tenant2_schedules.count(), 1)
    
    def test_active_method(self):
        """Test the active method."""
        active_schedules = BackupSchedule.objects.active()
        self.assertEqual(active_schedules.count(), 2)
        
        # Check that inactive schedule is not included
        schedule_ids = list(active_schedules.values_list('id', flat=True))
        self.assertNotIn(self.schedule2.id, schedule_ids)
    
    def test_inactive_method(self):
        """Test the inactive method."""
        inactive_schedules = BackupSchedule.objects.inactive()
        self.assertEqual(inactive_schedules.count(), 1)
        self.assertEqual(inactive_schedules.first().id, self.schedule2.id)
    
    def test_due_method(self):
        """Test the due method."""
        # Set schedule1 as due (next_run in the past)
        self.schedule1.next_run = timezone.now() - timedelta(hours=1)
        self.schedule1.save()
        
        # Set schedule3 as not due (next_run in the future)
        self.schedule3.next_run = timezone.now() + timedelta(days=1)
        self.schedule3.save()
        
        due_schedules = BackupSchedule.objects.due()
        self.assertEqual(due_schedules.count(), 1)
        self.assertEqual(due_schedules.first().id, self.schedule1.id)
    
    def test_by_frequency_method(self):
        """Test the by_frequency method."""
        daily_schedules = BackupSchedule.objects.by_frequency("daily")
        self.assertEqual(daily_schedules.count(), 1)
        self.assertEqual(daily_schedules.first().id, self.schedule1.id)
        
        weekly_schedules = BackupSchedule.objects.by_frequency("weekly")
        self.assertEqual(weekly_schedules.count(), 1)
        self.assertEqual(weekly_schedules.first().id, self.schedule2.id)
        
        monthly_schedules = BackupSchedule.objects.by_frequency("monthly")
        self.assertEqual(monthly_schedules.count(), 1)
        self.assertEqual(monthly_schedules.first().id, self.schedule3.id)


class BackupUtilityTest(TestCase):
    """Test cases for the BackupUtility class."""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10,
            max_storage_mb=1000
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.backup_job = BackupJob.objects.create(
            name="Test Backup",
            backup_type="full",
            tenant=self.tenant,
            created_by=self.user
        )
        self.backup_utility = BackupUtility(self.backup_job)
    
    def test_backup_utility_initialization(self):
        """Test BackupUtility initialization."""
        self.assertEqual(self.backup_utility.backup_job, self.backup_job)
        self.assertEqual(self.backup_utility.tenant, self.tenant)
        self.assertEqual(self.backup_utility.temp_dir, "")
        self.assertEqual(self.backup_utility.backup_file_path, "")
    
    @patch('backup_restore.utils.tempfile.mkdtemp')
    @patch('backup_restore.utils.shutil.rmtree')
    def test_create_backup_full(self, mock_rmtree, mock_mkdtemp):
        """Test creating a full backup."""
        # Mock temporary directory
        temp_dir = "/tmp/backup_test"
        mock_mkdtemp.return_value = temp_dir
        
        # Mock backup methods
        with patch.object(self.backup_utility, '_create_full_backup') as mock_full_backup, \
             patch.object(self.backup_utility, '_compress_backup') as mock_compress, \
             patch.object(self.backup_utility, '_encrypt_backup') as mock_encrypt, \
             patch.object(self.backup_utility, '_move_backup_to_storage') as mock_move, \
             patch('os.path.getsize', return_value=1048576):
            
            # Test successful backup
            result = self.backup_utility.create_backup()
            
            self.assertTrue(result)
            self.assertEqual(self.backup_job.status, "completed")
            self.assertEqual(self.backup_job.file_size, 1048576)
            mock_full_backup.assert_called_once()
            mock_compress.assert_called_once()
            mock_encrypt.assert_called_once()
            mock_move.assert_called_once()
            mock_rmtree.assert_called_once_with(temp_dir)
    
    @patch('backup_restore.utils.tempfile.mkdtemp')
    @patch('backup_restore.utils.shutil.rmtree')
    def test_create_backup_incremental(self, mock_rmtree, mock_mkdtemp):
        """Test creating an incremental backup."""
        # Create parent backup
        parent_backup = BackupJob.objects.create(
            name="Parent Backup",
            backup_type="full",
            tenant=self.tenant,
            created_by=self.user,
            status="completed",
            completed_at=timezone.now() - timedelta(days=1)
        )
        
        # Create incremental backup job
        incremental_job = BackupJob.objects.create(
            name="Incremental Backup",
            backup_type="incremental",
            tenant=self.tenant,
            created_by=self.user,
            parent_backup=parent_backup
        )
        
        backup_utility = BackupUtility(incremental_job)
        
        # Mock temporary directory
        temp_dir = "/tmp/backup_test"
        mock_mkdtemp.return_value = temp_dir
        
        # Mock backup methods
        with patch.object(backup_utility, '_create_incremental_backup') as mock_incremental_backup, \
             patch.object(backup_utility, '_compress_backup') as mock_compress, \
             patch.object(backup_utility, '_encrypt_backup') as mock_encrypt, \
             patch.object(backup_utility, '_move_backup_to_storage') as mock_move, \
             patch('os.path.getsize', return_value=524288):
            
            # Test successful backup
            result = backup_utility.create_backup()
            
            self.assertTrue(result)
            self.assertEqual(incremental_job.status, "completed")
            self.assertEqual(incremental_job.file_size, 524288)
            mock_incremental_backup.assert_called_once()
            mock_compress.assert_called_once()
            mock_encrypt.assert_called_once()
            mock_move.assert_called_once()
            mock_rmtree.assert_called_once_with(temp_dir)
    
    @patch('backup_restore.utils.tempfile.mkdtemp')
    @patch('backup_restore.utils.shutil.rmtree')
    def test_create_backup_failure(self, mock_rmtree, mock_mkdtemp):
        """Test backup creation failure."""
        # Mock temporary directory
        temp_dir = "/tmp/backup_test"
        mock_mkdtemp.return_value = temp_dir
        
        # Mock backup method to raise exception
        with patch.object(self.backup_utility, '_create_full_backup', side_effect=Exception("Test error")):
            # Test failed backup
            result = self.backup_utility.create_backup()
            
            self.assertFalse(result)
            self.assertEqual(self.backup_job.status, "failed")
            self.assertEqual(self.backup_job.error_message, "Backup failed: Test error")
            mock_rmtree.assert_called_once_with(temp_dir)
    
    @patch('backup_restore.utils.call_command')
    @patch('builtins.open')
    @patch('os.path.join')
    def test_create_database_backup(self, mock_join, mock_open, mock_call_command):
        """Test creating a database backup."""
        # Mock path joining
        mock_join.return_value = "/tmp/database.sql"
        
        # Test database backup
        self.backup_utility._create_database_backup()
        
        # Verify dumpdata was called for each model
        models_to_backup = [
            'accounts.CustomUser',
            'clients.Client',
            'cases.Case',
            'documents.Document',
            'billing.Invoice',
            'billing.Payment',
            'audit.AuditLog',
        ]
        
        expected_calls = [
            ((model, '--filter=tenant={}'.format(self.tenant.id)), {'stdout': mock_open.return_value.__enter__.return_value})
            for model in models_to_backup
        ]
        
        self.assertEqual(mock_call_command.call_count, len(models_to_backup))
    
    @patch('backup_restore.utils.shutil.copytree')
    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('os.path.join')
    def test_create_media_backup(self, mock_join, mock_makedirs, mock_exists, mock_copytree):
        """Test creating a media backup."""
        # Mock path joining
        mock_join.side_effect = lambda *args: "/".join(args)
        
        # Mock directory existence
        mock_exists.return_value = True
        
        # Test media backup
        self.backup_utility._create_media_backup()
        
        # Verify directories were created and files copied
        mock_makedirs.assert_called()
        mock_copytree.assert_called()
    
    @patch('json.dump')
    @patch('builtins.open')
    @patch('os.path.join')
    def test_create_settings_backup(self, mock_join, mock_open, mock_dump):
        """Test creating a settings backup."""
        # Mock path joining
        mock_join.side_effect = lambda *args: "/".join(args)
        
        # Test settings backup
        self.backup_utility._create_settings_backup()
        
        # Verify JSON dump was called
        mock_dump.assert_called()
    
    @patch('json.dump')
    @patch('builtins.open')
    @patch('os.path.join')
    def test_create_backup_metadata(self, mock_join, mock_open, mock_dump):
        """Test creating backup metadata."""
        # Mock path joining
        mock_join.return_value = "/tmp/metadata.json"
        
        # Test metadata creation
        self.backup_utility._create_backup_metadata()
        
        # Verify JSON dump was called with correct metadata
        mock_dump.assert_called_once()
        args, kwargs = mock_dump.call_args
        metadata = args[0]
        
        self.assertEqual(metadata['backup_type'], self.backup_job.backup_type)
        self.assertEqual(metadata['tenant_id'], self.tenant.id)
        self.assertEqual(metadata['tenant_name'], self.tenant.name)
        self.assertEqual(metadata['backup_job_id'], self.backup_job.id)
        self.assertEqual(metadata['backup_name'], self.backup_job.name)
    
    @patch('backup_restore.utils.tarfile.open')
    @patch('os.path.join')
    def test_compress_backup(self, mock_join, mock_tarfile):
        """Test compressing backup."""
        # Mock path joining
        mock_join.return_value = "/tmp/compressed.tar.gz"
        
        # Mock tarfile
        mock_tar = MagicMock()
        mock_tarfile.return_value.__enter__.return_value = mock_tar
        
        # Set temp directory
        self.backup_utility.temp_dir = "/tmp/backup_temp"
        
        # Test compression
        self.backup_utility._compress_backup()
        
        # Verify tarfile was created
        mock_tarfile.assert_called_once_with("/tmp/compressed.tar.gz", 'w:gz')
        mock_tar.add.assert_called_once()
        self.assertEqual(self.backup_utility.backup_file_path, "/tmp/compressed.tar.gz")
    
    @patch('builtins.open')
    @patch('os.remove')
    def test_encrypt_backup(self, mock_remove, mock_open):
        """Test encrypting backup."""
        # Set backup file path
        self.backup_utility.backup_file_path = "/tmp/backup.tar.gz"
        
        # Mock file operations
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = b"test data"
        
        # Test encryption
        with patch.object(self.backup_utility.backup_job, 'get_encryption_key', return_value=b'test_key'):
            self.backup_utility._encrypt_backup()
        
        # Verify file was encrypted
        mock_open.assert_called()
        mock_remove.assert_called_once_with("/tmp/backup.tar.gz")
        self.assertEqual(self.backup_utility.backup_file_path, "/tmp/backup.tar.gz.enc")


class RestoreUtilityTest(TestCase):
    """Test cases for the RestoreUtility class."""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10,
            max_storage_mb=1000
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.backup_job = BackupJob.objects.create(
            name="Test Backup",
            backup_type="full",
            tenant=self.tenant,
            created_by=self.user
        )
        self.restore_job = RestoreJob.objects.create(
            name="Test Restore",
            tenant=self.tenant,
            created_by=self.user,
            backup_job=self.backup_job
        )
        self.restore_utility = RestoreUtility(self.restore_job)
    
    def test_restore_utility_initialization(self):
        """Test RestoreUtility initialization."""
        self.assertEqual(self.restore_utility.restore_job, self.restore_job)
        self.assertEqual(self.restore_utility.tenant, self.tenant)
        self.assertEqual(self.restore_utility.temp_dir, "")
        self.assertEqual(self.restore_utility.backup_file_path, "")
    
    @patch('backup_restore.utils.tempfile.mkdtemp')
    @patch('backup_restore.utils.shutil.rmtree')
    def test_restore_from_backup(self, mock_rmtree, mock_mkdtemp):
        """Test restoring from backup."""
        # Mock temporary directory
        temp_dir = "/tmp/restore_test"
        mock_mkdtemp.return_value = temp_dir
        
        # Mock restore methods
        with patch.object(self.restore_utility, '_prepare_backup_file') as mock_prepare, \
             patch.object(self.restore_utility, '_is_compressed_backup', return_value=False), \
             patch.object(self.restore_utility, '_is_encrypted_backup', return_value=False), \
             patch.object(self.restore_utility, '_restore_database') as mock_restore_db, \
             patch.object(self.restore_utility, '_restore_media') as mock_restore_media, \
             patch.object(self.restore_utility, '_restore_documents') as mock_restore_docs, \
             patch.object(self.restore_utility, '_restore_settings') as mock_restore_settings:
            
            # Test successful restore
            result = self.restore_utility.restore_from_backup()
            
            self.assertTrue(result)
            self.assertEqual(self.restore_job.status, "completed")
            mock_prepare.assert_called_once()
            mock_restore_db.assert_called_once()
            mock_restore_media.assert_called_once()
            mock_restore_docs.assert_called_once()
            mock_restore_settings.assert_called_once()
            mock_rmtree.assert_called_once_with(temp_dir)
    
    @patch('backup_restore.utils.tempfile.mkdtemp')
    @patch('backup_restore.utils.shutil.rmtree')
    def test_restore_preview(self, mock_rmtree, mock_mkdtemp):
        """Test creating a restore preview."""
        # Set restore job to preview mode
        self.restore_job.status = "preview"
        self.restore_job.save()
        
        # Mock temporary directory
        temp_dir = "/tmp/restore_test"
        mock_mkdtemp.return_value = temp_dir
        
        # Mock restore methods
        with patch.object(self.restore_utility, '_prepare_backup_file') as mock_prepare, \
             patch.object(self.restore_utility, '_is_compressed_backup', return_value=False), \
             patch.object(self.restore_utility, '_is_encrypted_backup', return_value=False), \
             patch.object(self.restore_utility, '_create_restore_preview') as mock_preview:
            
            # Test successful preview
            result = self.restore_utility.restore_from_backup()
            
            self.assertTrue(result)
            self.assertEqual(self.restore_job.status, "preview")
            mock_prepare.assert_called_once()
            mock_preview.assert_called_once()
            mock_rmtree.assert_called_once_with(temp_dir)
    
    @patch('backup_restore.utils.tempfile.mkdtemp')
    @patch('backup_restore.utils.shutil.rmtree')
    def test_restore_failure(self, mock_rmtree, mock_mkdtemp):
        """Test restore failure."""
        # Mock temporary directory
        temp_dir = "/tmp/restore_test"
        mock_mkdtemp.return_value = temp_dir
        
        # Mock restore method to raise exception
        with patch.object(self.restore_utility, '_prepare_backup_file', side_effect=Exception("Test error")):
            # Test failed restore
            result = self.restore_utility.restore_from_backup()
            
            self.assertFalse(result)
            self.assertEqual(self.restore_job.status, "failed")
            self.assertEqual(self.restore_job.error_message, "Restore failed: Test error")
            mock_rmtree.assert_called_once_with(temp_dir)
    
    def test_is_compressed_backup(self):
        """Test checking if backup is compressed."""
        # Test with tar.gz file
        self.restore_utility.backup_file_path = "/tmp/backup.tar.gz"
        self.assertTrue(self.restore_utility._is_compressed_backup())
        
        # Test with zip file
        self.restore_utility.backup_file_path = "/tmp/backup.zip"
        self.assertTrue(self.restore_utility._is_compressed_backup())
        
        # Test with uncompressed file
        self.restore_utility.backup_file_path = "/tmp/backup.sql"
        self.assertFalse(self.restore_utility._is_compressed_backup())
    
    def test_is_encrypted_backup(self):
        """Test checking if backup is encrypted."""
        # Test with encrypted file
        self.restore_utility.backup_file_path = "/tmp/backup.tar.gz.enc"
        self.assertTrue(self.restore_utility._is_encrypted_backup())
        
        # Test with unencrypted file
        self.restore_utility.backup_file_path = "/tmp/backup.tar.gz"
        self.assertFalse(self.restore_utility._is_encrypted_backup())
    
    @patch('backup_restore.utils.tarfile.open')
    @patch('os.makedirs')
    @patch('os.path.join')
    def test_extract_backup(self, mock_join, mock_makedirs, mock_tarfile):
        """Test extracting compressed backup."""
        # Mock path joining
        mock_join.side_effect = lambda *args: "/".join(args)
        
        # Mock tarfile
        mock_tar = MagicMock()
        mock_tarfile.return_value.__enter__.return_value = mock_tar
        
        # Set backup file path
        self.restore_utility.backup_file_path = "/tmp/backup.tar.gz"
        self.restore_utility.temp_dir = "/tmp/restore"
        
        # Test extraction
        self.restore_utility._extract_backup()
        
        # Verify tarfile was extracted
        mock_tarfile.assert_called_once_with("/tmp/backup.tar.gz", 'r:gz')
        mock_tar.extractall.assert_called_once()
        self.assertEqual(self.restore_utility.backup_file_path, "/tmp/restore/extracted")
    
    @patch('builtins.open')
    @patch('os.remove')
    def test_decrypt_backup(self, mock_remove, mock_open):
        """Test decrypting backup."""
        # Set backup file path
        self.restore_utility.backup_file_path = "/tmp/backup.tar.gz.enc"
        
        # Mock file operations
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = b"encrypted data"
        
        # Mock encryption key
        with patch.object(self.backup_job, 'encryption_key', 'test_key'):
            # Test decryption
            self.restore_utility._decrypt_backup()
        
        # Verify file was decrypted
        mock_open.assert_called()
        mock_remove.assert_called_once_with("/tmp/backup.tar.gz.enc")
        self.assertEqual(self.restore_utility.backup_file_path, "/tmp/backup.tar.gz")
    
    @patch('json.load')
    @patch('builtins.open')
    @patch('os.path.exists')
    @patch('os.path.join')
    def test_preview_database_restore(self, mock_join, mock_exists, mock_open, mock_load):
        """Test previewing database restore."""
        # Mock path joining
        mock_join.return_value = "/tmp/database.sql"
        
        # Mock file existence
        mock_exists.return_value = True
        
        # Mock file content
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.__iter__.return_value = [
            '"model": "accounts.CustomUser"',
            '"model": "clients.Client"',
            '"model": "cases.Case"',
        ]
        
        # Mock file size
        with patch('os.path.getsize', return_value=1024):
            # Test preview
            result = self.restore_utility._preview_database_restore()
        
        # Verify preview data
        self.assertTrue(result['exists'])
        self.assertEqual(result['record_count'], 3)
        self.assertEqual(result['file_size'], 1024)
    
    @patch('os.walk')
    @patch('os.path.getsize')
    @patch('os.path.exists')
    @patch('os.path.join')
    def test_preview_media_restore(self, mock_join, mock_exists, mock_getsize, mock_walk):
        """Test previewing media restore."""
        # Mock path joining
        mock_join.return_value = "/tmp/media/file.txt"
        
        # Mock directory existence
        mock_exists.return_value = True
        
        # Mock file walk
        mock_walk.return_value = [
            ("/tmp/media", [], ["file1.txt", "file2.txt"])
        ]
        
        # Mock file size
        mock_getsize.side_effect = [512, 256]
        
        # Test preview
        result = self.restore_utility._preview_media_restore()
        
        # Verify preview data
        self.assertTrue(result['exists'])
        self.assertEqual(result['file_count'], 2)
        self.assertEqual(result['total_size'], 768)
    
    @patch('json.load')
    @patch('builtins.open')
    @patch('os.walk')
    @patch('os.path.exists')
    @patch('os.path.join')
    def test_preview_documents_restore(self, mock_join, mock_exists, mock_walk, mock_open, mock_load):
        """Test previewing documents restore."""
        # Mock path joining
        mock_join.side_effect = lambda *args: "/".join(args)
        
        # Mock directory existence
        mock_exists.return_value = True
        
        # Mock file walk
        mock_walk.return_value = [
            ("/tmp/documents/files", [], ["doc1.pdf", "doc2.pdf"])
        ]
        
        # Mock JSON content
        mock_load.return_value = [
            {"id": 1, "title": "Document 1"},
            {"id": 2, "title": "Document 2"},
            {"id": 3, "title": "Document 3"},
        ]
        
        # Test preview
        result = self.restore_utility._preview_documents_restore()
        
        # Verify preview data
        self.assertTrue(result['exists'])
        self.assertEqual(result['document_count'], 3)
        self.assertEqual(result['file_count'], 2)
    
    @patch('json.load')
    @patch('builtins.open')
    @patch('os.path.exists')
    @patch('os.path.join')
    def test_preview_settings_restore(self, mock_join, mock_exists, mock_open, mock_load):
        """Test previewing settings restore."""
        # Mock path joining
        mock_join.return_value = "/tmp/settings/tenant_settings.json"
        
        # Mock file existence
        mock_exists.return_value = True
        
        # Mock JSON content
        mock_load.return_value = {
            "tenant": {"name": "Test Tenant"},
            "settings": {"date_format": "YYYY-MM-DD", "timezone": "UTC"}
        }
        
        # Test preview
        result = self.restore_utility._preview_settings_restore()
        
        # Verify preview data
        self.assertTrue(result['exists'])
        self.assertEqual(result['tenant_name'], "Test Tenant")
        self.assertEqual(result['settings_count'], 2)
    
    @patch('shutil.copy2')
    @patch('os.makedirs')
    @patch('os.path.exists')
    @patch('os.path.join')
    def test_restore_media(self, mock_join, mock_exists, mock_makedirs, mock_copy2):
        """Test restoring media files."""
        # Mock path joining
        mock_join.side_effect = lambda *args: "/".join(args)
        
        # Mock directory existence
        mock_exists.return_value = True
        
        # Mock file walk
        with patch('os.walk') as mock_walk:
            mock_walk.return_value = [
                ("/tmp/media", [], ["file1.txt"])
            ]
            
            # Test restore with skip conflict resolution
            self.restore_job.conflict_resolution = "skip"
            self.restore_utility._restore_media()
            
            # Verify file was copied
            mock_copy2.assert_called()
    
    @patch('documents.models.Document.objects.create')
    @patch('documents.models.Document.objects.filter')
    @patch('json.load')
    @patch('builtins.open')
    @patch('os.path.exists')
    @patch('os.path.join')
    def test_restore_documents(self, mock_join, mock_exists, mock_open, mock_load, mock_filter, mock_create):
        """Test restoring documents."""
        # Mock path joining
        mock_join.side_effect = lambda *args: "/".join(args)
        
        # Mock directory existence
        mock_exists.return_value = True
        
        # Mock JSON content
        mock_load.return_value = [
            {"id": 1, "title": "Document 1", "description": "Test document", "category": "test"}
        ]
        
        # Mock document query
        mock_query = MagicMock()
        mock_query.exists.return_value = False
        mock_filter.return_value = mock_query
        
        # Mock document creation
        mock_doc = MagicMock()
        mock_create.return_value = mock_doc
        
        # Test restore
        self.restore_utility._restore_documents()
        
        # Verify document was created
        mock_create.assert_called_once_with(
            title="Document 1",
            description="Test document",
            category="test",
            tenant=self.tenant
        )
        self.assertEqual(self.restore_job.records_restored, 1)


class BackupRestoreUtilityTest(TestCase):
    """Test cases for backup/restore utility functions."""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10,
            max_storage_mb=1000
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.backup_job = BackupJob.objects.create(
            name="Test Backup",
            backup_type="full",
            tenant=self.tenant,
            created_by=self.user,
            status="completed",
            file_path="backups/tenant_1/test_backup.tar.gz",
            file_hash="abc123def456"
        )
    
    @patch('backup_restore.utils.default_storage.exists')
    @patch('backup_restore.utils.default_storage.open')
    @patch('backup_restore.utils.tempfile.NamedTemporaryFile')
    @patch('backup_restore.utils._calculate_file_hash')
    def test_verify_backup_integrity_success(self, mock_hash, mock_temp_file, mock_open, mock_exists):
        """Test successful backup integrity verification."""
        # Mock storage operations
        mock_exists.return_value = True
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_temp_file.return_value.__enter__.return_value.write = MagicMock()
        mock_hash.return_value = "abc123def456"
        
        # Test verification
        is_valid, message = verify_backup_integrity(self.backup_job)
        
        # Verify result
        self.assertTrue(is_valid)
        self.assertEqual(message, "Backup integrity verified")
    
    @patch('backup_restore.utils.default_storage.exists')
    def test_verify_backup_integrity_file_not_found(self, mock_exists):
        """Test backup integrity verification with file not found."""
        # Mock storage operations
        mock_exists.return_value = False
        
        # Test verification
        is_valid, message = verify_backup_integrity(self.backup_job)
        
        # Verify result
        self.assertFalse(is_valid)
        self.assertEqual(message, "Backup file not found in storage")
    
    @patch('backup_restore.utils.default_storage.exists')
    @patch('backup_restore.utils.default_storage.open')
    @patch('backup_restore.utils.tempfile.NamedTemporaryFile')
    @patch('backup_restore.utils._calculate_file_hash')
    def test_verify_backup_integrity_hash_mismatch(self, mock_hash, mock_temp_file, mock_open, mock_exists):
        """Test backup integrity verification with hash mismatch."""
        # Mock storage operations
        mock_exists.return_value = True
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_temp_file.return_value.__enter__.return_value.write = MagicMock()
        mock_hash.return_value = "different_hash"
        
        # Test verification
        is_valid, message = verify_backup_integrity(self.backup_job)
        
        # Verify result
        self.assertFalse(is_valid)
        self.assertEqual(message, "Backup file hash mismatch - file may be corrupted")
    
    @patch('backup_restore.utils.default_storage.exists')
    @patch('backup_restore.utils.default_storage.delete')
    @patch('backup_restore.utils.BackupJob.objects.filter')
    def test_cleanup_old_backups(self, mock_filter, mock_delete, mock_exists):
        """Test cleaning up old backups."""
        # Create backup schedule
        schedule = BackupSchedule.objects.create(
            name="Daily Backup",
            frequency="daily",
            retention_days=30,
            tenant=self.tenant,
            created_by=self.user
        )
        
        # Mock backup query
        mock_query = MagicMock()
        mock_filter.return_value = mock_query
        mock_query.__iter__.return_value = [self.backup_job]
        
        # Mock storage operations
        mock_exists.return_value = True
        
        # Test cleanup
        cleanup_old_backups()
        
        # Verify cleanup operations
        mock_filter.assert_called()
        mock_delete.assert_called_with(self.backup_job.file_path)
        mock_query.update.assert_called_with(status='deleted')


class BackupRestoreViewTest(TestCase):
    """Test cases for backup/restore views."""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10,
            max_storage_mb=1000
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        self.backup_job = BackupJob.objects.create(
            name="Test Backup",
            backup_type="full",
            tenant=self.tenant,
            created_by=self.user
        )
        self.restore_job = RestoreJob.objects.create(
            name="Test Restore",
            tenant=self.tenant,
            created_by=self.user,
            backup_job=self.backup_job
        )
        self.backup_schedule = BackupSchedule.objects.create(
            name="Daily Backup",
            frequency="daily",
            tenant=self.tenant,
            created_by=self.user
        )
    
    def test_backup_job_list_view_queryset(self):
        """Test BackupJobListView queryset filtering."""
        # Create view
        view = BackupJobListView()
        
        # Mock request with tenant
        request = MagicMock()
        request.tenant = self.tenant
        request.GET = {}
        view.request = request
        
        # Get queryset
        queryset = view.get_queryset()
        
        # Verify filtering
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().id, self.backup_job.id)
    
    def test_restore_job_list_view_queryset(self):
        """Test RestoreJobListView queryset filtering."""
        # Create view
        view = RestoreJobListView()
        
        # Mock request with tenant
        request = MagicMock()
        request.tenant = self.tenant
        request.GET = {}
        view.request = request
        
        # Get queryset
        queryset = view.get_queryset()
        
        # Verify filtering
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().id, self.restore_job.id)
    
    def test_backup_schedule_list_view_queryset(self):
        """Test BackupScheduleListView queryset filtering."""
        # Create view
        view = BackupScheduleListView()
        
        # Mock request with tenant
        request = MagicMock()
        request.tenant = self.tenant
        request.GET = {}
        view.request = request
        
        # Get queryset
        queryset = view.get_queryset()
        
        # Verify filtering
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().id, self.backup_schedule.id)
    
    def test_backup_job_detail_view_object(self):
        """Test BackupJobDetailView object retrieval."""
        # Create view
        view = BackupJobDetailView()
        
        # Mock request with tenant
        request = MagicMock()
        request.tenant = self.tenant
        view.request = request
        
        # Set kwargs
        view.kwargs = {'pk': self.backup_job.id}
        
        # Get object
        obj = view.get_object()
        
        # Verify object
        self.assertEqual(obj.id, self.backup_job.id)
    
    def test_restore_job_detail_view_object(self):
        """Test RestoreJobDetailView object retrieval."""
        # Create view
        view = RestoreJobDetailView()
        
        # Mock request with tenant
        request = MagicMock()
        request.tenant = self.tenant
        view.request = request
        
        # Set kwargs
        view.kwargs = {'pk': self.restore_job.id}
        
        # Get object
        obj = view.get_object()
        
        # Verify object
        self.assertEqual(obj.id, self.restore_job.id)
    
    def test_backup_schedule_detail_view_object(self):
        """Test BackupScheduleDetailView object retrieval."""
        # Create view
        view = BackupScheduleDetailView()
        
        # Mock request with tenant
        request = MagicMock()
        request.tenant = self.tenant
        view.request = request
        
        # Set kwargs
        view.kwargs = {'pk': self.backup_schedule.id}
        
        # Get object
        obj = view.get_object()
        
        # Verify object
        self.assertEqual(obj.id, self.backup_schedule.id)
    
    @patch('backup_restore.views.log_activity')
    @patch('backup_restore.views.messages.success')
    def test_backup_job_create_view_form_valid(self, mock_messages, mock_log):
        """Test BackupJobCreateView form validation."""
        # Create view
        view = BackupJobCreateView()
        
        # Mock request with tenant and user
        request = MagicMock()
        request.tenant = self.tenant
        request.user = self.user
        view.request = request
        
        # Mock form
        form = MagicMock()
        form.save.return_value = MagicMock()
        
        # Test form validation
        with patch.object(view, 'get_success_url', return_value='/success/'):
            response = view.form_valid(form)
        
        # Verify tenant and user were set
        form.save.assert_called_once_with(commit=False)
        mock_log.assert_called_once()
        mock_messages.assert_called_once()
    
    @patch('backup_restore.views.log_activity')
    @patch('backup_restore.views.messages.success')
    def test_restore_job_create_view_form_valid(self, mock_messages, mock_log):
        """Test RestoreJobCreateView form validation."""
        # Create view
        view = RestoreJobCreateView()
        
        # Mock request with tenant and user
        request = MagicMock()
        request.tenant = self.tenant
        request.user = self.user
        view.request = request
        
        # Mock form
        form = MagicMock()
        form.save.return_value = MagicMock()
        
        # Test form validation
        with patch.object(view, 'get_success_url', return_value='/success/'):
            response = view.form_valid(form)
        
        # Verify tenant and user were set
        form.save.assert_called_once_with(commit=False)
        mock_log.assert_called_once()
        mock_messages.assert_called_once()
    
    @patch('backup_restore.views.log_activity')
    @patch('backup_restore.views.messages.success')
    def test_backup_schedule_create_view_form_valid(self, mock_messages, mock_log):
        """Test BackupScheduleCreateView form validation."""
        # Create view
        view = BackupScheduleCreateView()
        
        # Mock request with tenant and user
        request = MagicMock()
        request.tenant = self.tenant
        request.user = self.user
        view.request = request
        
        # Mock form
        form = MagicMock()
        schedule = MagicMock()
        form.save.return_value = schedule
        
        # Test form validation
        with patch.object(view, 'get_success_url', return_value='/success/'):
            response = view.form_valid(form)
        
        # Verify tenant and user were set
        form.save.assert_called_once_with(commit=False)
        schedule.calculate_next_run.assert_called_once()
        mock_log.assert_called_once()
        mock_messages.assert_called_once()


class BackupRestoreIntegrationTest(TransactionTestCase):
    """Integration tests for backup/restore functionality."""
    
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            plan="basic",
            max_users=10,
            max_storage_mb=1000
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
    
    @patch('backup_restore.utils.call_command')
    @patch('backup_restore.utils.tempfile.mkdtemp')
    @patch('backup_restore.utils.shutil.rmtree')
    def test_full_backup_and_restore_integration(self, mock_rmtree, mock_mkdtemp, mock_call_command):
        """Test full backup and restore integration."""
        # Mock temporary directory
        temp_dir = "/tmp/backup_test"
        mock_mkdtemp.return_value = temp_dir
        
        # Create a backup job
        backup_job = BackupJob.objects.create(
            name="Integration Test Backup",
            backup_type="full",
            tenant=self.tenant,
            created_by=self.user
        )
        
        # Create a backup utility
        backup_utility = BackupUtility(backup_job)
        
        # Mock backup methods
        with patch.object(backup_utility, '_create_full_backup') as mock_full_backup, \
             patch.object(backup_utility, '_compress_backup') as mock_compress, \
             patch.object(backup_utility, '_encrypt_backup') as mock_encrypt, \
             patch.object(backup_utility, '_move_backup_to_storage') as mock_move, \
             patch('os.path.getsize', return_value=1048576):
            
            # Create backup
            result = backup_utility.create_backup()
            self.assertTrue(result)
            self.assertEqual(backup_job.status, "completed")
        
        # Create a restore job
        restore_job = RestoreJob.objects.create(
            name="Integration Test Restore",
            tenant=self.tenant,
            created_by=self.user,
            backup_job=backup_job
        )
        
        # Create a restore utility
        restore_utility = RestoreUtility(restore_job)
        
        # Mock restore methods
        with patch.object(restore_utility, '_prepare_backup_file') as mock_prepare, \
             patch.object(restore_utility, '_is_compressed_backup', return_value=False), \
             patch.object(restore_utility, '_is_encrypted_backup', return_value=False), \
             patch.object(restore_utility, '_restore_database') as mock_restore_db, \
             patch.object(restore_utility, '_restore_media') as mock_restore_media, \
             patch.object(restore_utility, '_restore_documents') as mock_restore_docs, \
             patch.object(restore_utility, '_restore_settings') as mock_restore_settings:
            
            # Restore from backup
            result = restore_utility.restore_from_backup()
            self.assertTrue(result)
            self.assertEqual(restore_job.status, "completed")
    
    def test_backup_schedule_execution(self):
        """Test backup schedule execution."""
        # Create a backup schedule
        schedule = BackupSchedule.objects.create(
            name="Scheduled Backup",
            frequency="daily",
            backup_type="full",
            tenant=self.tenant,
            created_by=self.user
        )
        
        # Calculate next run time
        next_run = schedule.calculate_next_run()
        self.assertIsNotNone(next_run)
        
        # Check if schedule is due
        schedule.next_run = timezone.now() - timedelta(hours=1)
        schedule.save()
        self.assertTrue(schedule.is_due)
        
        # Mark schedule as run
        backup_job = BackupJob.objects.create(
            name="Scheduled Backup Job",
            backup_type="full",
            tenant=self.tenant,
            created_by=self.user,
            status="completed"
        )
        
        schedule.mark_as_run(backup_job)
        
        # Verify schedule was updated
        self.assertIsNotNone(schedule.last_run)
        self.assertEqual(schedule.last_backup_job, backup_job)
        self.assertIsNotNone(schedule.next_run)
        self.assertGreater(schedule.next_run, timezone.now())
    
    def test_backup_retention_policy(self):
        """Test backup retention policy."""
        # Create a backup schedule with retention policy
        schedule = BackupSchedule.objects.create(
            name="Backup with Retention",
            frequency="daily",
            retention_days=7,
            retention_count=5,
            tenant=self.tenant,
            created_by=self.user
        )
        
        # Create old backup jobs
        old_date = timezone.now() - timedelta(days=10)
        for i in range(10):
            BackupJob.objects.create(
                name=f"Old Backup {i}",
                backup_type="full",
                tenant=self.tenant,
                created_by=self.user,
                status="completed",
                created_at=old_date + timedelta(days=i)
            )
        
        # Create recent backup jobs
        recent_date = timezone.now() - timedelta(days=2)
        for i in range(3):
            BackupJob.objects.create(
                name=f"Recent Backup {i}",
                backup_type="full",
                tenant=self.tenant,
                created_by=self.user,
                status="completed",
                created_at=recent_date + timedelta(days=i)
            )
        
        # Test cleanup
        with patch('backup_restore.utils.default_storage.exists', return_value=True), \
             patch('backup_restore.utils.default_storage.delete'):
            cleanup_old_backups()
        
        # Verify old backups were marked as deleted
        deleted_backups = BackupJob.objects.filter(
            tenant=self.tenant,
            status="deleted"
        )
        self.assertGreater(deleted_backups.count(), 0)
    
    def test_backup_encryption_decryption(self):
        """Test backup encryption and decryption."""
        # Create a backup job with encryption
        backup_job = BackupJob.objects.create(
            name="Encrypted Backup",
            backup_type="full",
            encrypted=True,
            tenant=self.tenant,
            created_by=self.user
        )
        
        # Get encryption key
        key = backup_job.get_encryption_key()
        self.assertIsNotNone(key)
        self.assertEqual(backup_job.encryption_key, key.decode())
        
        # Create a restore job for the encrypted backup
        restore_job = RestoreJob.objects.create(
            name="Encrypted Restore",
            tenant=self.tenant,
            created_by=self.user,
            backup_job=backup_job
        )
        
        # Create a restore utility
        restore_utility = RestoreUtility(restore_job)
        
        # Mock encrypted backup file
        restore_utility.backup_file_path = "/tmp/backup.tar.gz.enc"
        
        # Test decryption
        with patch('builtins.open') as mock_open, \
             patch('os.remove') as mock_remove:
            
            # Mock file operations
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            mock_file.read.return_value = b"encrypted data"
            
            # Test decryption
            restore_utility._decrypt_backup()
            
            # Verify decryption
            mock_open.assert_called()
            mock_remove.assert_called_once()
            self.assertEqual(restore_utility.backup_file_path, "/tmp/backup.tar.gz")
    
    def test_backup_conflict_resolution(self):
        """Test backup conflict resolution during restore."""
        # Create a backup job
        backup_job = BackupJob.objects.create(
            name="Conflict Test Backup",
            backup_type="full",
            tenant=self.tenant,
            created_by=self.user
        )
        
        # Create a restore job with conflict resolution
        restore_job = RestoreJob.objects.create(
            name="Conflict Test Restore",
            conflict_resolution="overwrite",
            tenant=self.tenant,
            created_by=self.user,
            backup_job=backup_job
        )
        
        # Create a restore utility
        restore_utility = RestoreUtility(restore_job)
        
        # Mock media restore with conflicts
        with patch('os.path.exists', return_value=True), \
             patch('os.path.join', side_effect=lambda *args: "/".join(args)), \
             patch('os.walk', return_value=[("/tmp/media", [], ["conflict_file.txt"])]), \
             patch('os.makedirs'), \
             patch('os.remove') as mock_remove, \
             patch('shutil.copy2') as mock_copy:
            
            # Test restore with overwrite conflict resolution
            restore_utility._restore_media()
            
            # Verify conflicts were resolved by overwriting
            mock_remove.assert_called()
            mock_copy.assert_called()
    
    def test_backup_performance_with_large_dataset(self):
        """Test backup performance with large dataset."""
        # Create a backup job
        backup_job = BackupJob.objects.create(
            name="Performance Test Backup",
            backup_type="full",
            tenant=self.tenant,
            created_by=self.user
        )
        
        # Create a backup utility
        backup_utility = BackupUtility(backup_job)
        
        # Mock large dataset backup
        with patch.object(backup_utility, '_create_database_backup') as mock_db_backup, \
             patch.object(backup_utility, '_create_media_backup') as mock_media_backup, \
             patch.object(backup_utility, '_create_documents_backup') as mock_docs_backup, \
             patch.object(backup_utility, '_create_settings_backup') as mock_settings_backup, \
             patch.object(backup_utility, '_compress_backup') as mock_compress, \
             patch.object(backup_utility, '_encrypt_backup') as mock_encrypt, \
             patch.object(backup_utility, '_move_backup_to_storage') as mock_move, \
             patch('os.path.getsize', return_value=104857600),  # 100 MB
             patch('backup_restore.utils.tempfile.mkdtemp', return_value="/tmp/perf_test"), \
             patch('backup_restore.utils.shutil.rmtree'):
            
            # Simulate large dataset backup
            mock_db_backup.side_effect = lambda: backup_job.update_progress(25, "Database backup")
            mock_media_backup.side_effect = lambda: backup_job.update_progress(50, "Media backup")
            mock_docs_backup.side_effect = lambda: backup_job.update_progress(75, "Documents backup")
            mock_settings_backup.side_effect = lambda: backup_job.update_progress(90, "Settings backup")
            
            # Create backup
            start_time = timezone.now()
            result = backup_utility.create_backup()
            end_time = timezone.now()
            
            # Verify backup completed successfully
            self.assertTrue(result)
            self.assertEqual(backup_job.status, "completed")
            self.assertEqual(backup_job.file_size, 104857600)
            
            # Verify progress was updated
            self.assertEqual(backup_job.progress_percentage, 100)
            
            # Verify performance (should complete in reasonable time)
            duration = (end_time - start_time).total_seconds()
            self.assertLess(duration, 60)  # Should complete in less than 60 seconds