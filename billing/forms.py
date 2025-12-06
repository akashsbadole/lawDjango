from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from .models import (
    BillingRate, Invoice, InvoiceItem, TimeEntry, 
    Expense, Payment
)

User = get_user_model()


class BillingRateForm(forms.ModelForm):
    """
    Form for creating and updating billing rates.
    """
    class Meta:
        model = BillingRate
        fields = [
            'role',
            'default_rate',
            'effective_date',
            'description',
        ]
        widgets = {
            'role': forms.Select(attrs={
                'class': 'form-control'
            }),
            'default_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'effective_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter description (optional)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False


class InvoiceForm(forms.ModelForm):
    """
    Form for creating and updating invoices.
    """
    class Meta:
        model = Invoice
        fields = [
            'client',
            'case',
            'issue_date',
            'due_date',
            'tax_rate',
            'status',
            'notes',
        ]
        widgets = {
            'client': forms.Select(attrs={
                'class': 'form-control'
            }),
            'case': forms.Select(attrs={
                'class': 'form-control'
            }),
            'issue_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'tax_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.0001',
                'min': '0',
                'max': '1'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter notes (optional)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            # Filter client and case by tenant
            self.fields['client'].queryset = self.fields['client'].queryset.filter(tenant=self.tenant)
            self.fields['case'].queryset = self.fields['case'].queryset.filter(tenant=self.tenant)
        
        # Make optional fields optional
        self.fields['case'].required = False
        self.fields['notes'].required = False
        
        # Set default values for new invoices
        if not self.instance.pk:
            self.fields['issue_date'].initial = timezone.now().date()
            self.fields['due_date'].initial = (timezone.now() + timezone.timedelta(days=30)).date()
            self.fields['tax_rate'].initial = Decimal('0.0000')
        
        # Add empty labels
        self.fields['case'].empty_label = "-- Select Case (Optional) --"
    
    def clean_due_date(self):
        """Validate that due date is after issue date."""
        issue_date = self.cleaned_data.get('issue_date')
        due_date = self.cleaned_data.get('due_date')
        
        if issue_date and due_date and due_date < issue_date:
            raise forms.ValidationError(_("Due date must be after issue date."))
        
        return due_date


class InvoiceItemForm(forms.ModelForm):
    """
    Form for creating and updating invoice items.
    """
    class Meta:
        model = InvoiceItem
        fields = [
            'description',
            'quantity',
            'rate',
        ]
        widgets = {
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter description'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
        }
    
    def clean(self):
        """Calculate amount based on quantity and rate."""
        cleaned_data = super().clean()
        quantity = cleaned_data.get('quantity')
        rate = cleaned_data.get('rate')
        
        if quantity and rate:
            cleaned_data['amount'] = quantity * rate
        
        return cleaned_data


class TimeEntryForm(forms.ModelForm):
    """
    Form for creating and updating time entries.
    """
    class Meta:
        model = TimeEntry
        fields = [
            'lawyer',
            'case',
            'hours',
            'rate',
            'description',
            'date',
            'is_billable',
        ]
        widgets = {
            'lawyer': forms.Select(attrs={
                'class': 'form-control'
            }),
            'case': forms.Select(attrs={
                'class': 'form-control'
            }),
            'hours': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter work description'
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'is_billable': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            # Filter case by tenant
            self.fields['case'].queryset = self.fields['case'].queryset.filter(tenant=self.tenant)
            
            # Filter lawyers by tenant
            self.fields['lawyer'].queryset = User.objects.filter(tenant=self.tenant, role__in=['partner', 'associate', 'paralegal', 'junior'])
        
        # Set default values
        if not self.instance.pk:
            self.fields['date'].initial = timezone.now().date()
            self.fields['is_billable'].initial = True
            
            # Set default lawyer to current user if they have a lawyer role
            if self.user and self.user.role in ['partner', 'associate', 'paralegal', 'junior']:
                self.fields['lawyer'].initial = self.user
    
    def clean_hours(self):
        """Validate that hours is a positive number."""
        hours = self.cleaned_data.get('hours')
        if hours <= 0:
            raise forms.ValidationError(_("Hours must be a positive number."))
        return hours


class ExpenseForm(forms.ModelForm):
    """
    Form for creating and updating expenses.
    """
    class Meta:
        model = Expense
        fields = [
            'description',
            'amount',
            'category',
            'receipt',
            'date',
            'is_reimbursable',
            'case',
        ]
        widgets = {
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter expense description'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'receipt': forms.FileInput(attrs={
                'class': 'form-control'
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'is_reimbursable': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'case': forms.Select(attrs={
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            # Filter case by tenant
            self.fields['case'].queryset = self.fields['case'].queryset.filter(tenant=self.tenant)
        
        # Set default values
        if not self.instance.pk:
            self.fields['date'].initial = timezone.now().date()
            self.fields['is_reimbursable'].initial = True
        
        # Make case optional
        self.fields['case'].required = False
        self.fields['receipt'].required = False
        
        # Add empty label
        self.fields['case'].empty_label = "-- Select Case (Optional) --"
    
    def clean_amount(self):
        """Validate that amount is a positive number."""
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise forms.ValidationError(_("Amount must be a positive number."))
        return amount


class PaymentForm(forms.ModelForm):
    """
    Form for creating and updating payments.
    """
    class Meta:
        model = Payment
        fields = [
            'invoice',
            'amount',
            'payment_date',
            'payment_method',
            'reference',
            'notes',
        ]
        widgets = {
            'invoice': forms.Select(attrs={
                'class': 'form-control'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'payment_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'payment_method': forms.Select(attrs={
                'class': 'form-control'
            }),
            'reference': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter reference number (optional)'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter notes (optional)'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            # Filter invoices by tenant and only show unpaid invoices
            self.fields['invoice'].queryset = Invoice.objects.filter(
                tenant=self.tenant,
                status__in=['draft', 'sent']
            )
        
        # Set default values
        if not self.instance.pk:
            self.fields['payment_date'].initial = timezone.now().date()
        
        # Make optional fields optional
        self.fields['reference'].required = False
        self.fields['notes'].required = False
    
    def clean_amount(self):
        """Validate that amount is a positive number."""
        amount = self.cleaned_data.get('amount')
        if amount <= 0:
            raise forms.ValidationError(_("Amount must be a positive number."))
        return amount
    
    def clean(self):
        """Validate that payment amount doesn't exceed invoice balance."""
        cleaned_data = super().clean()
        invoice = cleaned_data.get('invoice')
        amount = cleaned_data.get('amount')
        
        if invoice and amount:
            # Calculate remaining balance
            total_paid = sum(p.amount for p in invoice.payments.all())
            remaining_balance = invoice.total_amount - total_paid
            
            if amount > remaining_balance:
                raise forms.ValidationError(
                    _("Payment amount (${:.2f}) exceeds remaining balance (${:.2f}).").format(
                        amount, remaining_balance
                    )
                )
        
        return cleaned_data


class InvoiceSearchForm(forms.Form):
    """
    Form for searching invoices.
    """
    STATUS_CHOICES = [
        ('', 'All Statuses'),
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]
    
    query = forms.CharField(
        label=_('Search'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by invoice number or client...',
            'autocomplete': 'off'
        }),
        required=False
    )
    status = forms.ChoiceField(
        label=_('Status'),
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        required=False
    )
    date_from = forms.DateField(
        label=_('From'),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        required=False
    )
    date_to = forms.DateField(
        label=_('To'),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        required=False
    )


class TimeEntrySearchForm(forms.Form):
    """
    Form for searching time entries.
    """
    query = forms.CharField(
        label=_('Search'),
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by description or case...',
            'autocomplete': 'off'
        }),
        required=False
    )
    lawyer = forms.ModelChoiceField(
        label=_('Lawyer'),
        queryset=User.objects.none(),
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        required=False
    )
    case = forms.ModelChoiceField(
        label=_('Case'),
        queryset=None,  # Will be set in __init__
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        required=False
    )
    date_from = forms.DateField(
        label=_('From'),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        required=False
    )
    date_to = forms.DateField(
        label=_('To'),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        required=False
    )
    is_billable = forms.BooleanField(
        label=_('Billable only'),
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        if self.tenant:
            # Filter lawyers and cases by tenant
            self.fields['lawyer'].queryset = User.objects.filter(
                tenant=self.tenant,
                role__in=['partner', 'associate', 'paralegal', 'junior']
            )
            self.fields['case'].queryset = None  # Will be set based on cases app
        
        # Add empty labels
        self.fields['lawyer'].empty_label = "-- All Lawyers --"
        self.fields['case'].empty_label = "-- All Cases --"