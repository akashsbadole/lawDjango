from django.core.management.base import BaseCommand
from django.utils import timezone
from backup_restore.models import RestoreJob
from backup_restore.utils import RestoreUtility
from audit.utils import log_activity


class Command(BaseCommand):
    help = 'Execute a restore job by ID'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'restore_id',
            type=int,
            help='ID of the restore job to execute'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force execution even if restore is not in pending status'
        )
        parser.add_argument(
            '--preview-only',
            action='store_true',
            help='Only create preview, do not execute restore'
        )
    
    def handle(self, *args, **options):
        restore_id = options['restore_id']
        force = options['force']
        preview_only = options['preview_only']
        
        try:
            # Get restore job
            restore_job = RestoreJob.objects.get(pk=restore_id)
            
            # Check if restore can be executed
            if not force and restore_job.status not in ['pending', 'preview']:
                self.stdout.write(
                    self.style.ERROR(
                        f'Restore {restore_id} cannot be executed in current status: {restore_job.status}'
                    )
                )
                return
            
            # Set preview mode if requested
            if preview_only:
                restore_job.status = 'preview'
                restore_job.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Creating preview for restore {restore_id}: {restore_job.name}')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'Executing restore {restore_id}: {restore_job.name}')
                )
            
            # Execute restore
            restore_utility = RestoreUtility(restore_job)
            success = restore_utility.restore_from_backup()
            
            if success:
                action = 'previewed' if preview_only else 'completed'
                self.stdout.write(
                    self.style.SUCCESS(f'Restore {restore_id} {action} successfully')
                )
                
                # Log activity
                activity_type = 'RESTORE_PREVIEWED' if preview_only else 'RESTORE_EXECUTED'
                log_activity(
                    tenant=restore_job.tenant,
                    user=None,
                    activity_type=activity_type,
                    description=f'Restore {action} via command: {restore_job.name}',
                    related_object=restore_job
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f'Restore {restore_id} failed')
                )
        
        except RestoreJob.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Restore job with ID {restore_id} not found')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error executing restore: {str(e)}')
            )