from django.db import models


class BackupJobManager(models.Manager):
    """
    Manager for BackupJob model with tenant-aware queries.
    """
    def get_queryset(self):
        return super().get_queryset().select_related('tenant', 'created_by')
    
    def for_tenant(self, tenant):
        """Filter backup jobs by tenant."""
        return self.get_queryset().filter(tenant=tenant)
    
    def active(self):
        """Get active backup jobs (not failed or cancelled)."""
        return self.get_queryset().exclude(status__in=['failed', 'cancelled'])
    
    def completed(self):
        """Get completed backup jobs."""
        return self.get_queryset().filter(status='completed')
    
    def failed(self):
        """Get failed backup jobs."""
        return self.get_queryset().filter(status='failed')
    
    def running(self):
        """Get currently running backup jobs."""
        return self.get_queryset().filter(status='running')
    
    def by_type(self, backup_type):
        """Filter backup jobs by type."""
        return self.get_queryset().filter(backup_type=backup_type)


class RestoreJobManager(models.Manager):
    """
    Manager for RestoreJob model with tenant-aware queries.
    """
    def get_queryset(self):
        return super().get_queryset().select_related('tenant', 'created_by', 'backup_job')
    
    def for_tenant(self, tenant):
        """Filter restore jobs by tenant."""
        return self.get_queryset().filter(tenant=tenant)
    
    def active(self):
        """Get active restore jobs (not failed or cancelled)."""
        return self.get_queryset().exclude(status__in=['failed', 'cancelled'])
    
    def completed(self):
        """Get completed restore jobs."""
        return self.get_queryset().filter(status='completed')
    
    def failed(self):
        """Get failed restore jobs."""
        return self.get_queryset().filter(status='failed')
    
    def running(self):
        """Get currently running restore jobs."""
        return self.get_queryset().filter(status='running')
    
    def pending(self):
        """Get pending restore jobs."""
        return self.get_queryset().filter(status='pending')


class BackupScheduleManager(models.Manager):
    """
    Manager for BackupSchedule model with tenant-aware queries.
    """
    def get_queryset(self):
        return super().get_queryset().select_related('tenant', 'created_by', 'last_backup_job')
    
    def for_tenant(self, tenant):
        """Filter backup schedules by tenant."""
        return self.get_queryset().filter(tenant=tenant)
    
    def active(self):
        """Get active backup schedules."""
        return self.get_queryset().filter(is_active=True)
    
    def inactive(self):
        """Get inactive backup schedules."""
        return self.get_queryset().filter(is_active=False)
    
    def due(self):
        """Get backup schedules that are due for execution."""
        from django.utils import timezone
        return self.active().filter(
            models.Q(next_run__lte=timezone.now()) | models.Q(next_run__isnull=True)
        )
    
    def by_frequency(self, frequency):
        """Filter backup schedules by frequency."""
        return self.get_queryset().filter(frequency=frequency)