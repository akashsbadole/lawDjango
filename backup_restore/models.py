import os
import json
import hashlib
from datetime import datetime, timedelta, time
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.conf import settings
from cryptography.fernet import Fernet
from .managers import BackupJobManager, RestoreJobManager, BackupScheduleManager

User = get_user_model()


class BackupJob(models.Model):
    """
    Model representing a backup job for a tenant.
    """
    BACKUP_TYPE_CHOICES = [
        ('full', 'Full Backup'),
        ('incremental', 'Incremental Backup'),
        ('database_only', 'Database Only'),
        ('media_only', 'Media Files Only'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPE_CHOICES, default='full')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # File Information
    file_path = models.CharField(max_length=500, blank=True, null=True)
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_size = models.BigIntegerField(default=0)  # Size in bytes
    file_hash = models.CharField(max_length=64, blank=True, null=True)  # SHA-256 hash
    compressed = models.BooleanField(default=True)
    encrypted = models.BooleanField(default=True)
    encryption_key = models.CharField(max_length=100, blank=True, null=True)
    
    # Backup Content Options
    include_database = models.BooleanField(default=True)
    include_media = models.BooleanField(default=True)
    include_documents = models.BooleanField(default=True)
    include_settings = models.BooleanField(default=True)
    
    # Incremental Backup Options
    parent_backup = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='incremental_backups',
        help_text="Parent backup for incremental backups"
    )
    last_backup_time = models.DateTimeField(null=True, blank=True)
    
    # Tenant and User Information
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='backup_jobs'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_backups'
    )
    
    # Progress and Status
    progress_percentage = models.IntegerField(default=0)
    current_step = models.CharField(max_length=100, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    log_entries = models.JSONField(default=list, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    objects = BackupJobManager()
    
    class Meta:
        db_table = 'backup_jobs'
        verbose_name = 'Backup Job'
        verbose_name_plural = 'Backup Jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['backup_type']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
    
    @property
    def duration(self):
        """Calculate the duration of the backup job."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        elif self.started_at:
            return timezone.now() - self.started_at
        return None
    
    @property
    def file_size_mb(self):
        """Return file size in MB."""
        return round(self.file_size / (1024 * 1024), 2) if self.file_size else 0
    
    @property
    def is_running(self):
        """Check if the backup is currently running."""
        return self.status == 'running'
    
    @property
    def is_completed(self):
        """Check if the backup is completed."""
        return self.status == 'completed'
    
    @property
    def is_failed(self):
        """Check if the backup failed."""
        return self.status == 'failed'
    
    def start_backup(self):
        """Mark the backup as started."""
        self.status = 'running'
        self.started_at = timezone.now()
        self.save()
    
    def complete_backup(self, file_path, file_size=None):
        """Mark the backup as completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.progress_percentage = 100
        self.file_path = file_path
        
        if file_size:
            self.file_size = file_size
            
        # Calculate file hash
        if file_path and os.path.exists(file_path):
            self.file_hash = self._calculate_file_hash(file_path)
            
        self.save()
    
    def fail_backup(self, error_message):
        """Mark the backup as failed."""
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.save()
    
    def cancel_backup(self):
        """Cancel the backup."""
        self.status = 'cancelled'
        self.completed_at = timezone.now()
        self.save()
    
    def update_progress(self, percentage, step=None):
        """Update the backup progress."""
        self.progress_percentage = percentage
        if step:
            self.current_step = step
        self.save()
    
    def add_log_entry(self, level, message):
        """Add a log entry to the backup job."""
        entry = {
            'timestamp': timezone.now().isoformat(),
            'level': level,
            'message': message
        }
        self.log_entries.append(entry)
        self.save()
    
    def _calculate_file_hash(self, file_path):
        """Calculate SHA-256 hash of the backup file."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    
    def get_encryption_key(self):
        """Get or generate encryption key for the backup."""
        if self.encryption_key:
            return self.encryption_key.encode()
        else:
            key = Fernet.generate_key()
            self.encryption_key = key.decode()
            self.save()
            return key
    
    def get_absolute_url(self):
        """Return the absolute URL for this backup job."""
        from django.urls import reverse
        return reverse('backup_restore:backup_detail', kwargs={'pk': self.pk})


class RestoreJob(models.Model):
    """
    Model representing a restore job for a tenant.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('preview', 'Preview'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    CONFLICT_RESOLUTION_CHOICES = [
        ('skip', 'Skip Conflicts'),
        ('overwrite', 'Overwrite Existing'),
        ('rename', 'Rename Conflicting'),
        ('manual', 'Manual Resolution'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Backup Information
    backup_file = models.FileField(upload_to='restore_backups/')
    backup_job = models.ForeignKey(
        BackupJob,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='restore_jobs'
    )
    
    # Restore Options
    restore_database = models.BooleanField(default=True)
    restore_media = models.BooleanField(default=True)
    restore_documents = models.BooleanField(default=True)
    restore_settings = models.BooleanField(default=True)
    conflict_resolution = models.CharField(
        max_length=20,
        choices=CONFLICT_RESOLUTION_CHOICES,
        default='manual'
    )
    
    # Preview Information
    preview_data = models.JSONField(default=dict, blank=True)
    conflicts = models.JSONField(default=list, blank=True)
    
    # Tenant and User Information
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='restore_jobs'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_restores'
    )
    
    # Progress and Status
    progress_percentage = models.IntegerField(default=0)
    current_step = models.CharField(max_length=100, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    log_entries = models.JSONField(default=list, blank=True)
    
    # Statistics
    records_restored = models.IntegerField(default=0)
    records_skipped = models.IntegerField(default=0)
    records_failed = models.IntegerField(default=0)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    objects = RestoreJobManager()
    
    class Meta:
        db_table = 'restore_jobs'
        verbose_name = 'Restore Job'
        verbose_name_plural = 'Restore Jobs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
    
    @property
    def duration(self):
        """Calculate the duration of the restore job."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        elif self.started_at:
            return timezone.now() - self.started_at
        return None
    
    @property
    def is_running(self):
        """Check if the restore is currently running."""
        return self.status == 'running'
    
    @property
    def is_completed(self):
        """Check if the restore is completed."""
        return self.status == 'completed'
    
    @property
    def is_failed(self):
        """Check if the restore failed."""
        return self.status == 'failed'
    
    def start_restore(self):
        """Mark the restore as started."""
        self.status = 'running'
        self.started_at = timezone.now()
        self.save()
    
    def complete_restore(self):
        """Mark the restore as completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.progress_percentage = 100
        self.save()
    
    def fail_restore(self, error_message):
        """Mark the restore as failed."""
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.error_message = error_message
        self.save()
    
    def cancel_restore(self):
        """Cancel the restore."""
        self.status = 'cancelled'
        self.completed_at = timezone.now()
        self.save()
    
    def update_progress(self, percentage, step=None):
        """Update the restore progress."""
        self.progress_percentage = percentage
        if step:
            self.current_step = step
        self.save()
    
    def add_log_entry(self, level, message):
        """Add a log entry to the restore job."""
        entry = {
            'timestamp': timezone.now().isoformat(),
            'level': level,
            'message': message
        }
        self.log_entries.append(entry)
        self.save()
    
    def get_absolute_url(self):
        """Return the absolute URL for this restore job."""
        from django.urls import reverse
        return reverse('backup_restore:restore_detail', kwargs={'pk': self.pk})


class BackupSchedule(models.Model):
    """
    Model representing a scheduled backup for a tenant.
    """
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ]
    
    BACKUP_TYPE_CHOICES = [
        ('full', 'Full Backup'),
        ('incremental', 'Incremental Backup'),
    ]
    
    # Basic Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='daily')
    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPE_CHOICES, default='full')
    
    # Schedule Configuration
    is_active = models.BooleanField(default=True)
    run_at = models.TimeField(default=time(2, 0))  # Default to 2 AM
    run_day = models.IntegerField(null=True, blank=True, help_text="Day of month for monthly backups (1-31)")
    run_weekday = models.IntegerField(null=True, blank=True, help_text="Day of week for weekly backups (0-6, 0=Monday)")
    
    # Retention Policy
    retention_days = models.IntegerField(default=30, help_text="Number of days to retain backups")
    retention_count = models.IntegerField(null=True, blank=True, help_text="Maximum number of backups to retain")
    
    # Backup Options
    include_database = models.BooleanField(default=True)
    include_media = models.BooleanField(default=True)
    include_documents = models.BooleanField(default=True)
    include_settings = models.BooleanField(default=True)
    compress = models.BooleanField(default=True)
    encrypt = models.BooleanField(default=True)
    
    # Notification Settings
    email_notification = models.BooleanField(default=True)
    email_recipients = models.TextField(blank=True, null=True, help_text="Comma-separated email addresses")
    
    # Tenant and User Information
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='backup_schedules'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_backup_schedules'
    )
    
    # Tracking
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    last_backup_job = models.ForeignKey(
        BackupJob,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='schedules'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = BackupScheduleManager()
    
    class Meta:
        db_table = 'backup_schedules'
        verbose_name = 'Backup Schedule'
        verbose_name_plural = 'Backup Schedules'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'is_active']),
            models.Index(fields=['next_run']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.tenant.name})"
    
    @property
    def is_due(self):
        """Check if the schedule is due for execution."""
        if not self.is_active:
            return False
        if not self.next_run:
            return True
        return timezone.now() >= self.next_run
    
    def calculate_next_run(self):
        """Calculate the next run time based on frequency."""
        now = timezone.now()
        
        if self.frequency == 'daily':
            next_run = now.replace(hour=self.run_at.hour, minute=self.run_at.minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
                
        elif self.frequency == 'weekly':
            if self.run_weekday is not None:
                days_ahead = self.run_weekday - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                next_run = now + timedelta(days=days_ahead)
                next_run = next_run.replace(hour=self.run_at.hour, minute=self.run_at.minute, second=0, microsecond=0)
            else:
                next_run = now.replace(hour=self.run_at.hour, minute=self.run_at.minute, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(weeks=1)
                    
        elif self.frequency == 'monthly':
            if self.run_day is not None:
                if now.day <= self.run_day:
                    next_run = now.replace(day=self.run_day, hour=self.run_at.hour, minute=self.run_at.minute, second=0, microsecond=0)
                else:
                    if now.month == 12:
                        next_run = now.replace(year=now.year + 1, month=1, day=self.run_day, hour=self.run_at.hour, minute=self.run_at.minute, second=0, microsecond=0)
                    else:
                        next_run = now.replace(month=now.month + 1, day=self.run_day, hour=self.run_at.hour, minute=self.run_at.minute, second=0, microsecond=0)
            else:
                next_run = now.replace(hour=self.run_at.hour, minute=self.run_at.minute, second=0, microsecond=0)
                if next_run <= now:
                    if now.month == 12:
                        next_run = now.replace(year=now.year + 1, month=1)
                    else:
                        next_run = now.replace(month=now.month + 1)
                        
        elif self.frequency == 'quarterly':
            months_ahead = (3 - now.month % 3) % 3
            if months_ahead == 0:
                months_ahead = 3
            if self.run_day is not None and now.day <= self.run_day:
                target_day = self.run_day or now.day
                next_run = now.replace(month=now.month + months_ahead, day=target_day, hour=self.run_at.hour, minute=self.run_at.minute, second=0, microsecond=0)
            else:
                if now.month + months_ahead > 12:
                    next_run = now.replace(year=now.year + 1, month=(now.month + months_ahead - 12) % 12, day=self.run_day or now.day, hour=self.run_at.hour, minute=self.run_at.minute, second=0, microsecond=0)
                else:
                    next_run = now.replace(month=now.month + months_ahead, day=self.run_day or now.day, hour=self.run_at.hour, minute=self.run_at.minute, second=0, microsecond=0)
                    
        elif self.frequency == 'yearly':
            next_run = now.replace(year=now.year + 1, month=now.month, day=self.run_day or now.day, hour=self.run_at.hour, minute=self.run_at.minute, second=0, microsecond=0)
            
        else:
            next_run = now + timedelta(days=1)
            
        self.next_run = next_run
        self.save()
        return next_run
    
    def mark_as_run(self, backup_job):
        """Mark the schedule as run and update next run time."""
        self.last_run = timezone.now()
        self.last_backup_job = backup_job
        self.calculate_next_run()
    
    def get_email_recipients_list(self):
        """Get email recipients as a list."""
        if not self.email_recipients:
            return []
        return [email.strip() for email in self.email_recipients.split(',') if email.strip()]
    
    def get_absolute_url(self):
        """Return the absolute URL for this backup schedule."""
        from django.urls import reverse
        return reverse('backup_restore:schedule_detail', kwargs={'pk': self.pk})