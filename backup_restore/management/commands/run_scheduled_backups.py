from django.core.management.base import BaseCommand
from django.utils import timezone
from backup_restore.models import BackupSchedule, BackupJob
from backup_restore.utils import BackupUtility
from audit.utils import log_activity


class Command(BaseCommand):
    help = 'Execute all due scheduled backups'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be executed without actually running backups'
        )
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Run scheduled backups only for specific tenant ID'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        tenant_id = options['tenant_id']
        
        try:
            # Get due backup schedules
            if tenant_id:
                due_schedules = BackupSchedule.objects.filter(
                    is_active=True,
                    tenant_id=tenant_id
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Checking scheduled backups for tenant {tenant_id}')
                )
            else:
                due_schedules = BackupSchedule.objects.due()
                self.stdout.write(
                    self.style.SUCCESS('Checking scheduled backups for all tenants')
                )
            
            if not due_schedules:
                self.stdout.write(
                    self.style.WARNING('No due scheduled backups found')
                )
                return
            
            executed_count = 0
            failed_count = 0
            
            for schedule in due_schedules:
                try:
                    if dry_run:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'[DRY RUN] Would execute scheduled backup: {schedule.name} (Tenant: {schedule.tenant.name})'
                            )
                        )
                        executed_count += 1
                        continue
                    
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
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Executing scheduled backup: {schedule.name} (Tenant: {schedule.tenant.name})'
                        )
                    )
                    
                    # Execute backup
                    backup_utility = BackupUtility(backup_job)
                    success = backup_utility.create_backup()
                    
                    if success:
                        # Mark schedule as run
                        schedule.mark_as_run(backup_job)
                        executed_count += 1
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Scheduled backup completed: {schedule.name} (Backup ID: {backup_job.pk})'
                            )
                        )
                        
                        # Send email notification if enabled
                        if schedule.email_notification:
                            self._send_backup_completion_email(schedule, backup_job)
                    else:
                        failed_count += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f'Scheduled backup failed: {schedule.name}'
                            )
                        )
                        
                except Exception as e:
                    failed_count += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f'Error executing scheduled backup {schedule.name}: {str(e)}'
                        )
                    )
                    
                    # Log error
                    if schedule.tenant:
                        log_activity(
                            tenant=schedule.tenant,
                            user=None,
                            activity_type='SCHEDULED_BACKUP_FAILED',
                            description=f'Scheduled backup failed: {schedule.name}',
                            metadata={'error': str(e)}
                        )
            
            summary = f'Executed {executed_count} scheduled backups'
            if failed_count > 0:
                summary += f', {failed_count} failed'
            
            self.stdout.write(
                self.style.SUCCESS(summary)
            )
        
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error running scheduled backups: {str(e)}')
            )
    
    def _send_backup_completion_email(self, schedule, backup_job):
        """Send email notification when a scheduled backup completes."""
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
            
            self.stdout.write(
                self.style.SUCCESS(f'Email notification sent to {len(recipients)} recipients')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Failed to send email notification: {str(e)}')
            )