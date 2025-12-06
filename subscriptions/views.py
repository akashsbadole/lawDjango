from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, TemplateView
from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from django.utils import timezone
from django.http import JsonResponse, HttpResponseBadRequest
from django.db.models import Q, Sum
from django.contrib.auth import get_user_model
from decimal import Decimal
import json
import logging

from permissions.mixins import TenantPermissionRequiredMixin
from permissions.utils import has_permission
from .models import (
    SubscriptionPlan, SubscriptionFeature, PlanFeature, PaymentMethod,
    TenantSubscription, Invoice, Payment, UsageRecord, SubscriptionEvent
)
from .forms import (
    PlanSelectionForm, PaymentMethodForm, SubscriptionUpdateForm,
    InvoicePaymentForm, UsageFilterForm
)
from .utils import get_stripe_client, create_stripe_payment_intent

User = get_user_model()
logger = logging.getLogger(__name__)


class SubscriptionRequiredMixin(LoginRequiredMixin):
    """
    Mixin to ensure user has an active subscription.
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        
        tenant = getattr(request.user, 'tenant', None)
        if not tenant:
            messages.error(request, "No tenant found.")
            return redirect('account_login')
        
        # Check if tenant has active subscription
        subscription = TenantSubscription.objects.current_for_tenant(tenant)
        if not subscription or not subscription.is_active:
            messages.warning(request, "You need an active subscription to access this feature.")
            return redirect('subscriptions:plan_selection')
        
        return super().dispatch(request, *args, **kwargs)


class PlanSelectionView(TenantPermissionRequiredMixin, ListView):
    """
    View for selecting subscription plans.
    """
    permission_required = 'subscriptions.view_plans'
    template_name = 'subscriptions/plan_selection.html'
    context_object_name = 'plans'
    paginate_by = 10
    
    def get_queryset(self):
        return SubscriptionPlan.objects.public().order_by('price')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant
        
        # Get current subscription if any
        current_subscription = TenantSubscription.objects.current_for_tenant(tenant)
        context['current_subscription'] = current_subscription
        
        # Group plans by type
        context['plan_types'] = {}
        for plan in context['plans']:
            plan_type = plan.plan_type
            if plan_type not in context['plan_types']:
                context['plan_types'][plan_type] = []
            context['plan_types'][plan_type].append(plan)
        
        return context


class PlanDetailView(TenantPermissionRequiredMixin, DetailView):
    """
    View for displaying details of a subscription plan.
    """
    permission_required = 'subscriptions.view_plans'
    model = SubscriptionPlan
    template_name = 'subscriptions/plan_detail.html'
    context_object_name = 'plan'
    
    def get_queryset(self):
        return SubscriptionPlan.objects.public()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plan = self.get_object()
        
        # Get features for this plan
        context['features'] = PlanFeature.objects.filter(plan=plan).select_related('feature')
        
        # Get current subscription for comparison
        tenant = self.request.user.tenant
        context['current_subscription'] = TenantSubscription.objects.current_for_tenant(tenant)
        
        return context


class SubscriptionCreateView(TenantPermissionRequiredMixin, FormView):
    """
    View for creating a new subscription.
    """
    permission_required = 'subscriptions.create_subscription'
    template_name = 'subscriptions/subscription_create.html'
    form_class = PlanSelectionForm
    success_url = reverse_lazy('subscriptions:billing')
    
    def form_valid(self, form):
        tenant = self.request.user.tenant
        plan = form.cleaned_data['plan']
        payment_method_id = form.cleaned_data.get('payment_method')
        
        try:
            # Create or get payment method
            payment_method = None
            if payment_method_id:
                payment_method = PaymentMethod.objects.get(
                    id=payment_method_id,
                    tenant=tenant
                )
            
            # Create subscription
            subscription = TenantSubscription.objects.create(
                tenant=tenant,
                plan=plan,
                status='trial' if plan.trial_days > 0 else 'active',
                start_date=timezone.now(),
                trial_end_date=timezone.now() + timezone.timedelta(days=plan.trial_days) if plan.trial_days > 0 else None,
                payment_method=payment_method,
                auto_renew=True
            )
            
            # Calculate end date based on billing cycle
            if plan.billing_cycle == 'monthly':
                subscription.end_date = subscription.start_date + timezone.timedelta(days=30)
            elif plan.billing_cycle == 'yearly':
                subscription.end_date = subscription.start_date + timezone.timedelta(days=365)
            subscription.save()
            
            # Create setup fee invoice if applicable
            if plan.setup_fee > 0:
                self._create_invoice(subscription, 'setup_fee', plan.setup_fee)
            
            # Log event
            SubscriptionEvent.objects.log_event(
                tenant=tenant,
                subscription=subscription,
                event_type='created',
                description=f"Subscription created for plan {plan.name}"
            )
            
            messages.success(
                self.request,
                f"Successfully subscribed to {plan.name}!"
            )
            
            return super().form_valid(form)
            
        except Exception as e:
            logger.error(f"Error creating subscription: {str(e)}")
            messages.error(
                self.request,
                "An error occurred while creating your subscription. Please try again."
            )
            return self.form_invalid(form)
    
    def _create_invoice(self, subscription, invoice_type, amount):
        """Create an invoice for the subscription."""
        invoice_number = f"SUB-{timezone.now().strftime('%Y%m%d')}-{subscription.id:04d}"
        
        invoice = Invoice.objects.create(
            invoice_number=invoice_number,
            tenant=subscription.tenant,
            subscription=subscription,
            invoice_type=invoice_type,
            issue_date=timezone.now().date(),
            due_date=timezone.now().date() + timezone.timedelta(days=30),
            subtotal=amount,
            tax_rate=Decimal('0.0000'),
            total_amount=amount,
            status='draft'
        )
        
        return invoice


class SubscriptionUpdateView(SubscriptionRequiredMixin, TenantPermissionRequiredMixin, UpdateView):
    """
    View for updating subscription (upgrade/downgrade).
    """
    permission_required = 'subscriptions.update_subscription'
    model = TenantSubscription
    form_class = SubscriptionUpdateForm
    template_name = 'subscriptions/subscription_update.html'
    success_url = reverse_lazy('subscriptions:billing')
    
    def get_object(self):
        tenant = self.request.user.tenant
        return TenantSubscription.objects.current_for_tenant(tenant)
    
    def form_valid(self, form):
        subscription = self.get_object()
        old_plan = subscription.plan
        new_plan = form.cleaned_data['plan']
        
        if old_plan == new_plan:
            messages.info(self.request, "No changes made to your subscription.")
            return super().form_valid(form)
        
        try:
            # Update subscription
            subscription.plan = new_plan
            subscription.save()
            
            # Create invoice for plan change
            price_difference = new_plan.price - old_plan.price
            if price_difference > 0:
                self._create_invoice(subscription, 'other', price_difference)
            
            # Log event
            SubscriptionEvent.objects.log_event(
                tenant=subscription.tenant,
                subscription=subscription,
                event_type='plan_changed',
                description=f"Changed from {old_plan.name} to {new_plan.name}",
                metadata={
                    'old_plan': old_plan.name,
                    'new_plan': new_plan.name,
                    'price_difference': str(price_difference)
                }
            )
            
            messages.success(
                self.request,
                f"Successfully updated subscription to {new_plan.name}!"
            )
            
            return super().form_valid(form)
            
        except Exception as e:
            logger.error(f"Error updating subscription: {str(e)}")
            messages.error(
                self.request,
                "An error occurred while updating your subscription. Please try again."
            )
            return self.form_invalid(form)


class SubscriptionCancelView(SubscriptionRequiredMixin, TenantPermissionRequiredMixin, DeleteView):
    """
    View for cancelling subscription.
    """
    permission_required = 'subscriptions.cancel_subscription'
    model = TenantSubscription
    template_name = 'subscriptions/subscription_confirm_cancel.html'
    success_url = reverse_lazy('subscriptions:plan_selection')
    
    def get_object(self):
        tenant = self.request.user.tenant
        return TenantSubscription.objects.current_for_tenant(tenant)
    
    def delete(self, request, *args, **kwargs):
        subscription = self.get_object()
        
        try:
            # Update subscription status
            subscription.status = 'cancelled'
            subscription.cancelled_at = timezone.now()
            subscription.auto_renew = False
            subscription.save()
            
            # Log event
            SubscriptionEvent.objects.log_event(
                tenant=subscription.tenant,
                subscription=subscription,
                event_type='cancelled',
                description="Subscription cancelled by user"
            )
            
            messages.success(
                request,
                "Your subscription has been cancelled."
            )
            
            return redirect(self.success_url)
            
        except Exception as e:
            logger.error(f"Error cancelling subscription: {str(e)}")
            messages.error(
                request,
                "An error occurred while cancelling your subscription. Please try again."
            )
            return redirect('subscriptions:billing')


class BillingDashboardView(SubscriptionRequiredMixin, TenantPermissionRequiredMixin, TemplateView):
    """
    View for billing dashboard.
    """
    permission_required = 'subscriptions.view_billing'
    template_name = 'subscriptions/billing_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant
        subscription = TenantSubscription.objects.current_for_tenant(tenant)
        
        context['subscription'] = subscription
        
        # Get recent invoices
        context['recent_invoices'] = Invoice.objects.for_tenant(tenant).order_by('-created_at')[:5]
        
        # Get recent payments
        context['recent_payments'] = Payment.objects.for_tenant(tenant).successful().order_by('-payment_date')[:5]
        
        # Calculate billing summary
        current_month = timezone.now().replace(day=1)
        monthly_payments = Payment.objects.for_tenant(tenant).successful().filter(
            payment_date__gte=current_month
        )
        context['monthly_total'] = monthly_payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Get unpaid invoices
        context['unpaid_invoices'] = Invoice.objects.for_tenant(tenant).unpaid()
        context['unpaid_count'] = context['unpaid_invoices'].count()
        context['unpaid_total'] = context['unpaid_invoices'].aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0.00')
        
        return context


class InvoiceListView(SubscriptionRequiredMixin, TenantPermissionRequiredMixin, ListView):
    """
    View for listing invoices.
    """
    permission_required = 'subscriptions.view_invoices'
    model = Invoice
    template_name = 'subscriptions/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20
    
    def get_queryset(self):
        tenant = self.request.user.tenant
        queryset = Invoice.objects.for_tenant(tenant)
        
        # Apply filters
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', '')
        return context


class InvoiceDetailView(SubscriptionRequiredMixin, TenantPermissionRequiredMixin, DetailView):
    """
    View for invoice details.
    """
    permission_required = 'subscriptions.view_invoices'
    model = Invoice
    template_name = 'subscriptions/invoice_detail.html'
    context_object_name = 'invoice'
    
    def get_queryset(self):
        tenant = self.request.user.tenant
        return Invoice.objects.for_tenant(tenant)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.get_object()
        
        # Get payments for this invoice
        context['payments'] = invoice.payments.all().order_by('-payment_date')
        
        # Calculate total paid
        context['total_paid'] = sum(payment.amount for payment in context['payments'])
        
        # Calculate remaining balance
        context['remaining_balance'] = invoice.total_amount - context['total_paid']
        
        return context


class PaymentMethodListView(SubscriptionRequiredMixin, TenantPermissionRequiredMixin, ListView):
    """
    View for listing payment methods.
    """
    permission_required = 'subscriptions.view_payment_methods'
    model = PaymentMethod
    template_name = 'subscriptions/payment_method_list.html'
    context_object_name = 'payment_methods'
    
    def get_queryset(self):
        tenant = self.request.user.tenant
        return PaymentMethod.objects.filter(tenant=tenant).order_by('-is_default', '-created_at')


class PaymentMethodCreateView(SubscriptionRequiredMixin, TenantPermissionRequiredMixin, CreateView):
    """
    View for adding a new payment method.
    """
    permission_required = 'subscriptions.create_payment_method'
    model = PaymentMethod
    form_class = PaymentMethodForm
    template_name = 'subscriptions/payment_method_form.html'
    success_url = reverse_lazy('subscriptions:payment_methods')
    
    def form_valid(self, form):
        form.instance.tenant = self.request.user.tenant
        messages.success(self.request, "Payment method added successfully!")
        return super().form_valid(form)


class PaymentMethodUpdateView(SubscriptionRequiredMixin, TenantPermissionRequiredMixin, UpdateView):
    """
    View for updating a payment method.
    """
    permission_required = 'subscriptions.update_payment_method'
    model = PaymentMethod
    form_class = PaymentMethodForm
    template_name = 'subscriptions/payment_method_form.html'
    success_url = reverse_lazy('subscriptions:payment_methods')
    
    def get_queryset(self):
        tenant = self.request.user.tenant
        return PaymentMethod.objects.filter(tenant=tenant)
    
    def form_valid(self, form):
        messages.success(self.request, "Payment method updated successfully!")
        return super().form_valid(form)


class PaymentMethodDeleteView(SubscriptionRequiredMixin, TenantPermissionRequiredMixin, DeleteView):
    """
    View for deleting a payment method.
    """
    permission_required = 'subscriptions.delete_payment_method'
    model = PaymentMethod
    template_name = 'subscriptions/payment_method_confirm_delete.html'
    success_url = reverse_lazy('subscriptions:payment_methods')
    
    def get_queryset(self):
        tenant = self.request.user.tenant
        return PaymentMethod.objects.filter(tenant=tenant)
    
    def delete(self, request, *args, **kwargs):
        payment_method = self.get_object()
        
        # Prevent deletion of default payment method
        if payment_method.is_default:
            messages.error(request, "Cannot delete the default payment method.")
            return redirect('subscriptions:payment_methods')
        
        messages.success(request, "Payment method deleted successfully!")
        return super().delete(request, *args, **kwargs)


class PaymentCreateView(SubscriptionRequiredMixin, TenantPermissionRequiredMixin, FormView):
    """
    View for creating a payment for an invoice.
    """
    permission_required = 'subscriptions.create_payment'
    form_class = InvoicePaymentForm
    template_name = 'subscriptions/payment_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.invoice = get_object_or_404(
            Invoice,
            id=kwargs['invoice_id'],
            tenant=request.user.tenant
        )
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['invoice'] = self.invoice
        return context
    
    def form_valid(self, form):
        try:
            # Create Stripe payment intent (placeholder implementation)
            payment_intent_id = create_stripe_payment_intent(
                self.invoice.total_amount,
                "usd",
                self.invoice.invoice_number
            )
            
            # Create payment record
            payment = Payment.objects.create(
                invoice=self.invoice,
                amount=self.invoice.total_amount,
                payment_method='stripe',
                status='pending',
                stripe_payment_intent_id=payment_intent_id
            )
            
            # Update invoice status
            self.invoice.status = 'sent'
            self.invoice.save()
            
            # Log event
            SubscriptionEvent.objects.log_event(
                tenant=self.invoice.tenant,
                subscription=self.invoice.subscription,
                event_type='payment_succeeded',
                description=f"Payment initiated for invoice {self.invoice.invoice_number}",
                metadata={'payment_id': payment.id}
            )
            
            messages.success(
                self.request,
                "Payment initiated successfully!"
            )
            
            return redirect('subscriptions:invoice_detail', pk=self.invoice.pk)
            
        except Exception as e:
            logger.error(f"Error creating payment: {str(e)}")
            messages.error(
                self.request,
                "An error occurred while processing your payment. Please try again."
            )
            return self.form_invalid(form)


class UsageDashboardView(SubscriptionRequiredMixin, TenantPermissionRequiredMixin, TemplateView):
    """
    View for usage tracking dashboard.
    """
    permission_required = 'subscriptions.view_usage'
    template_name = 'subscriptions/usage_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant
        subscription = TenantSubscription.objects.current_for_tenant(tenant)
        
        context['subscription'] = subscription
        
        # Get current month usage records
        current_month = timezone.now().replace(day=1)
        context['usage_records'] = UsageRecord.objects.for_tenant(tenant).filter(
            period_start__gte=current_month
        ).select_related('feature')
        
        # Calculate usage statistics
        total_records = context['usage_records'].count()
        over_limit_records = context['usage_records'].filter(
            limit__isnull=False,
            current_usage__gt=models.F('limit')
        ).count()
        
        context['usage_stats'] = {
            'total_features': total_records,
            'over_limit_features': over_limit_records,
            'usage_percentage': (over_limit_records / total_records * 100) if total_records > 0 else 0
        }
        
        # Get user count and storage usage
        context['user_count'] = tenant.get_current_user_count()
        context['storage_used'] = tenant.get_storage_used()
        context['storage_limit'] = tenant.get_storage_limit()
        
        if context['storage_limit'] > 0:
            context['storage_percentage'] = (context['storage_used'] / context['storage_limit']) * 100
        else:
            context['storage_percentage'] = 0
        
        return context


class UsageRecordListView(SubscriptionRequiredMixin, TenantPermissionRequiredMixin, ListView):
    """
    View for listing usage records.
    """
    permission_required = 'subscriptions.view_usage'
    model = UsageRecord
    template_name = 'subscriptions/usage_list.html'
    context_object_name = 'usage_records'
    paginate_by = 20
    
    def get_queryset(self):
        tenant = self.request.user.tenant
        queryset = UsageRecord.objects.for_tenant(tenant).select_related('feature')
        
        # Apply filters
        form = UsageFilterForm(self.request.GET)
        if form.is_valid():
            feature = form.cleaned_data.get('feature')
            period = form.cleaned_data.get('period')
            
            if feature:
                queryset = queryset.filter(feature=feature)
            if period:
                queryset = queryset.filter(period=period)
        
        return queryset.order_by('-period_start', 'feature')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = UsageFilterForm(self.request.GET)
        return context
