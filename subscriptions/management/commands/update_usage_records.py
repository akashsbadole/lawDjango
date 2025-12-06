from django.core.management.base import BaseCommand
from django.utils import timezone
from tenants.models import Tenant
from subscriptions.models import SubscriptionFeature, UsageRecord
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update usage records for all tenants'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Update usage records for a specific tenant ID',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in dry-run mode without making changes',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        tenant_id = options['tenant_id']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in dry-run mode'))
        
        # Get tenants to update
        if tenant_id:
            try:
                tenants = [Tenant.objects.get(id=tenant_id)]
                self.stdout.write(f"Updating usage records for tenant ID {tenant_id}")
            except Tenant.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Tenant with ID {tenant_id} does not exist")
                )
                return
        else:
            tenants = Tenant.objects.all()
            self.stdout.write(f"Updating usage records for all {tenants.count()} tenants")
        
        # Get all features that need tracking
        features = SubscriptionFeature.objects.all()
        
        updated_count = 0
        
        for tenant in tenants:
            self.stdout.write(f"Updating usage for tenant: {tenant.name}")
            
            for feature in features:
                try:
                    # Calculate current usage based on feature type
                    if feature.code == 'users':
                        current_usage = self._get_user_usage(tenant)
                    elif feature.code == 'storage':
                        current_usage = self._get_storage_usage(tenant)
                    elif feature.code == 'cases':
                        current_usage = self._get_case_usage(tenant)
                    elif feature.code == 'documents':
                        current_usage = self._get_document_usage(tenant)
                    elif feature.code == 'clients':
                        current_usage = self._get_client_usage(tenant)
                    else:
                        # Skip unknown features
                        continue
                    
                    # Get or create usage record
                    usage_record, created = UsageRecord.objects.get_or_create(
                        tenant=tenant,
                        feature=feature,
                        defaults={
                            'current_usage': current_usage,
                            'period_start': timezone.now().replace(day=1),
                            'period_end': timezone.now().replace(day=28),
                        }
                    )
                    
                    if not created:
                        # Update existing record
                        if not dry_run:
                            usage_record.current_usage = current_usage
                            usage_record.save()
                    
                    if created or usage_record.current_usage != current_usage:
                        updated_count += 1
                        self.stdout.write(
                            f"  - {feature.name}: {current_usage} (previous: {usage_record.current_usage if not created else 'N/A'})"
                        )
                
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Error updating usage for feature {feature.name}: {str(e)}"
                        )
                    )
                    logger.error(f"Error updating usage for {feature.name}: {str(e)}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Usage records update completed. {updated_count} records updated."
            )
        )
    
    def _get_user_usage(self, tenant):
        """Get current user count for tenant"""
        from accounts.models import User
        return User.objects.filter(tenant=tenant).count()
    
    def _get_storage_usage(self, tenant):
        """Get current storage usage in MB for tenant"""
        try:
            from documents.models import Document
            storage_bytes = Document.objects.get_storage_usage(tenant)
            return round(storage_bytes / (1024 * 1024), 2)  # Convert to MB
        except:
            return 0
    
    def _get_case_usage(self, tenant):
        """Get current case count for tenant"""
        try:
            from cases.models import Case
            return Case.objects.active_for_tenant(tenant).count()
        except:
            return 0
    
    def _get_document_usage(self, tenant):
        """Get current document count for tenant"""
        try:
            from documents.models import Document
            return Document.objects.for_tenant(tenant).count()
        except:
            return 0
    
    def _get_client_usage(self, tenant):
        """Get current client count for tenant"""
        try:
            from clients.models import Client
            return Client.objects.for_tenant(tenant).count()
        except:
            return 0