from django.core.management.base import BaseCommand
from django.utils import timezone
from tenants.models import Tenant
from subscriptions.models import TenantSubscription, SubscriptionEvent
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Check subscription status for all tenants and update accordingly'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in dry-run mode without making changes',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in dry-run mode'))
        
        today = timezone.now().date()
        
        # Get all tenants with subscriptions
        tenants_with_subscriptions = Tenant.objects.filter(
            subscriptions__isnull=False
        ).distinct()
        
        self.stdout.write(f"Checking subscriptions for {tenants_with_subscriptions.count()} tenants")
        
        for tenant in tenants_with_subscriptions:
            subscription = TenantSubscription.objects.current_for_tenant(tenant)
            
            if not subscription:
                self.stdout.write(f"No active subscription found for tenant: {tenant.name}")
                continue
            
            # Check if subscription is expired
            if subscription.end_date and subscription.end_date < today:
                if subscription.status != TenantSubscription.EXPIRED:
                    if not dry_run:
                        subscription.status = TenantSubscription.EXPIRED
                        subscription.save()
                        
                        # Log the event
                        SubscriptionEvent.objects.create(
                            tenant=tenant,
                            subscription=subscription,
                            event_type=SubscriptionEvent.SUBSCRIPTION_EXPIRED,
                            description=f"Subscription expired on {subscription.end_date}"
                        )
                    
                    self.stdout.write(
                        self.style.WARNING(
                            f"Subscription EXPIRED for tenant: {tenant.name} (ended: {subscription.end_date})"
                        )
                    )
                continue
            
            # Check if subscription is past due
            if subscription.end_date and subscription.end_date <= today:
                if subscription.status == TenantSubscription.ACTIVE:
                    if not dry_run:
                        subscription.status = TenantSubscription.PAST_DUE
                        subscription.save()
                        
                        # Log the event
                        SubscriptionEvent.objects.create(
                            tenant=tenant,
                            subscription=subscription,
                            event_type=SubscriptionEvent.PAYMENT_FAILED,
                            description=f"Subscription became past due on {subscription.end_date}"
                        )
                    
                    self.stdout.write(
                        self.style.WARNING(
                            f"Subscription PAST DUE for tenant: {tenant.name} (due: {subscription.end_date})"
                        )
                    )
            
            # Check for trial expiring soon
            if subscription.status == TenantSubscription.TRIAL and subscription.end_date:
                days_until_expiry = (subscription.end_date - today).days
                
                if days_until_expiry <= 3 and days_until_expiry >= 0:
                    self.stdout.write(
                        self.style.NOTICE(
                            f"Trial for tenant: {tenant.name} expires in {days_until_expiry} days"
                        )
                    )
        
        self.stdout.write(self.style.SUCCESS('Subscription status check completed'))