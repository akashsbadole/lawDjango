from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from tenants.models import Tenant
from subscriptions.models import TenantSubscription, Invoice, Payment, SubscriptionEvent
from subscriptions.utils import create_stripe_payment_intent
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process recurring payments for subscriptions due for renewal'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in dry-run mode without processing payments',
        )
        parser.add_argument(
            '--days-ahead',
            type=int,
            default=3,
            help='Process payments due within this many days (default: 3)',
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        days_ahead = options['days_ahead']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Running in dry-run mode'))
        
        today = timezone.now().date()
        end_date = today + timezone.timedelta(days=days_ahead)
        
        self.stdout.write(f"Processing recurring payments due between {today} and {end_date}")
        
        # Get subscriptions due for renewal
        subscriptions_due = TenantSubscription.objects.filter(
            status__in=[TenantSubscription.ACTIVE, TenantSubscription.TRIAL],
            end_date__gte=today,
            end_date__lte=end_date,
            auto_renew=True
        )
        
        self.stdout.write(f"Found {subscriptions_due.count()} subscriptions due for renewal")
        
        successful_renewals = 0
        failed_renewals = 0
        
        for subscription in subscriptions_due:
            tenant = subscription.tenant
            self.stdout.write(f"Processing renewal for {tenant.name}...")
            
            try:
                with transaction.atomic():
                    if not dry_run:
                        # Create new invoice
                        invoice = Invoice.objects.create(
                            tenant=tenant,
                            subscription=subscription,
                            amount=subscription.plan.price,
                            description=f"Subscription renewal - {subscription.plan.name}",
                            due_date=today,
                            status=Invoice.PENDING
                        )
                        
                        # Get default payment method
                        payment_method = subscription.payment_method
                        if not payment_method:
                            # Try to get default payment method for tenant
                            from subscriptions.models import PaymentMethod
                            payment_method = PaymentMethod.objects.filter(
                                tenant=tenant,
                                is_default=True
                            ).first()
                        
                        if not payment_method:
                            self.stdout.write(
                                self.style.ERROR(
                                    f"No payment method found for {tenant.name}. Skipping renewal."
                                )
                            )
                            failed_renewals += 1
                            continue
                        
                        # Process payment (placeholder for actual payment processing)
                        payment = self._process_payment(invoice, payment_method)
                        
                        if payment.status == Payment.SUCCESS:
                            # Renew subscription
                            new_end_date = self._calculate_new_end_date(subscription)
                            subscription.end_date = new_end_date
                            subscription.save()
                            
                            # Update invoice status
                            invoice.status = Invoice.PAID
                            invoice.save()
                            
                            # Log successful renewal
                            SubscriptionEvent.objects.create(
                                tenant=tenant,
                                subscription=subscription,
                                event_type=SubscriptionEvent.SUBSCRIPTION_RENEWED,
                                description=f"Subscription successfully renewed until {new_end_date}"
                            )
                            
                            successful_renewals += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"Successfully renewed subscription for {tenant.name} until {new_end_date}"
                                )
                            )
                        else:
                            # Mark subscription as past due
                            subscription.status = TenantSubscription.PAST_DUE
                            subscription.save()
                            
                            # Log failed renewal
                            SubscriptionEvent.objects.create(
                                tenant=tenant,
                                subscription=subscription,
                                event_type=SubscriptionEvent.PAYMENT_FAILED,
                                description=f"Payment failed for subscription renewal: {payment.failure_reason}"
                            )
                            
                            failed_renewals += 1
                            self.stdout.write(
                                self.style.ERROR(
                                    f"Payment failed for {tenant.name}: {payment.failure_reason}"
                                )
                            )
                    else:
                        # Dry run mode
                        self.stdout.write(
                            self.style.NOTICE(
                                f"[DRY RUN] Would process renewal for {tenant.name} (Plan: {subscription.plan.name}, Amount: ${subscription.plan.price})"
                            )
                        )
                        successful_renewals += 1
            
            except Exception as e:
                failed_renewals += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"Error processing renewal for {tenant.name}: {str(e)}"
                    )
                )
                logger.error(f"Error processing renewal for {tenant.name}: {str(e)}")
        
        self.stdout.write(
            self.style.SUCCESS(
                f"Recurring payment processing completed. "
                f"Successful: {successful_renewals}, Failed: {failed_renewals}"
            )
        )
    
    def _process_payment(self, invoice, payment_method):
        """Process payment for an invoice"""
        try:
            # Placeholder for actual payment processing
            # In a real implementation, this would integrate with Stripe or another payment gateway
            
            if payment_method.method_type == 'stripe':
                # Create Stripe payment intent (placeholder)
                # payment_intent = create_stripe_payment_intent(
                #     amount=int(invoice.amount * 100),  # Convert to cents
                #     payment_method_id=payment_method.provider_id
                # )
                
                # For now, simulate successful payment
                payment = Payment.objects.create(
                    tenant=invoice.tenant,
                    invoice=invoice,
                    amount=invoice.amount,
                    payment_method=payment_method,
                    provider_transaction_id=f"test_txn_{timezone.now().timestamp()}",
                    status=Payment.SUCCESS,
                    processed_at=timezone.now()
                )
                return payment
            else:
                # Unsupported payment method
                return Payment.objects.create(
                    tenant=invoice.tenant,
                    invoice=invoice,
                    amount=invoice.amount,
                    payment_method=payment_method,
                    status=Payment.FAILED,
                    failure_reason=f"Unsupported payment method: {payment_method.method_type}",
                    processed_at=timezone.now()
                )
        
        except Exception as e:
            # Create failed payment record
            return Payment.objects.create(
                tenant=invoice.tenant,
                invoice=invoice,
                amount=invoice.amount,
                payment_method=payment_method,
                status=Payment.FAILED,
                failure_reason=str(e),
                processed_at=timezone.now()
            )
    
    def _calculate_new_end_date(self, subscription):
        """Calculate new end date based on subscription billing cycle"""
        current_end = subscription.end_date
        billing_cycle = subscription.plan.billing_cycle
        
        if billing_cycle == 'monthly':
            return current_end + timezone.timedelta(days=30)
        elif billing_cycle == 'yearly':
            return current_end + timezone.timedelta(days=365)
        else:
            # Default to monthly
            return current_end + timezone.timedelta(days=30)