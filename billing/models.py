from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from decimal import Decimal
from .managers import (
    BillingManager, InvoiceManager, TimeEntryManager, 
    ExpenseManager, PaymentManager
)

User = get_user_model()


class BillingRate(models.Model):
    """
    Model representing billing rates for different lawyer roles.
    """
    ROLE_CHOICES = [
        ('partner', 'Partner'),
        ('associate', 'Associate'),
        ('paralegal', 'Paralegal'),
        ('junior', 'Junior Lawyer'),
        ('other', 'Other'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    default_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    effective_date = models.DateField()
    description = models.CharField(max_length=255, blank=True, null=True)
    
    # Tenant and Audit Fields
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='billing_rates'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_billing_rates'
    )
    
    # Timestamps and Soft Delete
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    objects = BillingManager()
    
    class Meta:
        db_table = 'billing_rates'
        verbose_name = 'Billing Rate'
        verbose_name_plural = 'Billing Rates'
        ordering = ['-effective_date', 'role']
        unique_together = [['role', 'effective_date', 'tenant']]
    
    def __str__(self):
        return f"{self.get_role_display()}: ${self.default_rate}/hr (effective {self.effective_date})"
    
    @property
    def is_deleted(self):
        """Check if the billing rate is soft-deleted."""
        return self.deleted_at is not None
    
    def soft_delete(self):
        """Mark the billing rate as deleted without actually removing it from the database."""
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore a soft-deleted billing rate."""
        self.deleted_at = None
        self.save()


class Invoice(models.Model):
    """
    Model representing an invoice for billing clients.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]
    
    invoice_number = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='invoices'
    )
    case = models.ForeignKey(
        'cases.Case',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices'
    )
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    subtotal = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=Decimal('0.00')
    )
    tax_rate = models.DecimalField(
        max_digits=5, 
        decimal_places=4,
        default=Decimal('0.0000'),
        help_text="Tax rate as decimal (e.g., 0.08 for 8%)"
    )
    tax_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=Decimal('0.00')
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    notes = models.TextField(blank=True, null=True)
    
    # Tenant and Audit Fields
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='invoices'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_invoices'
    )
    
    # Timestamps and Soft Delete
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    objects = InvoiceManager()
    
    class Meta:
        db_table = 'invoices'
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.client}"
    
    @property
    def is_deleted(self):
        """Check if the invoice is soft-deleted."""
        return self.deleted_at is not None
    
    def soft_delete(self):
        """Mark the invoice as deleted without actually removing it from the database."""
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore a soft-deleted invoice."""
        self.deleted_at = None
        self.save()
    
    def calculate_totals(self):
        """Calculate subtotal, tax, and total based on invoice items."""
        self.subtotal = sum(item.amount for item in self.items.all())
        self.tax_amount = self.subtotal * self.tax_rate
        self.total_amount = self.subtotal + self.tax_amount
        self.save()
    
    def get_absolute_url(self):
        """Return the absolute URL for this invoice."""
        from django.urls import reverse
        return reverse('billing:invoice_detail', kwargs={'pk': self.pk})
    
    @property
    def is_overdue(self):
        """Check if the invoice is overdue."""
        return (
            self.due_date < timezone.now().date() and 
            self.status in ['draft', 'sent']
        )


class InvoiceItem(models.Model):
    """
    Model representing individual items on an invoice.
    """
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='items'
    )
    description = models.CharField(max_length=255)
    quantity = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    rate = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Optional links to time entries or expenses
    time_entry = models.ForeignKey(
        'TimeEntry',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_items'
    )
    expense = models.ForeignKey(
        'Expense',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoice_items'
    )
    
    # Tenant and Audit Fields
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='invoice_items'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    objects = BillingManager()
    
    class Meta:
        db_table = 'invoice_items'
        verbose_name = 'Invoice Item'
        verbose_name_plural = 'Invoice Items'
        ordering = ['id']
    
    def __str__(self):
        return f"{self.description} - ${self.amount}"
    
    @property
    def is_deleted(self):
        """Check if the invoice item is soft-deleted."""
        return self.deleted_at is not None
    
    def soft_delete(self):
        """Mark the invoice item as deleted without actually removing it from the database."""
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore a soft-deleted invoice item."""
        self.deleted_at = None
        self.save()
    
    def save(self, *args, **kwargs):
        """Calculate amount before saving."""
        self.amount = self.quantity * self.rate
        super().save(*args, **kwargs)


class TimeEntry(models.Model):
    """
    Model representing time entries for billing purposes.
    """
    lawyer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='time_entries'
    )
    case = models.ForeignKey(
        'cases.Case',
        on_delete=models.CASCADE,
        related_name='time_entries'
    )
    hours = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    rate = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    description = models.TextField()
    date = models.DateField(default=timezone.now)
    is_billable = models.BooleanField(default=True)
    
    # Tenant and Audit Fields
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='time_entries'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_time_entries'
    )
    
    # Timestamps and Soft Delete
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    objects = TimeEntryManager()
    
    class Meta:
        db_table = 'time_entries'
        verbose_name = 'Time Entry'
        verbose_name_plural = 'Time Entries'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.lawyer.get_full_name()} - {self.case.case_number} - {self.hours} hours"
    
    @property
    def is_deleted(self):
        """Check if the time entry is soft-deleted."""
        return self.deleted_at is not None
    
    def soft_delete(self):
        """Mark the time entry as deleted without actually removing it from the database."""
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore a soft-deleted time entry."""
        self.deleted_at = None
        self.save()
    
    @property
    def amount(self):
        """Calculate the total amount for this time entry."""
        return self.hours * self.rate
    
    @property
    def is_billed(self):
        """Check if this time entry has been billed."""
        return self.invoice_items.exists()


class Expense(models.Model):
    """
    Model representing expenses that can be billed to clients.
    """
    CATEGORY_CHOICES = [
        ('travel', 'Travel'),
        ('filing', 'Court Filing'),
        ('research', 'Research'),
        ('printing', 'Printing/Copying'),
        ('expert', 'Expert Witness'),
        ('other', 'Other'),
    ]
    
    description = models.CharField(max_length=255)
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    receipt = models.FileField(
        upload_to='expense_receipts/',
        blank=True,
        null=True
    )
    date = models.DateField(default=timezone.now)
    is_reimbursable = models.BooleanField(default=True)
    case = models.ForeignKey(
        'cases.Case',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses'
    )
    
    # Tenant and Audit Fields
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='expenses'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_expenses'
    )
    
    # Timestamps and Soft Delete
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    objects = ExpenseManager()
    
    class Meta:
        db_table = 'expenses'
        verbose_name = 'Expense'
        verbose_name_plural = 'Expenses'
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.description} - ${self.amount}"
    
    @property
    def is_deleted(self):
        """Check if the expense is soft-deleted."""
        return self.deleted_at is not None
    
    def soft_delete(self):
        """Mark the expense as deleted without actually removing it from the database."""
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore a soft-deleted expense."""
        self.deleted_at = None
        self.save()
    
    @property
    def is_billed(self):
        """Check if this expense has been billed."""
        return self.invoice_items.exists()


class Payment(models.Model):
    """
    Model representing payments received for invoices.
    """
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('check', 'Check'),
        ('credit_card', 'Credit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('online', 'Online Payment'),
        ('other', 'Other'),
    ]
    
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    payment_date = models.DateField(default=timezone.now)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    reference = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    # Tenant and Audit Fields
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='payments'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_payments'
    )
    
    # Timestamps and Soft Delete
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    objects = PaymentManager()
    
    class Meta:
        db_table = 'payments'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-payment_date', '-created_at']
    
    def __str__(self):
        return f"Payment of ${self.amount} for Invoice {self.invoice.invoice_number}"
    
    @property
    def is_deleted(self):
        """Check if the payment is soft-deleted."""
        return self.deleted_at is not None
    
    def soft_delete(self):
        """Mark the payment as deleted without actually removing it from the database."""
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restore a soft-deleted payment."""
        self.deleted_at = None
        self.save()
    
    @property
    def remaining_balance(self):
        """Calculate the remaining balance on the invoice after this payment."""
        total_paid = sum(p.amount for p in self.invoice.payments.all())
        return self.invoice.total_amount - total_paid
