import logging
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from .models import TenantSubscription, UsageRecord, Invoice

logger = logging.getLogger(__name__)


class SubscriptionEmailService:
    """Service for sending subscription-related emails"""
    
    @staticmethod
    def send_welcome_email(subscription):
        """Send welcome email to new subscribers"""
        try:
            tenant = subscription.tenant
            plan_features = subscription.plan.plan_features.select_related('feature').all()
            
            # Get site URL for email links
            site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            
            # Render email templates
            html_message = render_to_string('subscriptions/welcome_email.html', {
                'tenant': tenant,
                'subscription': subscription,
                'plan_features': plan_features,
                'site_url': site_url,
            })
            
            text_message = render_to_string('subscriptions/welcome_email.txt', {
                'tenant': tenant,
                'subscription': subscription,
                'plan_features': plan_features,
                'site_url': site_url,
            })
            
            # Send email
            send_mail(
                subject=f'Welcome to {tenant.name} - {subscription.plan.name} Plan',
                message=text_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@lawfirm.com'),
                recipient_list=[tenant.owner.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Welcome email sent to {tenant.owner.email} for subscription {subscription.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send welcome email: {str(e)}")
            return False
    
    @staticmethod
    def send_renewal_reminder(subscription, days_until_renewal):
        """Send renewal reminder email"""
        try:
            tenant = subscription.tenant
            current_plan_features = subscription.plan.plan_features.select_related('feature').all()
            
            # Get available plans for upgrade options
            available_plans = subscription.plan.__class__.objects.filter(
                is_active=True,
                price__gt=subscription.plan.price
            ).order_by('price')
            
            # Get features for available plans
            plan_features = {}
            for plan in available_plans:
                plan_features[plan.id] = plan.plan_features.select_related('feature').all()
            
            # Get payment methods
            payment_methods = tenant.payment_methods.filter(is_active=True)
            
            # Get site URL for email links
            site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            
            # Render email templates
            html_message = render_to_string('subscriptions/renewal_reminder_email.html', {
                'tenant': tenant,
                'subscription': subscription,
                'days_until_renewal': days_until_renewal,
                'current_plan_features': current_plan_features,
                'available_plans': available_plans,
                'plan_features': plan_features,
                'payment_methods': payment_methods,
                'site_url': site_url,
            })
            
            text_message = render_to_string('subscriptions/renewal_reminder_email.txt', {
                'tenant': tenant,
                'subscription': subscription,
                'days_until_renewal': days_until_renewal,
                'current_plan_features': current_plan_features,
                'available_plans': available_plans,
                'plan_features': plan_features,
                'payment_methods': payment_methods,
                'site_url': site_url,
            })
            
            # Send email
            send_mail(
                subject=f'Subscription Renewal Reminder - {tenant.name}',
                message=text_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@lawfirm.com'),
                recipient_list=[tenant.owner.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Renewal reminder sent to {tenant.owner.email} for subscription {subscription.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send renewal reminder: {str(e)}")
            return False
    
    @staticmethod
    def send_cancellation_email(subscription):
        """Send cancellation confirmation email"""
        try:
            tenant = subscription.tenant
            days_remaining = (subscription.end_date - timezone.now().date()).days
            
            # Get site URL for email links
            site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            
            # Render email templates
            html_message = render_to_string('subscriptions/cancellation_email.html', {
                'tenant': tenant,
                'subscription': subscription,
                'days_remaining': days_remaining,
                'site_url': site_url,
            })
            
            text_message = render_to_string('subscriptions/cancellation_email.txt', {
                'tenant': tenant,
                'subscription': subscription,
                'days_remaining': days_remaining,
                'site_url': site_url,
            })
            
            # Send email
            send_mail(
                subject=f'Subscription Cancelled - {tenant.name}',
                message=text_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@lawfirm.com'),
                recipient_list=[tenant.owner.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Cancellation email sent to {tenant.owner.email} for subscription {subscription.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send cancellation email: {str(e)}")
            return False
    
    @staticmethod
    def send_usage_notification(tenant, usage_records, notification_type='info'):
        """Send usage notification email"""
        try:
            subscription = TenantSubscription.objects.filter(
                tenant=tenant,
                status__in=['trial', 'active']
            ).first()
            
            if not subscription:
                return False
            
            # Calculate usage percentages
            for record in usage_records:
                if record.limit > 0:
                    record.usage_percentage = (record.current_usage / record.limit) * 100
                else:
                    record.usage_percentage = 0
            
            # Get site URL for email links
            site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            
            # Render email templates
            html_message = render_to_string('subscriptions/usage_notification_email.html', {
                'tenant': tenant,
                'subscription': subscription,
                'usage_records': usage_records,
                'notification_type': notification_type,
                'site_url': site_url,
            })
            
            text_message = render_to_string('subscriptions/usage_notification_email.txt', {
                'tenant': tenant,
                'subscription': subscription,
                'usage_records': usage_records,
                'notification_type': notification_type,
                'site_url': site_url,
            })
            
            # Determine subject based on notification type
            if notification_type == 'warning':
                subject = f'Usage Warning - {tenant.name}'
            elif notification_type == 'critical':
                subject = f'Critical Usage Alert - {tenant.name}'
            else:
                subject = f'Usage Summary - {tenant.name}'
            
            # Send email
            send_mail(
                subject=subject,
                message=text_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@lawfirm.com'),
                recipient_list=[tenant.owner.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Usage notification ({notification_type}) sent to {tenant.owner.email} for tenant {tenant.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send usage notification: {str(e)}")
            return False
    
    @staticmethod
    def send_invoice_notification(invoice):
        """Send invoice notification email"""
        try:
            tenant = invoice.subscription.tenant
            
            # Calculate days overdue if applicable
            days_overdue = None
            if invoice.status == 'overdue' and invoice.due_date:
                days_overdue = (timezone.now().date() - invoice.due_date).days
            
            # Get site URL for email links
            site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
            
            # Render email templates
            html_message = render_to_string('subscriptions/invoice_email.html', {
                'tenant': tenant,
                'invoice': invoice,
                'days_overdue': days_overdue,
                'site_url': site_url,
            })
            
            text_message = render_to_string('subscriptions/invoice_email.txt', {
                'tenant': tenant,
                'invoice': invoice,
                'days_overdue': days_overdue,
                'site_url': site_url,
            })
            
            # Determine subject based on invoice status
            if invoice.status == 'paid':
                subject = f'Payment Confirmation - Invoice #{invoice.invoice_number}'
            elif invoice.status == 'overdue':
                subject = f'Payment Overdue - Invoice #{invoice.invoice_number}'
            else:
                subject = f'Invoice Ready - #{invoice.invoice_number}'
            
            # Send email
            send_mail(
                subject=subject,
                message=text_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@lawfirm.com'),
                recipient_list=[tenant.owner.email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Invoice notification sent to {tenant.owner.email} for invoice {invoice.id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send invoice notification: {str(e)}")
            return False


class SubscriptionService:
    """Service for managing subscription operations"""
    
    @staticmethod
    def check_and_update_usage(tenant, feature_code, usage_delta=1):
        """Check and update usage for a specific feature"""
        try:
            # Get or create usage record
            usage_record, created = UsageRecord.objects.get_or_create(
                tenant=tenant,
                feature__code=feature_code,
                defaults={
                    'current_usage': 0,
                    'period_start': timezone.now().date().replace(day=1),
                    'period_end': (timezone.now().date().replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
                }
            )
            
            # Get subscription to check limits
            subscription = TenantSubscription.objects.filter(
                tenant=tenant,
                status__in=['trial', 'active']
            ).first()
            
            if not subscription:
                return {'success': False, 'message': 'No active subscription found'}
            
            # Get plan feature for limits
            plan_feature = subscription.plan.plan_features.filter(
                feature__code=feature_code
            ).first()
            
            if not plan_feature:
                return {'success': False, 'message': 'Feature not found in subscription plan'}
            
            # Check if usage would exceed limit
            new_usage = usage_record.current_usage + usage_delta
            limit = plan_feature.value if plan_feature.value.isdigit() else 0
            
            if limit > 0 and new_usage > limit:
                return {
                    'success': False,
                    'message': f'Usage limit exceeded for {feature_code}',
                    'current_usage': usage_record.current_usage,
                    'limit': limit,
                    'usage_delta': usage_delta
                }
            
            # Update usage
            usage_record.current_usage = new_usage
            usage_record.save()
            
            # Check if we should send a notification
            usage_percentage = (new_usage / limit) * 100 if limit > 0 else 0
            
            if usage_percentage >= 90:
                SubscriptionEmailService.send_usage_notification(
                    tenant, [usage_record], 'critical'
                )
            elif usage_percentage >= 75:
                SubscriptionEmailService.send_usage_notification(
                    tenant, [usage_record], 'warning'
                )
            
            return {
                'success': True,
                'message': 'Usage updated successfully',
                'current_usage': usage_record.current_usage,
                'limit': limit,
                'usage_percentage': usage_percentage
            }
            
        except Exception as e:
            logger.error(f"Error checking/updating usage: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    @staticmethod
    def can_access_feature(tenant, feature_code):
        """Check if tenant can access a specific feature"""
        try:
            # Get active subscription
            subscription = TenantSubscription.objects.filter(
                tenant=tenant,
                status__in=['trial', 'active']
            ).first()
            
            if not subscription:
                return {'can_access': False, 'reason': 'No active subscription'}
            
            # Check if feature is included in plan
            plan_feature = subscription.plan.plan_features.filter(
                feature__code=feature_code,
                is_included=True
            ).first()
            
            if not plan_feature:
                return {'can_access': False, 'reason': 'Feature not included in plan'}
            
            # Check usage limits
            usage_record = UsageRecord.objects.filter(
                tenant=tenant,
                feature__code=feature_code
            ).first()
            
            if usage_record and plan_feature.value and plan_feature.value.isdigit():
                limit = int(plan_feature.value)
                if usage_record.current_usage >= limit:
                    return {
                        'can_access': False,
                        'reason': 'Usage limit exceeded',
                        'current_usage': usage_record.current_usage,
                        'limit': limit
                    }
            
            return {'can_access': True}
            
        except Exception as e:
            logger.error(f"Error checking feature access: {str(e)}")
            return {'can_access': False, 'reason': str(e)}
    
    @staticmethod
    def get_subscription_status(tenant):
        """Get comprehensive subscription status for a tenant"""
        try:
            subscription = TenantSubscription.objects.filter(
                tenant=tenant
            ).first()
            
            if not subscription:
                return {
                    'status': 'none',
                    'message': 'No subscription found'
                }
            
            # Get usage records
            usage_records = UsageRecord.objects.filter(tenant=tenant)
            
            # Calculate usage percentages
            usage_summary = []
            for record in usage_records:
                plan_feature = subscription.plan.plan_features.filter(
                    feature=record.feature
                ).first()
                
                if plan_feature and plan_feature.value and plan_feature.value.isdigit():
                    limit = int(plan_feature.value)
                    usage_percentage = (record.current_usage / limit) * 100 if limit > 0 else 0
                    
                    usage_summary.append({
                        'feature_name': record.feature.name,
                        'feature_code': record.feature.code,
                        'current_usage': record.current_usage,
                        'limit': limit,
                        'usage_percentage': usage_percentage,
                        'status': 'critical' if usage_percentage >= 90 else 'warning' if usage_percentage >= 75 else 'ok'
                    })
            
            return {
                'status': subscription.status,
                'plan_name': subscription.plan.name,
                'start_date': subscription.start_date,
                'end_date': subscription.end_date,
                'cancelled_at': subscription.cancelled_at,
                'days_remaining': (subscription.end_date - timezone.now().date()).days if subscription.end_date else None,
                'usage_summary': usage_summary,
                'is_trial': subscription.status == 'trial',
                'is_active': subscription.status == 'active',
                'is_cancelled': subscription.status == 'cancelled',
                'is_expired': subscription.status == 'expired'
            }
            
        except Exception as e:
            logger.error(f"Error getting subscription status: {str(e)}")
            return {'status': 'error', 'message': str(e)}