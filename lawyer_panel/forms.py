from django import forms
from django.utils import timezone
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Field, Div
from clients.models import Client
from cases.models import Case, CaseEvent
from documents.models import Document
from billing.models import TimeEntry, Expense


class ClientForm(forms.ModelForm):
    """Form for creating and editing clients."""
    
    class Meta:
        model = Client
        fields = ['first_name', 'last_name', 'email', 'phone', 'address', 'company', 'occupation', 'notes']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('first_name', css_class='form-group col-md-6 mb-0'),
                Column('last_name', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'email',
            'phone',
            'address',
            Row(
                Column('company', css_class='form-group col-md-6 mb-0'),
                Column('occupation', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'notes',
            Submit('submit', 'Save Client', css_class='btn btn-primary')
        )


class CaseForm(forms.ModelForm):
    """Form for creating and editing cases."""
    
    class Meta:
        model = Case
        fields = ['title', 'case_number', 'description', 'status', 'case_type', 'client', 'assigned_lawyers', 'start_date', 'end_date', 'notes']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Filter clients and lawyers by tenant
        if self.request and hasattr(self.request, 'tenant'):
            self.fields['client'].queryset = Client.objects.filter(tenant=self.request.tenant, deleted_at__isnull=True)
            self.fields['assigned_lawyers'].queryset = self.request.tenant.users.filter(role__in=['lawyer', 'admin'])
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('title', css_class='form-group col-md-8 mb-0'),
                Column('case_number', css_class='form-group col-md-4 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('status', css_class='form-group col-md-6 mb-0'),
                Column('case_type', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'client',
            'assigned_lawyers',
            Row(
                Column('start_date', css_class='form-group col-md-6 mb-0'),
                Column('end_date', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'description',
            'notes',
            Submit('submit', 'Save Case', css_class='btn btn-primary')
        )


class CaseEventForm(forms.ModelForm):
    """Form for adding events to cases."""
    
    class Meta:
        model = CaseEvent
        fields = ['event_type', 'title', 'description', 'event_date']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'event_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default event date to current datetime
        if not self.instance.pk:
            self.fields['event_date'].initial = timezone.now()
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'event_type',
            'title',
            'description',
            'event_date',
            Submit('submit', 'Add Event', css_class='btn btn-primary')
        )


class DocumentForm(forms.ModelForm):
    """Form for uploading and editing documents."""
    
    class Meta:
        model = Document
        fields = ['title', 'description', 'file', 'category', 'access_level', 'case', 'client', 'tags']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'tags': forms.TextInput(attrs={'placeholder': 'Enter tags separated by commas'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Filter cases and clients by tenant
        if self.request and hasattr(self.request, 'tenant'):
            self.fields['case'].queryset = Case.objects.filter(tenant=self.request.tenant, deleted_at__isnull=True)
            self.fields['client'].queryset = Client.objects.filter(tenant=self.request.tenant, deleted_at__isnull=True)
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'title',
            'description',
            'file',
            Row(
                Column('category', css_class='form-group col-md-6 mb-0'),
                Column('access_level', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('case', css_class='form-group col-md-6 mb-0'),
                Column('client', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'tags',
            Submit('submit', 'Upload Document', css_class='btn btn-primary')
        )


class TimeEntryForm(forms.ModelForm):
    """Form for creating and editing time entries."""
    
    class Meta:
        model = TimeEntry
        fields = ['case', 'hours', 'rate', 'description', 'date', 'is_billable']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Filter cases by tenant and assigned lawyer
        if self.request and hasattr(self.request, 'tenant'):
            self.fields['case'].queryset = Case.objects.filter(
                tenant=self.request.tenant, 
                deleted_at__isnull=True,
                assigned_lawyers=self.request.user
            )
        
        # Set default values
        if not self.instance.pk:
            self.fields['date'].initial = timezone.now().date()
            self.fields['lawyer'].initial = self.request.user
            self.fields['rate'].initial = self._get_default_rate()
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'case',
            Row(
                Column('hours', css_class='form-group col-md-4 mb-0'),
                Column('rate', css_class='form-group col-md-4 mb-0'),
                Column('is_billable', css_class='form-group col-md-4 mb-0'),
                css_class='form-row'
            ),
            'date',
            'description',
            Submit('submit', 'Log Time', css_class='btn btn-primary')
        )
    
    def _get_default_rate(self):
        """Get default billing rate for the current user."""
        from billing.models import BillingRate
        try:
            # Try to get the latest billing rate for the user's role
            role_mapping = {
                'admin': 'partner',
                'lawyer': 'associate',
                'paralegal': 'paralegal',
            }
            role = role_mapping.get(self.request.user.role, 'associate')
            rate = BillingRate.objects.filter(
                tenant=self.request.tenant,
                role=role
            ).latest('effective_date')
            return rate.default_rate
        except Exception:
            return 150.00  # Default fallback rate


class ExpenseForm(forms.ModelForm):
    """Form for creating and editing expenses."""
    
    class Meta:
        model = Expense
        fields = ['description', 'amount', 'category', 'receipt', 'date', 'is_reimbursable', 'case']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Filter cases by tenant and assigned lawyer
        if self.request and hasattr(self.request, 'tenant'):
            self.fields['case'].queryset = Case.objects.filter(
                tenant=self.request.tenant, 
                deleted_at__isnull=True,
                assigned_lawyers=self.request.user
            )
        
        # Set default values
        if not self.instance.pk:
            self.fields['date'].initial = timezone.now().date()
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'description',
            Row(
                Column('amount', css_class='form-group col-md-6 mb-0'),
                Column('category', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'receipt',
            Row(
                Column('date', css_class='form-group col-md-6 mb-0'),
                Column('is_reimbursable', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'case',
            Submit('submit', 'Add Expense', css_class='btn btn-primary')
        )


class QuickSearchForm(forms.Form):
    """Form for quick search across different modules."""
    query = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search cases, clients, documents...',
            'autocomplete': 'off'
        })
    )
    search_type = forms.ChoiceField(
        choices=[
            ('all', 'All'),
            ('cases', 'Cases'),
            ('clients', 'Clients'),
            ('documents', 'Documents'),
        ],
        initial='all',
        widget=forms.Select(attrs={'class': 'form-control'})
    )