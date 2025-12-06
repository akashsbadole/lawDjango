from django.core.management.base import BaseCommand
from django.utils import timezone
from backup_restore.models import BackupJob, BackupSchedule
from backup_restore.utils import cleanup_old_backups
from audit.utils import log_activity


class Command(BaseCommand):
    help = 'Clean up old backups based on retention policies'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Clean up backups only for specific tenant ID'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force cleanup without confirmation'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        tenant_id = options['tenant_id']
        force = options['force']
        
        try:
            # Get backup schedules
            if tenant_id:
                schedules = BackupSchedule.objects.filter(
                    is_active=True,
                    tenant_id=tenant_id
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Checking backup cleanup for tenant {tenant_id}')
                )
            else:
                schedules = BackupSchedule.objects.filter(is_active=True)
                self.stdout.write(
                    self.style.SUCCESS('Checking backup cleanup for all tenants')
                )
            
            if not schedules:
                self.stdout.write(
                    self.style.WARNING('No active backup schedules found')
                )
                return
            
            total_deleted = 0
            total_failed = 0
            
            for schedule in schedules:
                try:
                    # Calculate what would be deleted
                    if dry_run:
                        deleted_count = self._simulate_cleanup(schedule)
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'[DRY RUN] Would delete {deleted_count} old backups for tenant: {schedule.tenant.name}'
                            )
                        )
                        total_deleted += deleted_count
                        continue
                    
                    # Ask for confirmation if not forced
                    if not force:
                        response = input(
                            f'Clean up old backups for tenant {schedule.tenant.name}? (y/N): '
                        )
                        if response.lower() != 'y':
                            self.stdout.write('Cleanup cancelled.')
                            continue
                    
                    # Perform actual cleanup
                    old_count = BackupJob.objects.filter(
                        tenant=schedule.tenant,
                        status='completed'
                    ).count()
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Cleaning up old backups for tenant: {schedule.tenant.name} (Current: {old_count})'
                        )
                    )
                    
                    # Clean up old backups
                    cleanup_old_backups()
                    
                    new_count = BackupJob.objects.filter(
                        tenant=schedule.tenant,
                        status='completed'
                    ).count()
                    
                    deleted_count = old_count - new_count
                    total_deleted += deleted_count
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Deleted {deleted_count} old backups for tenant: {schedule.tenant.name} (Remaining: {new_count})'
                        )
                    )
                    
                    # Log activity
                    log_activity(
                        tenant=schedule.tenant,
                        user=None,
                        activity_type='BACKUP_CLEANUP',
                        description=f'Cleaned up {deleted_count} old backups',
                        metadata={
                            'deleted_count': deleted_count,
                            'remaining_count': new_count
                        }
                    )
                    
                except Exception as e:
                    total_failed += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f'Error cleaning up backups for tenant {schedule.tenant.name}: {str(e)}'
                        )
                    )
                    
                    # Log error
                    log_activity(
                        tenant=schedule.tenant,
                        user=None,
                        activity_type='BACKUP_CLEANUP_FAILED',
                        description=f'Backup cleanup failed for tenant: {schedule.tenant.name}',
                        metadata={'error': str(e)}
                    )
            
            # Summary
            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'[DRY RUN] Would delete {total_deleted} old backups total'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Deleted {total_deleted} old backups total'
                    )
                )
                if total_failed > 0:
                    self.stdout.write(
                        self.style.WARNING(f'Failed to clean up {total_failed} tenants')
                    )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error during backup cleanup: {str(e)}')
            )
    
    def _simulate_cleanup(self, schedule):
        """Simulate what would be deleted during cleanup."""
        from django.utils import timezone
        
        deleted_count = 0
        
        # Calculate cutoff date
        if schedule.retention_days:
            cutoff_date = timezone.now() - timezone.timedelta(days=schedule.retention_days)
            
            # Count old backups
            old_backups = BackupJob.objects.filter(
                tenant=schedule.tenant,
                created_at__lt=cutoff_date,
                status='completed'
            )
            deleted_count += old_backups.count()
        
        # If retention count is specified, calculate based on count
        if schedule.retention_count:
            backups = BackupJob.objects.filter(
                tenant=schedule.tenant,
                status='completed'
            ).order_by('-created_at')
            
            if backups.count() > schedule.retention_count:
                backups_to_delete = backups[schedule.retention_count:]
                deleted_count += backups_to_delete.count()
        
        return deleted_count