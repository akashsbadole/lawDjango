from django.core.management.base import BaseCommand
from django.utils import timezone
from backup_restore.models import BackupJob
from backup_restore.utils import BackupUtility
from audit.utils import log_activity


class Command(BaseCommand):
    help = 'Execute a backup job by ID'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'backup_id',
            type=int,
            help='ID of the backup job to execute'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force execution even if backup is not in pending status'
        )
    
    def handle(self, *args, **options):
        backup_id = options['backup_id']
        force = options['force']
        
        try:
            # Get backup job
            backup_job = BackupJob.objects.get(pk=backup_id)
            
            # Check if backup can be executed
            if not force and backup_job.status not in ['pending', 'failed']:
                self.stdout.write(
                    self.style.ERROR(
                        f'Backup {backup_id} cannot be executed in current status: {backup_job.status}'
                    )
                )
                return
            
            # Execute backup
            self.stdout.write(
                self.style.SUCCESS(f'Executing backup {backup_id}: {backup_job.name}')
            )
            
            backup_utility = BackupUtility(backup_job)
            success = backup_utility.create_backup()
            
            if success:
                self.stdout.write(
                    self.style.SUCCESS(f'Backup {backup_id} completed successfully')
                )
                
                # Log activity
                log_activity(
                    tenant=backup_job.tenant,
                    user=None,
                    activity_type='BACKUP_EXECUTED',
                    description=f'Backup executed via command: {backup_job.name}',
                    related_object=backup_job
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'Backup {backup_id} failed')
                )
        
        except BackupJob.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Backup job with ID {backup_id} not found')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error executing backup: {str(e)}')
            )