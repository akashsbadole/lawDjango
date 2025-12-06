import logging
from django.db import models
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import TenantSubscription, SubscriptionEvent, Invoice, Payment
from .services import SubscriptionEmailService

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TenantSubscription)
def subscription_created(sender, instance, created, **kwargs):
    """Handle subscription creation events"""
    if created:
        # Log subscription creation event
        SubscriptionEvent.objects.create(
            tenant=instance.tenant,
            subscription=instance,
            event_type='created',
            description=f"Subscription to {instance.plan.name} created",
            old_status=None,
            new_status=instance.status,
        )
        
        # Send welcome email for new subscriptions
        if instance.status in ['trial', 'active']:
            SubscriptionEmailService.send_welcome_email(instance)


@receiver(pre_save, sender=TenantSubscription)
def subscription_status_change(sender, instance, **kwargs):
    """Handle subscription status changes"""
    if not instance.pk:
        return  # New subscription, handled by post_save
    
    try:
        old_instance = TenantSubscription.objects.get(pk=instance.pk)
        old_status = old_instance.status
        new_status = instance.status
        
        if old_status != new_status:
            # Log status change event
            SubscriptionEvent.objects.create(
                tenant=instance.tenant,
                subscription=instance,
                event_type='status_change',
                description=f"Subscription status changed from {old_instance.get_status_display()} to {instance.get_status_display()}",
                old_status=old_status,
                new_status=new_status,
            )
            
            # Send appropriate emails based on status change
            if old_status in ['trial', 'active'] and new_status == 'cancelled':
                # Subscription was cancelled
                SubscriptionEmailService.send_cancellation_email(instance)
            
            elif old_status == 'cancelled' and new_status in ['trial', 'active']:
                # Subscription was reactivated
                SubscriptionEmailService.send_welcome_email(instance)
    
    except TenantSubscription.DoesNotExist:
        pass  # New subscription, handled by post_save


@receiver(post_save, sender=Invoice)
def invoice_created(sender, instance, created, **kwargs):
    """Handle invoice creation events"""
    if created:
        # Send invoice notification
        SubscriptionEmailService.send_invoice_notification(instance)
        
        # Log invoice creation event
        SubscriptionEvent.objects.create(
            tenant=instance.subscription.tenant,
            subscription=instance.subscription,
            event_type='invoice_created',
            description=f"Invoice #{instance.invoice_number} created for ${instance.total_amount}",
            metadata={
                'invoice_id': instance.id,
                'invoice_number': instance.invoice_number,
                'amount': str(instance.total_amount),
            }
        )


@receiver(pre_save, sender=Invoice)
def invoice_status_change(sender, instance, **kwargs):
    """Handle invoice status changes"""
    if not instance.pk:
        return  # New invoice, handled by post_save
    
    try:
        old_instance = Invoice.objects.get(pk=instance.pk)
        old_status = old_instance.status
        new_status = instance.status
        
        if old_status != new_status:
            # Log invoice status change event
            SubscriptionEvent.objects.create(
                tenant=instance.subscription.tenant,
                subscription=instance.subscription,
                event_type='invoice_status_change',
                description=f"Invoice #{instance.invoice_number} status changed from {old_instance.get_status_display()} to {instance.get_status_display()}",
                old_status=old_status,
                new_status=new_status,
                metadata={
                    'invoice_id': instance.id,
                    'invoice_number': instance.invoice_number,
                }
            )
            
            # Send invoice notification for status changes
            if old_status != 'paid' and new_status == 'paid':
                # Invoice was paid
                SubscriptionEmailService.send_invoice_notification(instance)
            elif old_status in ['pending', 'paid'] and new_status == 'overdue':
                # Invoice became overdue
                SubscriptionEmailService.send_invoice_notification(instance)
    
    except Invoice.DoesNotExist:
        pass  # New invoice, handled by post_save


@receiver(post_save, sender=Payment)
def payment_created(sender, instance, created, **kwargs):
    """Handle payment creation events"""
    if created:
        # Update invoice status if payment is successful
        if instance.status == 'success' and instance.invoice:
            invoice = instance.invoice
            
            # Check if this payment fully covers the invoice
            total_paid = Payment.objects.filter(
                invoice=invoice,
                status='success'
            ).aggregate(
                total=models.Sum('amount')
            )['total'] or 0
            
            if total_paid >= invoice.total_amount:
                invoice.status = 'paid'
                invoice.paid_date = timezone.now().date()
                invoice.save(update_fields=['status', 'paid_date'])
        
        # Log payment event
        SubscriptionEvent.objects.create(
            tenant=instance.invoice.subscription.tenant if instance.invoice else None,
            subscription=instance.invoice.subscription if instance.invoice else None,
            event_type='payment_processed',
            description=f"Payment of ${instance.amount} processed via {instance.payment_method}",
            metadata={
                'payment_id': instance.id,
                'amount': str(instance.amount),
                'payment_method': instance.payment_method,
                'status': instance.status,
            }
        )