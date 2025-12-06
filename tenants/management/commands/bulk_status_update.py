from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from tenants.models import Tenant


class Command(BaseCommand):
    help = 'Bulk update tenant status'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--status',
            type=str,
            choices=['active', 'suspended', 'deleted', 'trial_expired'],
            required=True,
            help='New status to set'
        )
        parser.add_argument(
            '--tenant-ids',
            type=str,
            help='Comma-separated list of tenant IDs to update'
        )
        parser.add_argument(
            '--plan',
            type=str,
            choices=['free', 'basic', 'pro', 'enterprise'],
            help='Filter tenants by plan'
        )
        parser.add_argument(
            '--reason',
            type=str,
            default='Bulk status update',
            help='Reason for status change'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating'
        )
    
    def handle(self, *args, **options):
        new_status = options['status']
        tenant_ids = options['tenant_ids']
        plan_filter = options['plan']
        reason = options['reason']
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
        
        # Determine which tenants to update
        tenants_to_update = []
        
        if tenant_ids:
            # Parse comma-separated IDs
            id_list = [int(id.strip()) for id in tenant_ids.split(',') if id.strip().isdigit()]
            tenants_to_update = list(Tenant.objects.filter(id__in=id_list))
            self.stdout.write(f'Found {len(tenants_to_update)} tenants by ID.')
        elif plan_filter:
            tenants_to_update = list(Tenant.objects.by_plan(plan_filter))
            self.stdout.write(f'Found {len(tenants_to_update)} tenants with plan "{plan_filter}".')
        else:
            self.stdout.write(
                self.style.ERROR(
                    'Please specify either --tenant-ids or --plan'
                )
            )
            return
        
        if not tenants_to_update:
            self.stdout.write(self.style.WARNING('No tenants to update.'))
            return
        
        # Filter out tenants that already have the target status
        tenants_to_update = [
            t for t in tenants_to_update 
            if t.status != new_status
        ]
        
        if not tenants_to_update:
            self.stdout.write(
                self.style.WARNING(
                    f'All specified tenants already have status "{new_status}".'
                )
            )
            return
        
        # Show tenants to be updated
        self.stdout.write(f'\nTenants to be updated to "{new_status}":')
        for tenant in tenants_to_update:
            self.stdout.write(
                f'  - {tenant.name} ({tenant.slug}) - Current: {tenant.status}'
            )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN: No tenants were actually updated.')
            )
            return
        
        # Confirm before update
        confirm = input(f'\nAre you sure you want to update these {len(tenants_to_update)} tenants? [y/N] ')
        if confirm.lower() != 'y':
            self.stdout.write(self.style.WARNING('Operation cancelled.'))
            return
        
        # Perform status update
        updated_count = 0
        for tenant in tenants_to_update:
            try:
                # Use the appropriate method based on the new status
                if new_status == 'deleted':
                    tenant.soft_delete(reason=reason, changed_by=system_user)
                elif new_status == 'suspended':
                    tenant.suspend(reason=reason, changed_by=system_user)
                elif new_status == 'trial_expired':
                    tenant.expire_trial(changed_by=system_user)
                elif new_status == 'active':
                    if tenant.status == 'deleted':
                        tenant.restore(changed_by=system_user)
                    elif tenant.status == 'suspended':
                        tenant.unsuspend(changed_by=system_user)
                    else:
                        tenant._record_status_change('active', reason, system_user)
                        tenant.status = 'active'
                        tenant.is_active = True
                        tenant.save()
                
                updated_count += 1
                self.stdout.write(f'Updated: {tenant.name} → {new_status}')
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Failed to update {tenant.name}: {e}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully updated {updated_count} tenants to status "{new_status}".'
            )
        )