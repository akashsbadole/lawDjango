from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from audit.models import AuditLog, ActivityLog, LoginLog, SecurityEvent


class Command(BaseCommand):
    help = 'Clean up old audit logs based on retention policies'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--audit-retention',
            type=int,
            default=365,
            help='Days to retain audit logs (default: 365)',
        )
        parser.add_argument(
            '--activity-retention',
            type=int,
            default=180,
            help='Days to retain activity logs (default: 180)',
        )
        parser.add_argument(
            '--login-retention',
            type=int,
            default=90,
            help='Days to retain login logs (default: 90)',
        )
        parser.add_argument(
            '--security-retention',
            type=int,
            default=1825,  # 5 years
            help='Days to retain security events (default: 1825)',
        )
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Specific tenant ID to clean (default: all tenants)',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        audit_retention = options['audit_retention']
        activity_retention = options['activity_retention']
        login_retention = options['login_retention']
        security_retention = options['security_retention']
        tenant_id = options['tenant_id']
        
        self.stdout.write(self.style.SUCCESS('Starting audit log cleanup...'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be deleted'))
        
        # Calculate cutoff dates
        now = timezone.now()
        audit_cutoff = now - timedelta(days=audit_retention)
        activity_cutoff = now - timedelta(days=activity_retention)
        login_cutoff = now - timedelta(days=login_retention)
        security_cutoff = now - timedelta(days=security_retention)
        
        # Build base queryset
        base_kwargs = {}
        if tenant_id:
            base_kwargs['tenant_id'] = tenant_id
        
        # Clean audit logs
        audit_qs = AuditLog.objects.filter(
            timestamp__lt=audit_cutoff,
            **base_kwargs
        )
        audit_count = audit_qs.count()
        
        if audit_count > 0:
            self.stdout.write(
                f'Found {audit_count} audit logs older than {audit_cutoff.date()}'
            )
            if not dry_run:
                with transaction.atomic():
                    deleted_count, _ = audit_qs.delete()
                    self.stdout.write(
                        self.style.SUCCESS(f'Deleted {deleted_count} audit logs')
                    )
        
        # Clean activity logs
        activity_qs = ActivityLog.objects.filter(
            timestamp__lt=activity_cutoff,
            **base_kwargs
        )
        activity_count = activity_qs.count()
        
        if activity_count > 0:
            self.stdout.write(
                f'Found {activity_count} activity logs older than {activity_cutoff.date()}'
            )
            if not dry_run:
                with transaction.atomic():
                    deleted_count, _ = activity_qs.delete()
                    self.stdout.write(
                        self.style.SUCCESS(f'Deleted {deleted_count} activity logs')
                    )
        
        # Clean login logs
        login_qs = LoginLog.objects.filter(
            login_time__lt=login_cutoff,
            **base_kwargs
        )
        login_count = login_qs.count()
        
        if login_count > 0:
            self.stdout.write(
                f'Found {login_count} login logs older than {login_cutoff.date()}'
            )
            if not dry_run:
                with transaction.atomic():
                    deleted_count, _ = login_qs.delete()
                    self.stdout.write(
                        self.style.SUCCESS(f'Deleted {deleted_count} login logs')
                    )
        
        # Clean security events (only resolved ones)
        security_qs = SecurityEvent.objects.filter(
            timestamp__lt=security_cutoff,
            resolved=True,
            **base_kwargs
        )
        security_count = security_qs.count()
        
        if security_count > 0:
            self.stdout.write(
                f'Found {security_count} resolved security events older than {security_cutoff.date()}'
            )
            if not dry_run:
                with transaction.atomic():
                    deleted_count, _ = security_qs.delete()
                    self.stdout.write(
                        self.style.SUCCESS(f'Deleted {deleted_count} security events')
                    )
        
        total_deleted = audit_count + activity_count + login_count + security_count
        
        if total_deleted == 0:
            self.stdout.write(self.style.SUCCESS('No old audit logs found to clean up'))
        elif dry_run:
            self.stdout.write(
                self.style.WARNING(f'DRY RUN: Would delete {total_deleted} records total')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Cleanup completed. Deleted {total_deleted} records total')
            )