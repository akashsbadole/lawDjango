from django.db import models
from django.utils import timezone


class BillingManager(models.Manager):
    """
    Base manager for billing models with tenant filtering and soft delete functionality.
    """
    
    def get_queryset(self):
        """
        Override the default queryset to exclude soft-deleted records.
        """
        return super().get_queryset().filter(deleted_at__isnull=True)
    
    def all_with_deleted(self):
        """
        Return all records including soft-deleted ones.
        """
        return super().get_queryset()
    
    def deleted(self):
        """
        Return only soft-deleted records.
        """
        return super().get_queryset().filter(deleted_at__isnull=False)
    
    def for_tenant(self, tenant):
        """
        Filter records by tenant.
        """
        return self.filter(tenant=tenant)
    
    def active_for_tenant(self, tenant):
        """
        Return active (non-deleted) records for a specific tenant.
        """
        return self.filter(tenant=tenant, deleted_at__isnull=True)


class InvoiceManager(BillingManager):
    """
    Manager for the Invoice model with additional invoice-specific methods.
    """
    
    def for_status(self, status):
        """
        Filter invoices by status.
        """
        return self.filter(status=status)
    
    def overdue(self, tenant=None):
        """
        Return overdue invoices.
        """
        queryset = self.filter(due_date__lt=timezone.now().date(), status__in=['draft', 'sent'])
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def paid(self, tenant=None):
        """
        Return paid invoices.
        """
        queryset = self.filter(status='paid')
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def unpaid(self, tenant=None):
        """
        Return unpaid invoices.
        """
        queryset = self.filter(status__in=['draft', 'sent'])
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset


class TimeEntryManager(BillingManager):
    """
    Manager for the TimeEntry model with additional time entry-specific methods.
    """
    
    def for_lawyer(self, lawyer):
        """
        Filter time entries by lawyer.
        """
        return self.filter(lawyer=lawyer)
    
    def for_case(self, case):
        """
        Filter time entries by case.
        """
        return self.filter(case=case)
    
    def billable(self, tenant=None):
        """
        Return billable time entries.
        """
        queryset = self.filter(is_billable=True)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def unbilled(self, tenant=None):
        """
        Return time entries that haven't been billed yet.
        """
        queryset = self.filter(invoice_item__isnull=True)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset
    
    def for_date_range(self, start_date, end_date, tenant=None):
        """
        Return time entries within a date range.
        """
        queryset = self.filter(date__gte=start_date, date__lte=end_date)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset


class ExpenseManager(BillingManager):
    """
    Manager for the Expense model with additional expense-specific methods.
    """
    
    def for_case(self, case):
        """
        Filter expenses by case.
        """
        return self.filter(case=case)
    
    def for_category(self, category):
        """
        Filter expenses by category.
        """
        return self.filter(category=category)
    
    def reimbursable(self, tenant=None):
        """
        Return reimbursable expenses.
        """
        queryset = self.filter(is_reimbursable=True)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset


class PaymentManager(BillingManager):
    """
    Manager for the Payment model with additional payment-specific methods.
    """
    
    def for_invoice(self, invoice):
        """
        Filter payments by invoice.
        """
        return self.filter(invoice=invoice)
    
    def for_method(self, method):
        """
        Filter payments by payment method.
        """
        return self.filter(payment_method=method)
    
    def for_date_range(self, start_date, end_date, tenant=None):
        """
        Return payments within a date range.
        """
        queryset = self.filter(payment_date__gte=start_date, payment_date__lte=end_date)
        if tenant:
            queryset = queryset.filter(tenant=tenant)
        return queryset