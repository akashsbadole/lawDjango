from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from tenants.models import Tenant


class Command(BaseCommand):
    help = 'Restore suspended tenants'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Restore all suspended tenants'
        )
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Restore specific tenant by ID'
        )
        parser.add_argument(
            '--tenant-slug',
            type=str,
            help='Restore specific tenant by slug'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be restored without actually restoring'
        )
    
    def handle(self, *args, **options):
        all_tenants = options['all']
        tenant_id = options['tenant_id']
        tenant_slug = options['tenant_slug']
        dry_run = options['dry_run']
        
        # Get the system user for audit trail
        User = get_user_model()
        try:
            system_user = User.objects.filter(is_superuser=True).first()
            if not system_user:
                self.stdout.write(
                    self.style.ERROR('No superuser found to assign as changed_by user.')
                )
                return
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error getting system user: {e}')
            )
            return
        
        # Determine which tenants to restore
        tenants_to_restore = []
        
        if all_tenants:
            tenants_to_restore = list(Tenant.objects.suspended())
            self.stdout.write(f'Found {len(tenants_to_restore)} suspended tenants.')
        elif tenant_id:
            try:
                tenant = Tenant.objects.get(id=tenant_id, status='suspended')
                tenants_to_restore.append(tenant)
                self.stdout.write(f'Found tenant: {tenant.name} (ID: {tenant.id})')
            except Tenant.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'No suspended tenant found with ID: {tenant_id}')
                )
                return
        elif tenant_slug:
            try:
                tenant = Tenant.objects.get(slug=tenant_slug, status='suspended')
                tenants_to_restore.append(tenant)
                self.stdout.write(f'Found tenant: {tenant.name} (slug: {tenant.slug})')
            except Tenant.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'No suspended tenant found with slug: {tenant_slug}')
                )
                return
        else:
            self.stdout.write(
                self.style.ERROR(
                    'Please specify --all, --tenant-id, or --tenant-slug'
                )
            )
            return
        
        if not tenants_to_restore:
            self.stdout.write(self.style.WARNING('No tenants to restore.'))
            return
        
        # Show tenants to be restored
        for tenant in tenants_to_restore:
            self.stdout.write(f'  - {tenant.name} (suspended: {tenant.suspended_at})')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN: No tenants were actually restored.')
            )
            return
        
        # Confirm before restoration
        confirm = input(f'\nAre you sure you want to restore these {len(tenants_to_restore)} tenants? [y/N] ')
        if confirm.lower() != 'y':
            self.stdout.write(self.style.WARNING('Operation cancelled.'))
            return
        
        # Perform restoration
        restored_count = 0
        for tenant in tenants_to_restore:
            try:
                tenant.unsuspend(changed_by=system_user)
                restored_count += 1
                self.stdout.write(f'Restored: {tenant.name}')
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Failed to restore {tenant.name}: {e}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully restored {restored_count} tenants.'
            )
        )