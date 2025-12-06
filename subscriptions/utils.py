import logging
from django.conf import settings
from decimal import Decimal

logger = logging.getLogger(__name__)


def get_stripe_client():
    """
    Get Stripe client instance.
    Placeholder implementation - in production, this would use actual Stripe API keys.
    """
    try:
        import stripe
        stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', 'sk_test_placeholder')
        return stripe
    except ImportError:
        logger.warning("Stripe library not installed. Using placeholder implementation.")
        return None


def create_stripe_payment_intent(amount, currency, description):
    """
    Create a Stripe payment intent.
    Placeholder implementation - in production, this would create an actual Stripe payment intent.
    """
    stripe = get_stripe_client()
    if not stripe:
        # Return a placeholder payment intent ID
        return f"pi_placeholder_{amount}_{currency}"
    
    try:
        # Create payment intent
        intent = stripe.PaymentIntent.create(
            amount=int(amount * 100),  # Stripe expects amount in cents
            currency=currency.lower(),
            description=description,
            payment_method_types=['card'],
            confirm=False,
        )
        return intent.id
    except Exception as e:
        logger.error(f"Error creating Stripe payment intent: {str(e)}")
        # Return placeholder ID on error
        return f"pi_error_{amount}_{currency}"


def process_stripe_webhook(payload, sig_header):
    """
    Process Stripe webhook.
    Placeholder implementation - in production, this would verify and process actual Stripe webhooks.
    """
    stripe = get_stripe_client()
    if not stripe:
        logger.warning("Stripe library not installed. Cannot process webhook.")
        return None
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, getattr(settings, 'STRIPE_WEBHOOK_SECRET', 'whsec_placeholder')
        )
        
        # Process different event types
        if event.type == 'payment_intent.succeeded':
            payment_intent = event.data.object
            handle_successful_payment(payment_intent)
        elif event.type == 'payment_intent.payment_failed':
            payment_intent = event.data.object
            handle_failed_payment(payment_intent)
        elif event.type == 'invoice.payment_succeeded':
            invoice = event.data.object
            handle_invoice_payment(invoice)
        elif event.type == 'invoice.payment_failed':
            invoice = event.data.object
            handle_invoice_payment_failed(invoice)
        elif event.type == 'customer.subscription.deleted':
            subscription = event.data.object
            handle_subscription_cancellation(subscription)
        elif event.type == 'invoice.upcoming':
            invoice = event.data.object
            handle_upcoming_invoice(invoice)
        
        return event
        
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {str(e)}")
        return None


def handle_successful_payment(payment_intent):
    """
    Handle successful payment intent.
    """
    from .models import Payment, Invoice
    
    try:
        # Find invoice by payment intent metadata
        invoice = Invoice.objects.filter(
            stripe_payment_intent_id=payment_intent.id
        ).first()
        
        if invoice:
            # Update payment record
            payment = Payment.objects.filter(
                stripe_payment_intent_id=payment_intent.id
            ).first()
            
            if payment:
                payment.status = 'completed'
                payment.transaction_id = payment_intent.charges.data[0].id if payment_intent.charges.data else None
                payment.save()
                
                # Update invoice status
                if invoice.total_amount <= payment.amount:
                    invoice.status = 'paid'
                invoice.save()
                
                logger.info(f"Payment {payment.id} completed successfully for invoice {invoice.invoice_number}")
    
    except Exception as e:
        logger.error(f"Error handling successful payment: {str(e)}")


def handle_failed_payment(payment_intent):
    """
    Handle failed payment intent.
    """
    from .models import Payment, Invoice
    
    try:
        # Find invoice by payment intent metadata
        invoice = Invoice.objects.filter(
            stripe_payment_intent_id=payment_intent.id
        ).first()
        
        if invoice:
            # Update payment record
            payment = Payment.objects.filter(
                stripe_payment_intent_id=payment_intent.id
            ).first()
            
            if payment:
                payment.status = 'failed'
                payment.notes = f"Payment failed: {payment_intent.last_payment_error.message if payment_intent.last_payment_error else 'Unknown error'}"
                payment.save()
                
                logger.warning(f"Payment {payment.id} failed for invoice {invoice.invoice_number}")
    
    except Exception as e:
        logger.error(f"Error handling failed payment: {str(e)}")


def handle_invoice_payment(invoice):
    """
    Handle successful invoice payment from Stripe.
    """
    from .models import Payment, TenantSubscription
    
    try:
        # Find subscription by Stripe subscription ID
        subscription = TenantSubscription.objects.filter(
            stripe_subscription_id=invoice.subscription
        ).first()
        
        if subscription:
            # Create payment record
            payment = Payment.objects.create(
                invoice=None,  # Will be linked later
                amount=Decimal(invoice.total_paid) / 100,  # Convert from cents
                payment_method='stripe',
                status='completed',
                transaction_id=invoice.charge,
                stripe_payment_intent_id=invoice.payment_intent
            )
            
            logger.info(f"Payment {payment.id} recorded for Stripe invoice {invoice.id}")
    
    except Exception as e:
        logger.error(f"Error handling invoice payment: {str(e)}")


def handle_invoice_payment_failed(invoice):
    """
    Handle failed invoice payment from Stripe.
    """
    from .models import TenantSubscription
    
    try:
        # Find subscription by Stripe subscription ID
        subscription = TenantSubscription.objects.filter(
            stripe_subscription_id=invoice.subscription
        ).first()
        
        if subscription:
            # Update subscription status
            subscription.status = 'past_due'
            subscription.save()
            
            logger.warning(f"Subscription {subscription.id} marked as past due")
    
    except Exception as e:
        logger.error(f"Error handling invoice payment failure: {str(e)}")


def handle_subscription_cancellation(subscription):
    """
    Handle subscription cancellation from Stripe.
    """
    from .models import TenantSubscription, SubscriptionEvent
    
    try:
        # Find subscription by Stripe subscription ID
        tenant_subscription = TenantSubscription.objects.filter(
            stripe_subscription_id=subscription.id
        ).first()
        
        if tenant_subscription:
            # Update subscription status
            tenant_subscription.status = 'cancelled'
            tenant_subscription.cancelled_at = subscription.canceled_at
            tenant_subscription.auto_renew = False
            tenant_subscription.save()
            
            # Log event
            SubscriptionEvent.objects.log_event(
                tenant=tenant_subscription.tenant,
                subscription=tenant_subscription,
                event_type='cancelled',
                description="Subscription cancelled via Stripe webhook"
            )
            
            logger.info(f"Subscription {tenant_subscription.id} cancelled via Stripe")
    
    except Exception as e:
        logger.error(f"Error handling subscription cancellation: {str(e)}")


def handle_upcoming_invoice(invoice):
    """
    Handle upcoming invoice notification from Stripe.
    """
    from .models import Invoice
    
    try:
        # Find subscription by Stripe subscription ID
        tenant_subscription = TenantSubscription.objects.filter(
            stripe_subscription_id=invoice.subscription
        ).first()
        
        if tenant_subscription:
            # Create invoice record
            invoice_number = f"STR-{invoice.id}"
            Invoice.objects.create(
                invoice_number=invoice_number,
                tenant=tenant_subscription.tenant,
                subscription=tenant_subscription,
                invoice_type='subscription',
                issue_date=timezone.now().date(),
                due_date=timezone.now().date() + timezone.timedelta(days=invoice.days_until_due),
                subtotal=Decimal(invoice.subtotal) / 100,  # Convert from cents
                tax_rate=Decimal(invoice.tax) / 100,  # Convert from cents
                tax_amount=Decimal(invoice.tax) / 100,  # Convert from cents
                total_amount=Decimal(invoice.total) / 100,  # Convert from cents
                status='draft',
                stripe_invoice_id=invoice.id
            )
            
            logger.info(f"Upcoming invoice {invoice_number} created for subscription {tenant_subscription.id}")
    
    except Exception as e:
        logger.error(f"Error handling upcoming invoice: {str(e)}")


def calculate_prorated_amount(plan, days_used, days_in_period):
    """
    Calculate prorated amount for plan changes.
    """
    if not plan or days_in_period == 0:
        return Decimal('0.00')
    
    # Calculate daily rate
    if plan.billing_cycle == 'monthly':
        daily_rate = plan.price / 30
    elif plan.billing_cycle == 'yearly':
        daily_rate = plan.price / 365
    else:
        daily_rate = plan.price / 30  # Default to monthly
    
    # Calculate prorated amount
    prorated_amount = daily_rate * (days_in_period - days_used)
    
    # Round to 2 decimal places
    return prorated_amount.quantize(Decimal('0.01'))


def generate_invoice_number(prefix='INV'):
    """
    Generate unique invoice number.
    """
    from django.utils import timezone
    from .models import Invoice
    
    # Get current date in YYYYMMDD format
    date_str = timezone.now().strftime('%Y%m%d')
    
    # Get count of invoices for today
    today_count = Invoice.objects.filter(
        invoice_number__startswith=f"{prefix}-{date_str}"
    ).count()
    
    # Generate invoice number
    invoice_number = f"{prefix}-{date_str}-{today_count + 1:04d}"
    
    return invoice_number


def send_usage_notification(tenant, feature, usage_percentage):
    """
    Send usage notification to tenant.
    Placeholder implementation - in production, this would send actual notifications.
    """
    logger.info(
        f"Usage notification for {tenant.name}: {feature.name} at {usage_percentage:.1f}%"
    )
    
    # In production, this would send email, SMS, or in-app notification
    # For now, we just log it


def check_subscription_limits(tenant):
    """
    Check if tenant is approaching or exceeding subscription limits.
    """
    from .models import UsageRecord, SubscriptionFeature
    
    subscription = tenant.get_current_subscription()
    if not subscription or not subscription.plan:
        return []
    
    notifications = []
    
    # Check user limit
    current_users = tenant.get_current_user_count()
    if current_users >= subscription.plan.max_users:
        notifications.append({
            'type': 'user_limit',
            'message': f"You've reached your user limit of {subscription.plan.max_users}",
            'severity': 'error'
        })
    elif current_users >= subscription.plan.max_users * 0.9:
        notifications.append({
            'type': 'user_warning',
            'message': f"You're approaching your user limit ({current_users}/{subscription.plan.max_users})",
            'severity': 'warning'
        })
    
    # Check storage limit
    storage_used = tenant.get_storage_used()
    storage_limit = subscription.plan.max_storage_mb
    if storage_limit > 0:
        if storage_used >= storage_limit:
            notifications.append({
                'type': 'storage_limit',
                'message': f"You've reached your storage limit of {storage_limit}MB",
                'severity': 'error'
            })
        elif storage_used >= storage_limit * 0.9:
            notifications.append({
                'type': 'storage_warning',
                'message': f"You're approaching your storage limit ({storage_used}/{storage_limit}MB)",
                'severity': 'warning'
            })
    
    # Check feature usage
    current_month = timezone.now().replace(day=1)
    usage_records = UsageRecord.objects.filter(
        tenant=tenant,
        period_start__gte=current_month,
        limit__isnull=False
    ).select_related('feature')
    
    for record in usage_records:
        if record.is_over_limit:
            notifications.append({
                'type': 'feature_limit',
                'message': f"You've exceeded the limit for {record.feature.name}",
                'severity': 'error'
            })
        elif record.usage_percentage >= 90:
            notifications.append({
                'type': 'feature_warning',
                'message': f"You're approaching the limit for {record.feature.name} ({record.usage_percentage:.1f}%)",
                'severity': 'warning'
            })
    
    return notifications