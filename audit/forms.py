from django import forms
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

from .models import AuditLog, ActivityLog, SecurityEvent, LoginLog

User = get_user_model()


class AuditLogFilterForm(forms.Form):
    """
    Form for filtering audit logs.
    """
    ACTION_CHOICES = [('', 'All Actions')] + AuditLog.ACTION_CHOICES
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    model_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Model name...'
        })
    )
    
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        empty_label="All Users",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    
    date_to = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    
    ip_address = forms.GenericIPAddressField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'IP Address...'
        })
    )
    
    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        # Filter users by tenant if available
        if tenant and 'user' in self.fields:
            self.fields['user'].queryset = User.objects.filter(tenant=tenant)
        
        # Set default date range to last 7 days
        if not kwargs.get('data'):
            self.fields['date_from'].initial = timezone.now() - timedelta(days=7)


class ActivityLogFilterForm(forms.Form):
    """
    Form for filtering activity logs.
    """
    ACTIVITY_TYPES = [('', 'All Activities')] + ActivityLog.ACTIVITY_TYPES
    
    activity_type = forms.ChoiceField(
        choices=ACTIVITY_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        empty_label="All Users",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    
    date_to = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search description...'
        })
    )
    
    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        # Filter users by tenant if available
        if tenant and 'user' in self.fields:
            self.fields['user'].queryset = User.objects.filter(tenant=tenant)
        
        # Set default date range to last 7 days
        if not kwargs.get('data'):
            self.fields['date_from'].initial = timezone.now() - timedelta(days=7)


class SecurityEventFilterForm(forms.Form):
    """
    Form for filtering security events.
    """
    EVENT_TYPES = [('', 'All Events')] + SecurityEvent.EVENT_TYPES
    SEVERITY_LEVELS = [('', 'All Severities')] + SecurityEvent.SEVERITY_LEVELS
    
    event_type = forms.ChoiceField(
        choices=EVENT_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    severity = forms.ChoiceField(
        choices=SEVERITY_LEVELS,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    resolved = forms.ChoiceField(
        choices=[
            ('', 'All'),
            ('True', 'Resolved'),
            ('False', 'Unresolved'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        empty_label="All Users",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    
    date_to = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    
    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        # Filter users by tenant if available
        if tenant and 'user' in self.fields:
            self.fields['user'].queryset = User.objects.filter(tenant=tenant)
        
        # Set default date range to last 7 days
        if not kwargs.get('data'):
            self.fields['date_from'].initial = timezone.now() - timedelta(days=7)


class LoginLogFilterForm(forms.Form):
    """
    Form for filtering login logs.
    """
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        empty_label="All Users",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    login_successful = forms.ChoiceField(
        choices=[
            ('', 'All'),
            ('True', 'Successful'),
            ('False', 'Failed'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    
    date_to = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    
    ip_address = forms.GenericIPAddressField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'IP Address...'
        })
    )
    
    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        # Filter users by tenant if available
        if tenant and 'user' in self.fields:
            self.fields['user'].queryset = User.objects.filter(tenant=tenant)
        
        # Set default date range to last 7 days
        if not kwargs.get('data'):
            self.fields['date_from'].initial = timezone.now() - timedelta(days=7)


class AuditExportForm(forms.Form):
    """
    Form for exporting audit data.
    """
    EXPORT_TYPES = [
        ('csv', 'CSV'),
        ('json', 'JSON'),
    ]
    
    LOG_TYPES = [
        ('audit', 'Audit Logs'),
        ('activity', 'Activity Logs'),
        ('security', 'Security Events'),
        ('login', 'Login Logs'),
    ]
    
    export_type = forms.ChoiceField(
        choices=EXPORT_TYPES,
        initial='csv',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    log_type = forms.ChoiceField(
        choices=LOG_TYPES,
        initial='audit',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_from = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        }),
        help_text="Export records from this date onwards (optional)"
    )
    
    date_to = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        }),
        help_text="Export records up to this date (optional)"
    )
    
    include_sensitive = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Include sensitive information like IP addresses and user agents"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set default date range to last 30 days
        if not kwargs.get('data'):
            self.fields['date_from'].initial = timezone.now() - timedelta(days=30)


class SecurityEventResolutionForm(forms.Form):
    """
    Form for resolving security events.
    """
    resolution_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter resolution notes...'
        }),
        required=True,
        help_text="Provide details about how this security event was resolved"
    )


class BulkActionForm(forms.Form):
    """
    Form for bulk actions on audit records.
    """
    ACTION_CHOICES = [
        ('', 'Select Action'),
        ('resolve', 'Resolve Security Events'),
        ('export', 'Export Selected'),
        ('delete', 'Delete Selected (Admin Only)'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    selected_items = forms.CharField(
        widget=forms.HiddenInput(),
        required=True
    )
    
    confirmation = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Confirm this action"
    )
    
    def clean_selected_items(self):
        selected_items = self.cleaned_data.get('selected_items', '')
        if not selected_items:
            raise forms.ValidationError("No items selected")
        
        try:
            # Parse comma-separated IDs
            item_ids = [int(id.strip()) for id in selected_items.split(',') if id.strip()]
            return item_ids
        except ValueError:
            raise forms.ValidationError("Invalid item IDs")
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        confirmation = cleaned_data.get('confirmation')
        
        if action in ['delete'] and not confirmation:
            raise forms.ValidationError("Confirmation is required for destructive actions")
        
        return cleaned_data


class AuditRetentionForm(forms.Form):
    """
    Form for configuring audit log retention policies.
    """
    RETENTION_CHOICES = [
        (30, '30 days'),
        (60, '60 days'),
        (90, '90 days'),
        (180, '180 days'),
        (365, '1 year'),
        (730, '2 years'),
        (1825, '5 years'),
        (0, 'Keep forever'),
    ]
    
    audit_log_retention = forms.ChoiceField(
        choices=RETENTION_CHOICES,
        initial=365,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="How long to keep audit logs"
    )
    
    activity_log_retention = forms.ChoiceField(
        choices=RETENTION_CHOICES,
        initial=180,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="How long to keep activity logs"
    )
    
    login_log_retention = forms.ChoiceField(
        choices=RETENTION_CHOICES,
        initial=90,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="How long to keep login logs"
    )
    
    security_event_retention = forms.ChoiceField(
        choices=RETENTION_CHOICES,
        initial=1825,  # 5 years for security events
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="How long to keep security events (recommended: 5+ years)"
    )
    
    auto_cleanup_enabled = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Enable automatic cleanup of old audit records"
    )
    
    cleanup_frequency = forms.ChoiceField(
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ],
        initial='weekly',
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="How often to run cleanup"
    )


class AuditReportForm(forms.Form):
    """
    Form for generating audit reports.
    """
    REPORT_TYPES = [
        ('user_activity', 'User Activity Report'),
        ('security_summary', 'Security Summary Report'),
        ('login_analytics', 'Login Analytics Report'),
        ('data_access', 'Data Access Report'),
        ('compliance', 'Compliance Report'),
    ]
    
    DATE_RANGE_CHOICES = [
        ('7', 'Last 7 days'),
        ('30', 'Last 30 days'),
        ('90', 'Last 90 days'),
        ('365', 'Last year'),
        ('custom', 'Custom range'),
    ]
    
    report_type = forms.ChoiceField(
        choices=REPORT_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_range = forms.ChoiceField(
        choices=DATE_RANGE_CHOICES,
        initial='30',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    custom_date_from = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    
    custom_date_to = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control'}),
        help_text="Filter by specific users (leave empty for all users)"
    )
    
    include_charts = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Include charts and graphs in the report"
    )
    
    email_report = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Email report to me when ready"
    )
    
    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        
        # Filter users by tenant if available
        if tenant and 'users' in self.fields:
            self.fields['users'].queryset = User.objects.filter(tenant=tenant)
    
    def clean(self):
        cleaned_data = super().clean()
        date_range = cleaned_data.get('date_range')
        custom_date_from = cleaned_data.get('custom_date_from')
        custom_date_to = cleaned_data.get('custom_date_to')
        
        if date_range == 'custom':
            if not custom_date_from:
                raise forms.ValidationError("Custom date range requires a start date")
            if not custom_date_to:
                raise forms.ValidationError("Custom date range requires an end date")
            if custom_date_from >= custom_date_to:
                raise forms.ValidationError("Start date must be before end date")
        
        return cleaned_data