from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Sum, Q
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from decimal import Decimal
# We'll import weasyprint only when needed to avoid import errors
weasyprint = None

# Import permission utilities
from permissions.decorators import role_required
from permissions.mixins import TenantPermissionRequiredMixin
from permissions.utils import has_permission

from .models import (
    BillingRate, Invoice, InvoiceItem, TimeEntry,
    Expense, Payment
)
from .forms import (
    BillingRateForm, InvoiceForm, InvoiceItemForm, TimeEntryForm,
    ExpenseForm, PaymentForm, InvoiceSearchForm, TimeEntrySearchForm
)
from audit.utils import log_activity

User = get_user_model()


class TenantRequiredMixin(LoginRequiredMixin):
    """
    Mixin to ensure user is authenticated and has a tenant.
    """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not hasattr(request.user, 'tenant'):
            return redirect('account_login')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tenant'] = self.request.user.tenant
        return context


class BillingDashboardView(TenantPermissionRequiredMixin, ListView):
    permission_required = 'billing.view_dashboard'
    """
    Dashboard view for billing module.
    """
    template_name = 'billing/dashboard.html'
    context_object_name = None
    paginate_by = None
    
    def get_queryset(self):
        return None
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant
        
        # Get recent invoices
        context['recent_invoices'] = Invoice.objects.active_for_tenant(tenant).order_by('-created_at')[:5]
        
        # Get unpaid invoices count and total
        unpaid_invoices = Invoice.objects.unpaid(tenant)
        context['unpaid_invoices_count'] = unpaid_invoices.count()
        context['unpaid_invoices_total'] = unpaid_invoices.aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0.00')
        
        # Get overdue invoices
        context['overdue_invoices'] = Invoice.objects.overdue(tenant)[:5]
        
        # Get unbilled time entries
        context['unbilled_time_entries'] = TimeEntry.objects.unbilled(tenant)[:5]
        
        # Get recent payments
        context['recent_payments'] = Payment.objects.active_for_tenant(tenant).order_by('-payment_date')[:5]
        
        # Get monthly revenue
        current_month = timezone.now().replace(day=1)
        monthly_payments = Payment.objects.active_for_tenant(tenant).filter(
            payment_date__gte=current_month
        )
        context['monthly_revenue'] = monthly_payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        return context


# Invoice Views
class InvoiceListView(TenantPermissionRequiredMixin, ListView):
    permission_required = 'billing.view_invoice'
    """
    List view for invoices.
    """
    model = Invoice
    template_name = 'billing/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 10
    
    def get_queryset(self):
        tenant = self.request.user.tenant
        queryset = Invoice.objects.active_for_tenant(tenant)
        
        # Apply search filters
        form = InvoiceSearchForm(self.request.GET)
        if form.is_valid():
            query = form.cleaned_data.get('query')
            status = form.cleaned_data.get('status')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            
            if query:
                queryset = queryset.filter(
                    Q(invoice_number__icontains=query) |
                    Q(client__first_name__icontains=query) |
                    Q(client__last_name__icontains=query) |
                    Q(client__company__icontains=query)
                )
            
            if status:
                queryset = queryset.filter(status=status)
            
            if date_from:
                queryset = queryset.filter(issue_date__gte=date_from)
            
            if date_to:
                queryset = queryset.filter(issue_date__lte=date_to)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = InvoiceSearchForm(self.request.GET)
        return context


class InvoiceDetailView(TenantPermissionRequiredMixin, DetailView):
    permission_required = 'billing.view_invoice'
    """
    Detail view for invoices.
    """
    model = Invoice
    template_name = 'billing/invoice_detail.html'
    context_object_name = 'invoice'
    
    def get_queryset(self):
        return Invoice.objects.active_for_tenant(self.request.user.tenant)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.get_object()
        
        # Get invoice items
        context['items'] = invoice.items.all()
        
        # Get payments
        context['payments'] = invoice.payments.all()
        
        # Calculate total paid
        context['total_paid'] = sum(payment.amount for payment in context['payments'])
        
        # Calculate remaining balance
        context['remaining_balance'] = invoice.total_amount - context['total_paid']
        
        return context


class InvoiceCreateView(TenantPermissionRequiredMixin, CreateView):
    permission_required = 'billing.create_invoice'
    """
    Create view for invoices.
    """
    model = Invoice
    form_class = InvoiceForm
    template_name = 'billing/invoice_form.html'
    success_url = reverse_lazy('billing:invoice_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.user.tenant
        return kwargs
    
    def form_valid(self, form):
        form.instance.tenant = self.request.user.tenant
        form.instance.created_by = self.request.user
        
        # Generate invoice number
        last_invoice = Invoice.objects.active_for_tenant(self.request.user.tenant).order_by('-id').first()
        if last_invoice:
            last_number = int(last_invoice.invoice_number.split('-')[-1])
            new_number = f"INV-{last_number + 1:04d}"
        else:
            new_number = "INV-0001"
        
        form.instance.invoice_number = new_number
        invoice = form.save()
        
        # Log activity
        log_activity(
            tenant=self.request.user.tenant,
            user=self.request.user,
            activity_type='INVOICE_CREATED',
            description=f'Created invoice: {invoice.invoice_number}',
            related_object=invoice,
            metadata={
                'invoice_number': invoice.invoice_number,
                'client': invoice.client.get_full_name() if invoice.client else None,
                'total_amount': str(invoice.total_amount),
            }
        )
        
        messages.success(self.request, f'Invoice {invoice.invoice_number} created successfully.')
        return super().form_valid(form)


class InvoiceUpdateView(TenantPermissionRequiredMixin, UpdateView):
    permission_required = 'billing.edit_invoice'
    """
    Update view for invoices.
    """
    model = Invoice
    form_class = InvoiceForm
    template_name = 'billing/invoice_form.html'
    success_url = reverse_lazy('billing:invoice_list')
    
    def get_queryset(self):
        return Invoice.objects.active_for_tenant(self.request.user.tenant)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.user.tenant
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, f'Invoice {form.instance.invoice_number} updated successfully.')
        return super().form_valid(form)


class InvoiceDeleteView(TenantPermissionRequiredMixin, DeleteView):
    permission_required = 'billing.delete_invoice'
    """
    Delete view for invoices.
    """
    model = Invoice
    template_name = 'billing/invoice_confirm_delete.html'
    success_url = reverse_lazy('billing:invoice_list')
    
    def get_queryset(self):
        return Invoice.objects.active_for_tenant(self.request.user.tenant)
    
    def delete(self, request, *args, **kwargs):
        invoice = self.get_object()
        invoice.soft_delete()
        messages.success(request, f'Invoice {invoice.invoice_number} deleted successfully.')
        return redirect(self.success_url)


class InvoicePDFView(TenantPermissionRequiredMixin, DetailView):
    permission_required = 'billing.view_invoice'
    """
    Generate PDF for invoice.
    """
    model = Invoice
    template_name = 'billing/invoice_pdf.html'
    context_object_name = 'invoice'
    
    def get_queryset(self):
        return Invoice.objects.active_for_tenant(self.request.user.tenant)
    
    def get(self, request, *args, **kwargs):
        invoice = self.get_object()
        
        # Try to import weasyprint only when needed
        try:
            import weasyprint
        except ImportError:
            messages.error(request, 'PDF generation is not available. Please install weasyprint.')
            return redirect('billing:invoice_detail', pk=invoice.pk)
        
        # Get invoice items and payments
        items = invoice.items.all()
        payments = invoice.payments.all()
        total_paid = sum(payment.amount for payment in payments)
        remaining_balance = invoice.total_amount - total_paid
        
        # Render HTML
        html = render_to_string(self.template_name, {
            'invoice': invoice,
            'items': items,
            'payments': payments,
            'total_paid': total_paid,
            'remaining_balance': remaining_balance,
            'tenant': request.user.tenant,
        })
        
        # Generate PDF
        pdf = weasyprint.HTML(string=html).write_pdf()
        
        # Create response
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
        
        return response


# Time Entry Views
class TimeEntryListView(TenantPermissionRequiredMixin, ListView):
    permission_required = 'billing.view_time_entry'
    """
    List view for time entries.
    """
    model = TimeEntry
    template_name = 'billing/time_entry_list.html'
    context_object_name = 'time_entries'
    paginate_by = 20
    
    def get_queryset(self):
        tenant = self.request.user.tenant
        queryset = TimeEntry.objects.active_for_tenant(tenant)
        
        # Apply search filters
        form = TimeEntrySearchForm(self.request.GET, tenant=tenant)
        if form.is_valid():
            query = form.cleaned_data.get('query')
            lawyer = form.cleaned_data.get('lawyer')
            case = form.cleaned_data.get('case')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            is_billable = form.cleaned_data.get('is_billable')
            
            if query:
                queryset = queryset.filter(description__icontains=query)
            
            if lawyer:
                queryset = queryset.filter(lawyer=lawyer)
            
            if case:
                queryset = queryset.filter(case=case)
            
            if date_from:
                queryset = queryset.filter(date__gte=date_from)
            
            if date_to:
                queryset = queryset.filter(date__lte=date_to)
            
            if is_billable:
                queryset = queryset.filter(is_billable=True)
        
        return queryset.order_by('-date', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = TimeEntrySearchForm(self.request.GET, tenant=self.request.user.tenant)
        return context


class TimeEntryCreateView(TenantPermissionRequiredMixin, CreateView):
    permission_required = 'billing.create_time_entry'
    """
    Create view for time entries.
    """
    model = TimeEntry
    form_class = TimeEntryForm
    template_name = 'billing/time_entry_form.html'
    success_url = reverse_lazy('billing:time_entry_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.user.tenant
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.tenant = self.request.user.tenant
        form.instance.created_by = self.request.user
        
        time_entry = form.save()
        
        # Log activity
        log_activity(
            tenant=self.request.user.tenant,
            user=self.request.user,
            activity_type='TIME_ENTRY_CREATED',
            description=f'Logged time entry: {time_entry.description}',
            related_object=time_entry,
            metadata={
                'hours': str(time_entry.hours),
                'rate': str(time_entry.rate),
                'amount': str(time_entry.amount),
                'date': str(time_entry.date),
                'case': time_entry.case.title if time_entry.case else None,
            }
        )
        
        messages.success(self.request, 'Time entry created successfully.')
        return super().form_valid(form)


class TimeEntryUpdateView(TenantPermissionRequiredMixin, UpdateView):
    permission_required = 'billing.edit_time_entry'
    """
    Update view for time entries.
    """
    model = TimeEntry
    form_class = TimeEntryForm
    template_name = 'billing/time_entry_form.html'
    success_url = reverse_lazy('billing:time_entry_list')
    
    def get_queryset(self):
        return TimeEntry.objects.active_for_tenant(self.request.user.tenant)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.user.tenant
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, 'Time entry updated successfully.')
        return super().form_valid(form)


class TimeEntryDeleteView(TenantPermissionRequiredMixin, DeleteView):
    permission_required = 'billing.delete_time_entry'
    """
    Delete view for time entries.
    """
    model = TimeEntry
    template_name = 'billing/time_entry_confirm_delete.html'
    success_url = reverse_lazy('billing:time_entry_list')
    
    def get_queryset(self):
        return TimeEntry.objects.active_for_tenant(self.request.user.tenant)
    
    def delete(self, request, *args, **kwargs):
        time_entry = self.get_object()
        time_entry.soft_delete()
        messages.success(request, 'Time entry deleted successfully.')
        return redirect(self.success_url)


# Expense Views
class ExpenseListView(TenantPermissionRequiredMixin, ListView):
    permission_required = 'billing.view_expense'
    """
    List view for expenses.
    """
    model = Expense
    template_name = 'billing/expense_list.html'
    context_object_name = 'expenses'
    paginate_by = 20
    
    def get_queryset(self):
        return Expense.objects.active_for_tenant(self.request.user.tenant).order_by('-date', '-created_at')


class ExpenseCreateView(TenantPermissionRequiredMixin, CreateView):
    permission_required = 'billing.create_expense'
    """
    Create view for expenses.
    """
    model = Expense
    form_class = ExpenseForm
    template_name = 'billing/expense_form.html'
    success_url = reverse_lazy('billing:expense_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.user.tenant
        return kwargs
    
    def form_valid(self, form):
        form.instance.tenant = self.request.user.tenant
        form.instance.created_by = self.request.user
        
        expense = form.save()
        
        # Log activity
        log_activity(
            tenant=self.request.user.tenant,
            user=self.request.user,
            activity_type='EXPENSE_CREATED',
            description=f'Created expense: {expense.description}',
            related_object=expense,
            metadata={
                'amount': str(expense.amount),
                'date': str(expense.date),
                'category': expense.category,
                'is_reimbursable': expense.is_reimbursable,
            }
        )
        
        messages.success(self.request, 'Expense created successfully.')
        return super().form_valid(form)


class ExpenseUpdateView(TenantPermissionRequiredMixin, UpdateView):
    permission_required = 'billing.edit_expense'
    """
    Update view for expenses.
    """
    model = Expense
    form_class = ExpenseForm
    template_name = 'billing/expense_form.html'
    success_url = reverse_lazy('billing:expense_list')
    
    def get_queryset(self):
        return Expense.objects.active_for_tenant(self.request.user.tenant)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.user.tenant
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, 'Expense updated successfully.')
        return super().form_valid(form)


class ExpenseDeleteView(TenantPermissionRequiredMixin, DeleteView):
    permission_required = 'billing.delete_expense'
    """
    Delete view for expenses.
    """
    model = Expense
    template_name = 'billing/expense_confirm_delete.html'
    success_url = reverse_lazy('billing:expense_list')
    
    def get_queryset(self):
        return Expense.objects.active_for_tenant(self.request.user.tenant)
    
    def delete(self, request, *args, **kwargs):
        expense = self.get_object()
        expense.soft_delete()
        messages.success(request, 'Expense deleted successfully.')
        return redirect(self.success_url)


# Payment Views
class PaymentListView(TenantPermissionRequiredMixin, ListView):
    permission_required = 'billing.view_payment'
    """
    List view for payments.
    """
    model = Payment
    template_name = 'billing/payment_list.html'
    context_object_name = 'payments'
    paginate_by = 20
    
    def get_queryset(self):
        return Payment.objects.active_for_tenant(self.request.user.tenant).order_by('-payment_date', '-created_at')


class PaymentCreateView(TenantPermissionRequiredMixin, CreateView):
    permission_required = 'billing.create_payment'
    """
    Create view for payments.
    """
    model = Payment
    form_class = PaymentForm
    template_name = 'billing/payment_form.html'
    success_url = reverse_lazy('billing:payment_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.user.tenant
        return kwargs
    
    def form_valid(self, form):
        form.instance.tenant = self.request.user.tenant
        form.instance.created_by = self.request.user
        
        payment = form.save()
        
        # Log activity
        log_activity(
            tenant=self.request.user.tenant,
            user=self.request.user,
            activity_type='PAYMENT_RECORDED',
            description=f'Recorded payment for invoice {payment.invoice.invoice_number}',
            related_object=payment,
            metadata={
                'amount': str(payment.amount),
                'payment_date': str(payment.payment_date),
                'payment_method': payment.payment_method,
                'invoice_number': payment.invoice.invoice_number,
            }
        )
        
        messages.success(self.request, 'Payment recorded successfully.')
        return super().form_valid(form)


class PaymentUpdateView(TenantPermissionRequiredMixin, UpdateView):
    permission_required = 'billing.edit_payment'
    """
    Update view for payments.
    """
    model = Payment
    form_class = PaymentForm
    template_name = 'billing/payment_form.html'
    success_url = reverse_lazy('billing:payment_list')
    
    def get_queryset(self):
        return Payment.objects.active_for_tenant(self.request.user.tenant)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.user.tenant
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, 'Payment updated successfully.')
        return super().form_valid(form)


class PaymentDeleteView(TenantPermissionRequiredMixin, DeleteView):
    permission_required = 'billing.delete_payment'
    """
    Delete view for payments.
    """
    model = Payment
    template_name = 'billing/payment_confirm_delete.html'
    success_url = reverse_lazy('billing:payment_list')
    
    def get_queryset(self):
        return Payment.objects.active_for_tenant(self.request.user.tenant)
    
    def delete(self, request, *args, **kwargs):
        payment = self.get_object()
        payment.soft_delete()
        messages.success(request, 'Payment deleted successfully.')
        return redirect(self.success_url)


# Invoice Item Views (AJAX)
class InvoiceItemCreateView(TenantPermissionRequiredMixin, CreateView):
    permission_required = 'billing.edit_invoice'
    """
    Create view for invoice items (AJAX).
    """
    model = InvoiceItem
    form_class = InvoiceItemForm
    template_name = 'billing/invoice_item_form.html'
    
    def form_valid(self, form):
        form.instance.tenant = self.request.user.tenant
        form.instance.invoice_id = self.kwargs['invoice_id']
        form.save()
        
        # Update invoice totals
        invoice = form.instance.invoice
        invoice.calculate_totals()
        
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'item_id': form.instance.id,
                'description': form.instance.description,
                'quantity': str(form.instance.quantity),
                'rate': str(form.instance.rate),
                'amount': str(form.instance.amount),
                'subtotal': str(invoice.subtotal),
                'tax_amount': str(invoice.tax_amount),
                'total_amount': str(invoice.total_amount),
            })
        
        return redirect('billing:invoice_detail', pk=invoice.pk)


class InvoiceItemDeleteView(TenantPermissionRequiredMixin, DeleteView):
    permission_required = 'billing.edit_invoice'
    """
    Delete view for invoice items (AJAX).
    """
    model = InvoiceItem
    template_name = 'billing/invoice_item_confirm_delete.html'
    
    def get_queryset(self):
        return InvoiceItem.objects.active_for_tenant(self.request.user.tenant)
    
    def delete(self, request, *args, **kwargs):
        item = self.get_object()
        invoice = item.invoice
        item.soft_delete()
        
        # Update invoice totals
        invoice.calculate_totals()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'subtotal': str(invoice.subtotal),
                'tax_amount': str(invoice.tax_amount),
                'total_amount': str(invoice.total_amount),
            })
        
        return redirect('billing:invoice_detail', pk=invoice.pk)


# Invoice Generation from Time Entries
class GenerateInvoiceView(TenantPermissionRequiredMixin, FormView):
    permission_required = 'billing.create_invoice'
    """
    Generate invoice from time entries.
    """
    template_name = 'billing/generate_invoice.html'
    form_class = InvoiceForm
    success_url = reverse_lazy('billing:invoice_list')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.user.tenant
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant = self.request.user.tenant
        
        # Get unbilled time entries
        context['unbilled_time_entries'] = TimeEntry.objects.unbilled(tenant)
        
        # Get unbilled expenses
        context['unbilled_expenses'] = Expense.objects.active_for_tenant(tenant).filter(
            invoice_items__isnull=True,
            is_reimbursable=True
        )
        
        return context
    
    def form_valid(self, form):
        tenant = self.request.user.tenant
        
        # Create invoice
        invoice = form.save(commit=False)
        invoice.tenant = tenant
        invoice.created_by = self.request.user
        
        # Generate invoice number
        last_invoice = Invoice.objects.active_for_tenant(tenant).order_by('-id').first()
        if last_invoice:
            last_number = int(last_invoice.invoice_number.split('-')[-1])
            new_number = f"INV-{last_number + 1:04d}"
        else:
            new_number = "INV-0001"
        
        invoice.invoice_number = new_number
        invoice.save()
        
        # Get selected time entries and expenses
        time_entry_ids = self.request.POST.getlist('time_entries')
        expense_ids = self.request.POST.getlist('expenses')
        
        # Add time entries to invoice
        for te_id in time_entry_ids:
            time_entry = TimeEntry.objects.get(pk=te_id)
            InvoiceItem.objects.create(
                invoice=invoice,
                description=f"Time Entry: {time_entry.description}",
                quantity=time_entry.hours,
                rate=time_entry.rate,
                tenant=tenant,
                time_entry=time_entry
            )
        
        # Add expenses to invoice
        for exp_id in expense_ids:
            expense = Expense.objects.get(pk=exp_id)
            InvoiceItem.objects.create(
                invoice=invoice,
                description=f"Expense: {expense.description}",
                quantity=1,
                rate=expense.amount,
                tenant=tenant,
                expense=expense
            )
        
        # Calculate totals
        invoice.calculate_totals()
        
        messages.success(self.request, f'Invoice {invoice.invoice_number} generated successfully.')
        return redirect('billing:invoice_detail', pk=invoice.pk)
