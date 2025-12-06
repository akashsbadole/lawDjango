from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from tenants.models import Tenant


class Command(BaseCommand):
    help = 'Clean up permanently deleted tenants after retention period'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Number of days to retain soft-deleted tenants before permanent deletion (default: 90)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
    
    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        # Calculate cutoff date
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Find tenants deleted before cutoff date
        tenants_to_delete = Tenant.objects.filter(
            deleted_at__isnull=False,
            deleted_at__lt=cutoff_date
        )
        
        if not tenants_to_delete.exists():
            self.stdout.write(
                self.style.SUCCESS(f'No tenants found deleted more than {days} days ago.')
            )
            return
        
        self.stdout.write(
            f'Found {tenants_to_delete.count()} tenants deleted more than {days} days ago:'
        )
        
        for tenant in tenants_to_delete:
            self.stdout.write(f'  - {tenant.name} (deleted: {tenant.deleted_at})')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN: No tenants were actually deleted.')
            )
            return
        
        # Confirm before deletion
        confirm = input(f'\nAre you sure you want to permanently delete these {tenants_to_delete.count()} tenants? [y/N] ')
        if confirm.lower() != 'y':
            self.stdout.write(self.style.WARNING('Operation cancelled.'))
            return
        
        # Perform permanent deletion
        deleted_count = 0
        for tenant in tenants_to_delete:
            # In a real implementation, you might want to cascade delete related data
            # or archive it before permanent deletion
            tenant.permanent_delete()
            deleted_count += 1
            self.stdout.write(f'Deleted: {tenant.name}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully permanently deleted {deleted_count} tenants.'
            )
        )