from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from tenants.models import Tenant
from subscriptions.models import TenantSubscription, UsageRecord
from subscriptions.utils import get_usage_percentage
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send usage notifications to tenants approaching their limits'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in dry-run mode without sending emails',
        )
        parser.add_argument(
            '--threshold',
            type=float,
            default=0.8,
            help='Usage threshold for sending notifications (default: 0.8 or 80%)',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        threshold = options['threshold']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in dry-run mode'))
        
        self.stdout.write(f"Checking usage with threshold: {threshold * 100}%")
        
        # Get all tenants with active subscriptions
        tenants_with_active_subscriptions = Tenant.objects.filter(
            subscriptions__status=TenantSubscription.ACTIVE
        ).distinct()
        
        notifications_sent = 0
        
        for tenant in tenants_with_active_subscriptions:
            subscription = TenantSubscription.objects.current_for_tenant(tenant)
            
            if not subscription or not subscription.plan:
                continue
            
            # Check usage for each feature
            usage_notifications = []
            
            # Check user count
            if subscription.plan.max_users:
                user_usage = get_usage_percentage(tenant, 'users', subscription.plan.max_users)
                if user_usage >= threshold:
                    usage_notifications.append({
                        'feature': 'Users',
                        'current': tenant.get_current_user_count(),
                        'limit': subscription.plan.max_users,
                        'percentage': user_usage * 100
                    })
            
            # Check storage usage
            if subscription.plan.max_storage_mb:
                storage_usage = get_usage_percentage(tenant, 'storage', subscription.plan.max_storage_mb)
                if storage_usage >= threshold:
                    usage_notifications.append({
                        'feature': 'Storage',
                        'current': round(tenant.get_storage_used() / (1024 * 1024), 2),  # Convert to MB
                        'limit': subscription.plan.max_storage_mb,
                        'percentage': storage_usage * 100
                    })
            
            # Check other features from usage records
            usage_records = UsageRecord.objects.for_tenant(tenant).select_related('feature')
            for record in usage_records:
                if record.feature.code in ['users', 'storage']:
                    continue  # Already checked above
                
                if record.feature.limit_value:
                    usage_percentage = get_usage_percentage(
                        tenant, record.feature.code, record.feature.limit_value
                    )
                    if usage_percentage >= threshold:
                        usage_notifications.append({
                            'feature': record.feature.name,
                            'current': record.current_usage,
                            'limit': record.feature.limit_value,
                            'percentage': usage_percentage * 100
                        })
            
            # Send notification if there are usage alerts
            if usage_notifications:
                if not dry_run:
                    self._send_usage_notification(tenant, usage_notifications)
                
                self.stdout.write(
                    self.style.NOTICE(
                        f"Sending usage notification to {tenant.name} for {len(usage_notifications)} features"
                    )
                )
                
                for notification in usage_notifications:
                    self.stdout.write(
                        f"  - {notification['feature']}: {notification['current']}/{notification['limit']} ({notification['percentage']:.1f}%)"
                    )
                
                notifications_sent += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Usage notification check completed. {notifications_sent} notifications would be sent."
            )
        )
    
    def _send_usage_notification(self, tenant, usage_notifications):
        """Send usage notification email to tenant admin"""
        try:
            # Get tenant admin users
            from accounts.models import User
            admin_users = User.objects.filter(
                tenant=tenant,
                role__in=['admin', 'owner']
            )
            
            if not admin_users:
                logger.warning(f"No admin users found for tenant {tenant.name}")
                return
            
            # Prepare email content
            subject = f"Usage Alert for {tenant.name}"
            
            # Build notification message
            message_lines = [
                f"Hello,",
                "",
                f"This is an automated notification to inform you that your tenant '{tenant.name}' is approaching usage limits:",
                ""
            ]
            
            for notification in usage_notifications:
                message_lines.append(
                    f"- {notification['feature']}: {notification['current']}/{notification['limit']} ({notification['percentage']:.1f}%)"
                )
            
            message_lines.extend([
                "",
                "Please consider upgrading your subscription plan to avoid service interruption.",
                "",
                "You can manage your subscription at:",
                f"{settings.SITE_URL}/subscriptions/",
                "",
                "Thank you,",
                "The Law Firm Management System Team"
            ])
            
            message = "\n".join(message_lines)
            
            # Send email to all admin users
            recipient_emails = [user.email for user in admin_users if user.email]
            
            if recipient_emails:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                    recipient_list=recipient_emails,
                    fail_silently=False,
                )
                logger.info(f"Usage notification sent to {tenant.name}")
            
        except Exception as e:
            logger.error(f"Error sending usage notification to {tenant.name}: {str(e)}")