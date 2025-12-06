try:
    from celery import shared_task
except ImportError:
    # Fallback for when celery is not available
    def shared_task(func):
        return func
from django.utils import timezone
from .models import BackupJob, RestoreJob, BackupSchedule
from .utils import BackupUtility, RestoreUtility, cleanup_old_backups
from audit.utils import log_activity


@shared_task(bind=True)
def execute_backup_task(self, backup_job_id):
    """
    Execute a backup job in the background.
    """
    try:
        # Get backup job
        backup_job = BackupJob.objects.get(pk=backup_job_id)
        
        # Check if backup can be executed
        if backup_job.status not in ['pending', 'failed']:
            return {'status': 'error', 'message': 'Backup cannot be executed in current status'}
        
        # Create backup utility and execute backup
        backup_utility = BackupUtility(backup_job)
        success = backup_utility.create_backup()
        
        if success:
            return {
                'status': 'success',
                'message': 'Backup completed successfully',
                'backup_job_id': str(backup_job.pk)
            }
        else:
            return {
                'status': 'error',
                'message': 'Backup failed',
                'backup_job_id': str(backup_job.pk)
            }
    
    except BackupJob.DoesNotExist:
        return {'status': 'error', 'message': 'Backup job not found'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@shared_task(bind=True)
def execute_restore_task(self, restore_job_id):
    """
    Execute a restore job in the background.
    """
    try:
        # Get restore job
        restore_job = RestoreJob.objects.get(pk=restore_job_id)
        
        # Check if restore can be executed
        if restore_job.status not in ['pending', 'preview']:
            return {'status': 'error', 'message': 'Restore cannot be executed in current status'}
        
        # Create restore utility and execute restore
        restore_utility = RestoreUtility(restore_job)
        success = restore_utility.restore_from_backup()
        
        if success:
            return {
                'status': 'success',
                'message': 'Restore completed successfully',
                'restore_job_id': str(restore_job.pk)
            }
        else:
            return {
                'status': 'error',
                'message': 'Restore failed',
                'restore_job_id': str(restore_job.pk)
            }
    
    except RestoreJob.DoesNotExist:
        return {'status': 'error', 'message': 'Restore job not found'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@shared_task(bind=True)
def preview_restore_task(self, restore_job_id):
    """
    Create a preview of a restore job in the background.
    """
    try:
        # Get restore job
        restore_job = RestoreJob.objects.get(pk=restore_job_id)
        
        # Check if restore can be previewed
        if restore_job.status != 'pending':
            return {'status': 'error', 'message': 'Restore cannot be previewed in current status'}
        
        # Set status to preview
        restore_job.status = 'preview'
        restore_job.save()
        
        # Create restore utility and create preview
        restore_utility = RestoreUtility(restore_job)
        success = restore_utility.restore_from_backup()
        
        if success:
            return {
                'status': 'success',
                'message': 'Restore preview created successfully',
                'restore_job_id': str(restore_job.pk)
            }
        else:
            return {
                'status': 'error',
                'message': 'Restore preview failed',
                'restore_job_id': str(restore_job.pk)
            }
    
    except RestoreJob.DoesNotExist:
        return {'status': 'error', 'message': 'Restore job not found'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@shared_task(bind=True)
def execute_scheduled_backups_task(self):
    """
    Execute all due scheduled backups.
    """
    try:
        # Get all due backup schedules
        due_schedules = BackupSchedule.objects.due()
        
        executed_count = 0
        failed_count = 0
        
        for schedule in due_schedules:
            try:
                # Create backup job from schedule
                backup_job = BackupJob.objects.create(
                    name=f"Scheduled: {schedule.name}",
                    description=f"Automatic backup from schedule: {schedule.description or schedule.name}",
                    backup_type=schedule.backup_type,
                    include_database=schedule.include_database,
                    include_media=schedule.include_media,
                    include_documents=schedule.include_documents,
                    include_settings=schedule.include_settings,
                    compress=schedule.compress,
                    encrypted=schedule.encrypt,
                    tenant=schedule.tenant,
                    created_by=None  # System created
                )
                
                # Execute backup
                backup_utility = BackupUtility(backup_job)
                success = backup_utility.create_backup()
                
                if success:
                    # Mark schedule as run
                    schedule.mark_as_run(backup_job)
                    executed_count += 1
                    
                    # Send email notification if enabled
                    if schedule.email_notification:
                        send_backup_completion_email(schedule, backup_job)
                else:
                    failed_count += 1
                    
            except Exception as e:
                failed_count += 1
                # Log error
                if schedule.tenant:
                    log_activity(
                        tenant=schedule.tenant,
                        user=None,
                        activity_type='SCHEDULED_BACKUP_FAILED',
                        description=f'Scheduled backup failed: {schedule.name}',
                        metadata={'error': str(e)}
                    )
        
        return {
            'status': 'success',
            'message': f'Executed {executed_count} scheduled backups, {failed_count} failed',
            'executed_count': executed_count,
            'failed_count': failed_count
        }
    
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@shared_task(bind=True)
def cleanup_old_backups_task(self):
    """
    Clean up old backups based on retention policies.
    """
    try:
        # Clean up old backups
        cleanup_old_backups()
        
        return {
            'status': 'success',
            'message': 'Backup cleanup completed successfully'
        }
    
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


@shared_task(bind=True)
def verify_backup_integrity_task(self, backup_job_id):
    """
    Verify the integrity of a backup file in the background.
    """
    try:
        # Get backup job
        backup_job = BackupJob.objects.get(pk=backup_job_id)
        
        # Verify backup integrity
        from .utils import verify_backup_integrity
        is_valid, message = verify_backup_integrity(backup_job)
        
        # Log verification result
        if backup_job.tenant:
            log_activity(
                tenant=backup_job.tenant,
                user=None,
                activity_type='BACKUP_VERIFIED' if is_valid else 'BACKUP_VERIFICATION_FAILED',
                description=f'Backup integrity check: {backup_job.name}',
                metadata={
                    'is_valid': is_valid,
                    'message': message
                }
            )
        
        return {
            'status': 'success',
            'message': message,
            'is_valid': is_valid,
            'backup_job_id': str(backup_job.pk)
        }
    
    except BackupJob.DoesNotExist:
        return {'status': 'error', 'message': 'Backup job not found'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}


def send_backup_completion_email(schedule, backup_job):
    """
    Send email notification when a scheduled backup completes.
    """
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from django.template.loader import render_to_string
        
        # Get email recipients
        recipients = schedule.get_email_recipients_list()
        if not recipients:
            return
        
        # Render email template
        context = {
            'schedule': schedule,
            'backup_job': backup_job,
            'tenant': schedule.tenant
        }
        
        subject = f'Backup Completed: {backup_job.name}'
        message = render_to_string('backup_restore/email/backup_completion.txt', context)
        html_message = render_to_string('backup_restore/email/backup_completion.html', context)
        
        # Send email
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            html_message=html_message,
            fail_silently=False
        )
        
    except Exception as e:
        # Log email error but don't fail the backup
        if schedule.tenant:
            log_activity(
                tenant=schedule.tenant,
                user=None,
                activity_type='BACKUP_EMAIL_FAILED',
                description=f'Failed to send backup completion email: {backup_job.name}',
                metadata={'error': str(e)}
            )


def send_restore_completion_email(restore_job):
    """
    Send email notification when a restore completes.
    """
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from django.template.loader import render_to_string
        
        # Get email recipients (tenant admin)
        if not restore_job.tenant:
            return
        
        # Get tenant admin users
        from accounts.models import CustomUser
        admin_users = CustomUser.objects.filter(
            tenant=restore_job.tenant,
            role__in=['admin', 'lawyer']
        )
        
        recipients = [user.email for user in admin_users if user.email]
        if not recipients:
            return
        
        # Render email template
        context = {
            'restore_job': restore_job,
            'tenant': restore_job.tenant
        }
        
        subject = f'Restore Completed: {restore_job.name}'
        message = render_to_string('backup_restore/email/restore_completion.txt', context)
        html_message = render_to_string('backup_restore/email/restore_completion.html', context)
        
        # Send email
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            html_message=html_message,
            fail_silently=False
        )
        
    except Exception as e:
        # Log email error but don't fail the restore
        if restore_job.tenant:
            log_activity(
                tenant=restore_job.tenant,
                user=None,
                activity_type='RESTORE_EMAIL_FAILED',
                description=f'Failed to send restore completion email: {restore_job.name}',
                metadata={'error': str(e)}
            )