from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from tenants.models import Tenant, TenantStatusHistory


class Command(BaseCommand):
    help = 'Check and report tenant status'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--status',
            type=str,
            choices=['active', 'suspended', 'deleted', 'trial_expired'],
            help='Filter by specific status'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to look back for status changes (default: 30)'
        )
        parser.add_argument(
            '--history',
            action='store_true',
            help='Show recent status changes'
        )
    
    def handle(self, *args, **options):
        status_filter = options['status']
        days = options['days']
        show_history = options['history']
        
        # Get tenants based on filter
        if status_filter:
            tenants = Tenant.objects.by_status(status_filter)
            self.stdout.write(f'Tenants with status "{status_filter}":')
        else:
            tenants = Tenant.objects.all()
            self.stdout.write('All tenants:')
        
        if not tenants.exists():
            self.stdout.write(self.style.WARNING('No tenants found.'))
            return
        
        # Display tenant information
        for tenant in tenants:
            status_display = tenant.get_status_display_with_icon()
            self.stdout.write(
                f'  - {tenant.name} ({tenant.slug}) - {status_display}'
            )
            
            # Show additional info based on status
            if tenant.status == 'suspended':
                self.stdout.write(
                    f'    Suspended: {tenant.suspended_at}'
                )
                if tenant.suspension_reason:
                    self.stdout.write(
                        f'    Reason: {tenant.suspension_reason}'
                    )
            elif tenant.status == 'deleted':
                self.stdout.write(
                    f'    Deleted: {tenant.deleted_at}'
                )
            
            # Show user count
            user_count = tenant.get_current_user_count()
            self.stdout.write(
                f'    Users: {user_count}/{tenant.max_users}'
            )
        
        # Show status history if requested
        if show_history:
            self.stdout.write('\nRecent status changes:')
            cutoff_date = timezone.now() - timedelta(days=days)
            
            history = TenantStatusHistory.objects.filter(
                changed_at__gte=cutoff_date
            ).order_by('-changed_at')
            
            if not history.exists():
                self.stdout.write(
                    self.style.WARNING(
                        f'No status changes in the last {days} days.'
                    )
                )
                return
            
            for change in history:
                self.stdout.write(
                    f'  - {change.tenant.name}: {change.old_status or "None"} → '
                    f'{change.new_status} at {change.changed_at}'
                )
                if change.reason:
                    self.stdout.write(f'    Reason: {change.reason}')
                if change.changed_by:
                    self.stdout.write(f'    Changed by: {change.changed_by.username}')
        
        # Summary statistics
        self.stdout.write('\nSummary:')
        total_tenants = Tenant.objects.count()
        active_count = Tenant.objects.active().count()
        suspended_count = Tenant.objects.suspended().count()
        deleted_count = Tenant.objects.deleted().count()
        trial_expired_count = Tenant.objects.trial_expired().count()
        
        self.stdout.write(f'  Total tenants: {total_tenants}')
        self.stdout.write(f'  Active: {active_count}')
        self.stdout.write(f'  Suspended: {suspended_count}')
        self.stdout.write(f'  Deleted: {deleted_count}')
        self.stdout.write(f'  Trial expired: {trial_expired_count}')