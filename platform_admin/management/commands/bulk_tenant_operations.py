from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
import csv
import io

from tenants.models import Tenant, TenantSettings
from accounts.models import CustomUser
from platform_admin.models import AdminActivityLog, AdminNote

User = get_user_model()


class Command(BaseCommand):
    help = 'Perform bulk operations on tenants'
    
    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest='operation', help='Available operations')
        
        # Enable tenants
        enable_parser = subparsers.add_parser('enable', help='Enable multiple tenants')
        enable_parser.add_argument(
            '--tenant-ids',
            type=str,
            required=True,
            help='Comma-separated list of tenant IDs to enable'
        )
        enable_parser.add_argument(
            '--reason',
            type=str,
            help='Reason for enabling tenants'
        )
        
        # Disable tenants
        disable_parser = subparsers.add_parser('disable', help='Disable multiple tenants')
        disable_parser.add_argument(
            '--tenant-ids',
            type=str,
            required=True,
            help='Comma-separated list of tenant IDs to disable'
        )
        disable_parser.add_argument(
            '--reason',
            type=str,
            help='Reason for disabling tenants'
        )
        
        # Delete tenants
        delete_parser = subparsers.add_parser('delete', help='Soft delete multiple tenants')
        delete_parser.add_argument(
            '--tenant-ids',
            type=str,
            required=True,
            help='Comma-separated list of tenant IDs to delete'
        )
        delete_parser.add_argument(
            '--reason',
            type=str,
            help='Reason for deleting tenants'
        )
        
        # Import tenants
        import_parser = subparsers.add_parser('import', help='Import tenants from CSV file')
        import_parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Path to CSV file containing tenant data'
        )
        import_parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview import without actually creating tenants'
        )
        
        # Export tenants
        export_parser = subparsers.add_parser('export', help='Export tenants to CSV file')
        export_parser.add_argument(
            '--file',
            type=str,
            help='Path to save CSV file (default: stdout)'
        )
        export_parser.add_argument(
            '--active-only',
            action='store_true',
            help='Export only active tenants'
        )
        
        # Update plans
        update_plan_parser = subparsers.add_parser('update-plan', help='Update subscription plans for multiple tenants')
        update_plan_parser.add_argument(
            '--tenant-ids',
            type=str,
            required=True,
            help='Comma-separated list of tenant IDs to update'
        )
        update_plan_parser.add_argument(
            '--plan',
            type=str,
            required=True,
            choices=['free', 'basic', 'professional', 'enterprise'],
            help='New subscription plan'
        )
        update_plan_parser.add_argument(
            '--reason',
            type=str,
            help='Reason for plan update'
        )
        
        # Common arguments
        parser.add_argument(
            '--admin-user',
            type=str,
            help='Email of admin user performing the operation'
        )
    
    def handle(self, *args, **options):
        operation = options.get('operation')
        admin_user_email = options.get('admin_user')
        
        # Get admin user
        admin_user = None
        if admin_user_email:
            try:
                admin_user = User.objects.get(email=admin_user_email, is_superuser=True)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Admin user {admin_user_email} not found')
                )
                return
        
        if not admin_user:
            self.stdout.write(
                self.style.ERROR('Admin user is required for bulk operations')
            )
            return
        
        # Execute operation
        if operation == 'enable':
            self.enable_tenants(options, admin_user)
        elif operation == 'disable':
            self.disable_tenants(options, admin_user)
        elif operation == 'delete':
            self.delete_tenants(options, admin_user)
        elif operation == 'import':
            self.import_tenants(options, admin_user)
        elif operation == 'export':
            self.export_tenants(options, admin_user)
        elif operation == 'update-plan':
            self.update_plans(options, admin_user)
        else:
            self.stdout.write(
                self.style.ERROR('Operation is required')
            )
    
    def enable_tenants(self, options, admin_user):
        """Enable multiple tenants."""
        tenant_ids_str = options.get('tenant_ids', '')
        reason = options.get('reason', 'Bulk enable operation')
        
        try:
            tenant_ids = [int(id.strip()) for id in tenant_ids_str.split(',')]
        except ValueError:
            self.stdout.write(
                self.style.ERROR('Invalid tenant IDs format')
            )
            return
        
        with transaction.atomic():
            tenants = Tenant.objects.filter(id__in=tenant_ids)
            count = 0
            
            for tenant in tenants:
                if not tenant.is_active:
                    tenant.is_active = True
                    tenant.save()
                    count += 1
                    
                    # Log activity
                    AdminActivityLog.objects.create(
                        admin_user=admin_user,
                        action_type='enable',
                        action_description=f'Enabled tenant: {tenant.name}',
                        tenant=tenant,
                        details={'reason': reason}
                    )
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'Enabled tenant: {tenant.name}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Tenant already active: {tenant.name}')
                    )
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully enabled {count} tenants')
            )
    
    def disable_tenants(self, options, admin_user):
        """Disable multiple tenants."""
        tenant_ids_str = options.get('tenant_ids', '')
        reason = options.get('reason', 'Bulk disable operation')
        
        try:
            tenant_ids = [int(id.strip()) for id in tenant_ids_str.split(',')]
        except ValueError:
            self.stdout.write(
                self.style.ERROR('Invalid tenant IDs format')
            )
            return
        
        with transaction.atomic():
            tenants = Tenant.objects.filter(id__in=tenant_ids)
            count = 0
            
            for tenant in tenants:
                if tenant.is_active:
                    tenant.is_active = False
                    tenant.save()
                    count += 1
                    
                    # Log activity
                    AdminActivityLog.objects.create(
                        admin_user=admin_user,
                        action_type='disable',
                        action_description=f'Disabled tenant: {tenant.name}',
                        tenant=tenant,
                        details={'reason': reason}
                    )
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'Disabled tenant: {tenant.name}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Tenant already disabled: {tenant.name}')
                    )
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully disabled {count} tenants')
            )
    
    def delete_tenants(self, options, admin_user):
        """Soft delete multiple tenants."""
        tenant_ids_str = options.get('tenant_ids', '')
        reason = options.get('reason', 'Bulk delete operation')
        
        try:
            tenant_ids = [int(id.strip()) for id in tenant_ids_str.split(',')]
        except ValueError:
            self.stdout.write(
                self.style.ERROR('Invalid tenant IDs format')
            )
            return
        
        with transaction.atomic():
            tenants = Tenant.objects.filter(id__in=tenant_ids)
            count = 0
            
            for tenant in tenants:
                if not tenant.is_deleted:
                    tenant.soft_delete()
                    count += 1
                    
                    # Log activity
                    AdminActivityLog.objects.create(
                        admin_user=admin_user,
                        action_type='delete',
                        action_description=f'Deleted tenant: {tenant.name}',
                        tenant=tenant,
                        details={'reason': reason}
                    )
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'Deleted tenant: {tenant.name}')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'Tenant already deleted: {tenant.name}')
                    )
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully deleted {count} tenants')
            )
    
    def import_tenants(self, options, admin_user):
        """Import tenants from CSV file."""
        file_path = options.get('file')
        dry_run = options.get('dry_run', False)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                if dry_run:
                    self.stdout.write(
                        self.style.SUCCESS('DRY RUN - Preview of import:')
                    )
                
                count = 0
                errors = []
                
                for row in reader:
                    try:
                        # Validate required fields
                        if not row.get('name'):
                            errors.append(f'Row {count + 1}: Missing name')
                            count += 1
                            continue
                        
                        # Check if tenant already exists
                        if Tenant.objects.filter(name=row['name']).exists():
                            errors.append(f'Row {count + 1}: Tenant {row["name"]} already exists')
                            count += 1
                            continue
                        
                        if not dry_run:
                            # Create tenant
                            tenant = Tenant(
                                name=row['name'],
                                plan=row.get('plan', 'free'),
                                max_users=int(row.get('max_users', 3)),
                                max_storage_mb=int(row.get('max_storage_mb', 100)),
                                is_active=row.get('is_active', 'true').lower() == 'true'
                            )
                            tenant.save()
                            
                            # Create tenant settings
                            settings = TenantSettings(
                                tenant=tenant,
                                company_name=row.get('company_name', tenant.name),
                                default_currency=row.get('default_currency', 'USD'),
                                email_notifications=row.get('email_notifications', 'true').lower() == 'true'
                            )
                            settings.save()
                            
                            # Log activity
                            AdminActivityLog.objects.create(
                                admin_user=admin_user,
                                action_type='create',
                                action_description=f'Imported tenant: {tenant.name}',
                                tenant=tenant,
                                details={'import_source': 'csv', 'row_data': row}
                            )
                        
                        self.stdout.write(
                            self.style.SUCCESS(f'{"[DRY RUN] " if dry_run else ""}Processed tenant: {row["name"]}')
                        )
                        count += 1
                        
                    except Exception as e:
                        errors.append(f'Row {count + 1}: {str(e)}')
                        count += 1
                
                if dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(f'DRY RUN - Would import {count} tenants')
                    )
                    if errors:
                        self.stdout.write(
                            self.style.WARNING(f'DRY RUN - {len(errors)} errors found')
                        )
                        for error in errors[:10]:  # Show first 10 errors
                            self.stdout.write(self.style.WARNING(f'  {error}'))
                else:
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully imported {count} tenants')
                    )
                    if errors:
                        self.stdout.write(
                            self.style.WARNING(f'{len(errors)} errors encountered')
                        )
                        for error in errors[:10]:  # Show first 10 errors
                            self.stdout.write(self.style.WARNING(f'  {error}'))
        
        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f'File not found: {file_path}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error importing tenants: {str(e)}')
            )
    
    def export_tenants(self, options, admin_user):
        """Export tenants to CSV file."""
        file_path = options.get('file')
        active_only = options.get('active_only', False)
        
        # Get tenants
        queryset = Tenant.objects.all()
        if active_only:
            queryset = queryset.filter(is_active=True)
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'id', 'name', 'slug', 'plan', 'max_users', 'max_storage_mb',
            'is_active', 'created_at', 'updated_at', 'user_count'
        ])
        
        # Write tenant data
        for tenant in queryset:
            writer.writerow([
                tenant.id,
                tenant.name,
                tenant.slug,
                tenant.plan,
                tenant.max_users,
                tenant.max_storage_mb,
                tenant.is_active,
                tenant.created_at.isoformat() if tenant.created_at else '',
                tenant.updated_at.isoformat() if tenant.updated_at else '',
                tenant.get_current_user_count()
            ])
        
        # Log activity
        AdminActivityLog.objects.create(
            admin_user=admin_user,
            action_type='export',
            action_description=f'Exported {queryset.count()} tenants',
            details={
                'active_only': active_only,
                'export_count': queryset.count()
            }
        )
        
        # Output CSV
        csv_content = output.getvalue()
        output.close()
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as csvfile:
                    csvfile.write(csv_content)
                self.stdout.write(
                    self.style.SUCCESS(f'Exported {queryset.count()} tenants to {file_path}')
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error writing to file: {str(e)}')
                )
        else:
            # Output to stdout
            self.stdout.write(csv_content)
    
    def update_plans(self, options, admin_user):
        """Update subscription plans for multiple tenants."""
        tenant_ids_str = options.get('tenant_ids', '')
        new_plan = options.get('plan')
        reason = options.get('reason', f'Bulk plan update to {new_plan}')
        
        try:
            tenant_ids = [int(id.strip()) for id in tenant_ids_str.split(',')]
        except ValueError:
            self.stdout.write(
                self.style.ERROR('Invalid tenant IDs format')
            )
            return
        
        with transaction.atomic():
            tenants = Tenant.objects.filter(id__in=tenant_ids)
            count = 0
            
            for tenant in tenants:
                if tenant.plan != new_plan:
                    old_plan = tenant.plan
                    tenant.plan = new_plan
                    tenant.save()
                    count += 1
                    
                    # Log activity
                    AdminActivityLog.objects.create(
                        admin_user=admin_user,
                        action_type='update',
                        action_description=f'Updated plan for {tenant.name}: {old_plan} -> {new_plan}',
                        tenant=tenant,
                        details={
                            'old_plan': old_plan,
                            'new_plan': new_plan,
                            'reason': reason
                        }
                    )
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Updated plan for {tenant.name}: {old_plan} -> {new_plan}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Tenant {tenant.name} already has plan {new_plan}'
                        )
                    )
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully updated plans for {count} tenants')
            )