from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, Submit, Reset, HTML
from crispy_forms.bootstrap import FormActions

from tenants.models import Tenant
from .models import SystemSettings, AdminNote, SystemAnnouncement

User = get_user_model()


class SystemSettingsForm(forms.ModelForm):
    """Form for editing system-wide settings."""
    
    class Meta:
        model = SystemSettings
        fields = [
            'platform_name', 'platform_version', 'support_email', 'support_phone',
            'allow_public_registration', 'require_admin_approval', 'default_trial_days',
            'max_tenants', 'max_users_per_tenant', 'enforce_2fa_for_admins',
            'session_timeout_minutes', 'auto_backup_enabled', 'backup_retention_days',
            'system_alerts_enabled', 'email_notifications_enabled', 'maintenance_mode',
            'maintenance_message', 'custom_css', 'custom_js', 'api_rate_limit_enabled',
            'api_rate_limit_requests'
        ]
        widgets = {
            'maintenance_message': forms.Textarea(attrs={'rows': 3}),
            'custom_css': forms.Textarea(attrs={'rows': 10, 'class': 'font-monospace'}),
            'custom_js': forms.Textarea(attrs={'rows': 10, 'class': 'font-monospace'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                'Platform Information',
                Row(
                    Column('platform_name', css_class='form-group col-md-8 mb-0'),
                    Column('platform_version', css_class='form-group col-md-4 mb-0'),
                    css_class='form-row'
                ),
            ),
            Fieldset(
                'Contact Information',
                Row(
                    Column('support_email', css_class='form-group col-md-8 mb-0'),
                    Column('support_phone', css_class='form-group col-md-4 mb-0'),
                    css_class='form-row'
                ),
            ),
            Fieldset(
                'Registration Settings',
                'allow_public_registration',
                'require_admin_approval',
                'default_trial_days',
            ),
            Fieldset(
                'System Limits',
                Row(
                    Column('max_tenants', css_class='form-group col-md-6 mb-0'),
                    Column('max_users_per_tenant', css_class='form-group col-md-6 mb-0'),
                    css_class='form-row'
                ),
            ),
            Fieldset(
                'Security Settings',
                'enforce_2fa_for_admins',
                'session_timeout_minutes',
            ),
            Fieldset(
                'Backup Settings',
                'auto_backup_enabled',
                'backup_retention_days',
            ),
            Fieldset(
                'Notification Settings',
                'system_alerts_enabled',
                'email_notifications_enabled',
            ),
            Fieldset(
                'Maintenance Mode',
                'maintenance_mode',
                'maintenance_message',
            ),
            Fieldset(
                'Custom Styling',
                'custom_css',
                'custom_js',
            ),
            Fieldset(
                'API Settings',
                'api_rate_limit_enabled',
                'api_rate_limit_requests',
            ),
            FormActions(
                Submit('submit', 'Save Settings', css_class='btn-primary'),
                Reset('reset', 'Reset', css_class='btn-secondary'),
            )
        )
        
        # Add help text and placeholders
        self.fields['support_email'].widget.attrs.update({
            'placeholder': 'support@example.com'
        })
        self.fields['support_phone'].widget.attrs.update({
            'placeholder': '+1-555-123-4567'
        })
        self.fields['default_trial_days'].widget.attrs.update({
            'min': 0,
            'max': 365
        })
        self.fields['max_users_per_tenant'].widget.attrs.update({
            'min': 1,
            'max': 1000
        })
        self.fields['session_timeout_minutes'].widget.attrs.update({
            'min': 5,
            'max': 1440
        })
        self.fields['backup_retention_days'].widget.attrs.update({
            'min': 1,
            'max': 365
        })
        self.fields['api_rate_limit_requests'].widget.attrs.update({
            'min': 10,
            'max': 10000
        })


class AdminNoteForm(forms.ModelForm):
    """Form for creating and editing admin notes."""
    
    class Meta:
        model = AdminNote
        fields = [
            'tenant', 'note_type', 'title', 'content', 'is_private',
            'requires_follow_up', 'follow_up_date', 'related_user'
        ]
        widgets = {
            'content': forms.Textarea(attrs={'rows': 5}),
            'follow_up_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('tenant', css_class='form-group col-md-6 mb-0'),
                Column('note_type', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            'title',
            'content',
            Row(
                Column('is_private', css_class='form-group col-md-4 mb-0'),
                Column('requires_follow_up', css_class='form-group col-md-4 mb-0'),
                Column('follow_up_date', css_class='form-group col-md-4 mb-0'),
                css_class='form-row'
            ),
            'related_user',
            FormActions(
                Submit('submit', 'Save Note', css_class='btn-primary'),
                Reset('reset', 'Reset', css_class='btn-secondary'),
            )
        )
        
        # Filter users for related_user field
        if self.user and self.user.is_superuser:
            self.fields['related_user'].queryset = User.objects.all().order_by('email')
        else:
            self.fields['related_user'].queryset = User.objects.none()
        
        # Set minimum date for follow_up_date to now
        if not self.instance.pk:  # Only for new notes
            self.fields['follow_up_date'].widget.attrs.update({
                'min': timezone.now().strftime('%Y-%m-%dT%H:%M')
            })
    
    def clean_follow_up_date(self):
        """Validate that follow_up_date is in the future if requires_follow_up is checked."""
        follow_up_date = self.cleaned_data.get('follow_up_date')
        requires_follow_up = self.cleaned_data.get('requires_follow_up')
        
        if requires_follow_up and not follow_up_date:
            raise ValidationError("Follow-up date is required when follow-up is required.")
        
        if follow_up_date and follow_up_date <= timezone.now():
            raise ValidationError("Follow-up date must be in the future.")
        
        return follow_up_date


class SystemAnnouncementForm(forms.ModelForm):
    """Form for creating and editing system announcements."""
    
    class Meta:
        model = SystemAnnouncement
        fields = [
            'title', 'content', 'announcement_type', 'target_all_tenants',
            'target_tenants', 'target_roles', 'is_active', 'start_date',
            'end_date', 'show_on_login', 'show_on_dashboard', 'show_as_banner',
            'is_dismissible', 'priority'
        ]
        widgets = {
            'content': forms.Textarea(attrs={'rows': 5}),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'target_roles': forms.CheckboxSelectMultiple(),
            'target_tenants': forms.CheckboxSelectMultiple(),
        }
    
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('lawyer', 'Lawyer'),
        ('paralegal', 'Paralegal'),
        ('billing_manager', 'Billing Manager'),
        ('staff', 'Staff'),
    ]
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Row(
                Column('title', css_class='form-group col-md-8 mb-0'),
                Column('announcement_type', css_class='form-group col-md-4 mb-0'),
                css_class='form-row'
            ),
            'content',
            Fieldset(
                'Targeting',
                'target_all_tenants',
                'target_tenants',
                'target_roles',
            ),
            Fieldset(
                'Scheduling',
                'is_active',
                Row(
                    Column('start_date', css_class='form-group col-md-6 mb-0'),
                    Column('end_date', css_class='form-group col-md-6 mb-0'),
                    css_class='form-row'
                ),
            ),
            Fieldset(
                'Display Options',
                Row(
                    Column('show_on_login', css_class='form-group col-md-3 mb-0'),
                    Column('show_on_dashboard', css_class='form-group col-md-3 mb-0'),
                    Column('show_as_banner', css_class='form-group col-md-3 mb-0'),
                    Column('is_dismissible', css_class='form-group col-md-3 mb-0'),
                    css_class='form-row'
                ),
            ),
            'priority',
            FormActions(
                Submit('submit', 'Save Announcement', css_class='btn-primary'),
                Reset('reset', 'Reset', css_class='btn-secondary'),
            )
        )
        
        # Set choices for target_roles
        self.fields['target_roles'].choices = self.ROLE_CHOICES
        
        # Set minimum date for start_date to now
        if not self.instance.pk:  # Only for new announcements
            self.fields['start_date'].widget.attrs.update({
                'min': timezone.now().strftime('%Y-%m-%dT%H:%M')
            })
        
        # Set minimum date for end_date to start_date
        if self.instance and self.instance.start_date:
            self.fields['end_date'].widget.attrs.update({
                'min': self.instance.start_date.strftime('%Y-%m-%dT%H:%M')
            })
        
        # Set priority range
        self.fields['priority'].widget.attrs.update({
            'min': 0,
            'max': 100
        })
    
    def clean_end_date(self):
        """Validate that end_date is after start_date."""
        end_date = self.cleaned_data.get('end_date')
        start_date = self.cleaned_data.get('start_date')
        
        if end_date and start_date and end_date <= start_date:
            raise ValidationError("End date must be after start date.")
        
        return end_date
    
    def clean(self):
        """Clean method to validate form-wide constraints."""
        cleaned_data = super().clean()
        target_all_tenants = cleaned_data.get('target_all_tenants')
        target_tenants = cleaned_data.get('target_tenants')
        
        if not target_all_tenants and not target_tenants:
            raise ValidationError("Either target all tenants or select specific tenants.")
        
        return cleaned_data


class TenantEditForm(forms.ModelForm):
    """Form for editing tenant information in super admin."""
    
    class Meta:
        model = Tenant
        fields = [
            'name', 'plan', 'max_users', 'max_storage_mb', 'is_active'
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'name',
            Row(
                Column('plan', css_class='form-group col-md-6 mb-0'),
                Column('is_active', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            Row(
                Column('max_users', css_class='form-group col-md-6 mb-0'),
                Column('max_storage_mb', css_class='form-group col-md-6 mb-0'),
                css_class='form-row'
            ),
            FormActions(
                Submit('submit', 'Update Tenant', css_class='btn-primary'),
                Reset('reset', 'Reset', css_class='btn-secondary'),
            )
        )
        
        # Add validation attributes
        self.fields['max_users'].widget.attrs.update({
            'min': 1,
            'max': 1000
        })
        self.fields['max_storage_mb'].widget.attrs.update({
            'min': 100,
            'max': 1024000  # 1TB
        })
    
    def clean_max_users(self):
        """Validate max_users field."""
        max_users = self.cleaned_data.get('max_users')
        current_users = self.instance.get_current_user_count()
        
        if max_users < current_users:
            raise ValidationError(
                f"Cannot set max users to {max_users} as this tenant already has {current_users} users."
            )
        
        return max_users
    
    def clean_max_storage_mb(self):
        """Validate max_storage_mb field."""
        max_storage = self.cleaned_data.get('max_storage_mb')
        current_storage = self.instance.get_storage_used()
        
        if max_storage < current_storage:
            raise ValidationError(
                f"Cannot set max storage to {max_storage}MB as this tenant already uses {current_storage}MB."
            )
        
        return max_storage


class BulkTenantForm(forms.Form):
    """Form for bulk operations on tenants."""
    
    ACTION_CHOICES = [
        ('enable', 'Enable Tenants'),
        ('disable', 'Disable Tenants'),
        ('delete', 'Delete Tenants'),
    ]
    
    action = forms.ChoiceField(choices=ACTION_CHOICES, widget=forms.RadioSelect)
    confirmation = forms.CharField(
        max_length=100,
        help_text="Type 'CONFIRM' to proceed with the bulk operation"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'action',
            'confirmation',
            FormActions(
                Submit('submit', 'Execute Bulk Operation', css_class='btn-danger'),
                Reset('reset', 'Cancel', css_class='btn-secondary'),
            )
        )
    
    def clean_confirmation(self):
        """Validate that user has typed CONFIRM."""
        confirmation = self.cleaned_data.get('confirmation')
        
        if confirmation.upper() != 'CONFIRM':
            raise ValidationError("You must type 'CONFIRM' to proceed with this operation.")
        
        return confirmation


class TenantSearchForm(forms.Form):
    """Form for searching and filtering tenants."""
    
    search = forms.CharField(
        max_length=255,
        required=False,
        help_text="Search by name or slug"
    )
    status = forms.ChoiceField(
        choices=[('', 'All Status'), ('active', 'Active'), ('inactive', 'Inactive')],
        required=False
    )
    plan = forms.ChoiceField(
        choices=[('', 'All Plans')] + Tenant.PLAN_CHOICES,
        required=False
    )
    order_by = forms.ChoiceField(
        choices=[
            ('-created_at', 'Newest First'),
            ('created_at', 'Oldest First'),
            ('name', 'Name (A-Z)'),
            ('-name', 'Name (Z-A)'),
            ('-active', 'Active First'),
            ('active', 'Inactive First'),
        ],
        required=False,
        initial='-created_at'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.form_method = 'get'
        self.helper.form_class = 'form-inline'
        self.helper.layout = Layout(
            Row(
                Column('search', css_class='form-group col-md-3 mb-0'),
                Column('status', css_class='form-group col-md-2 mb-0'),
                Column('plan', css_class='form-group col-md-2 mb-0'),
                Column('order_by', css_class='form-group col-md-2 mb-0'),
                Column(
                    FormActions(
                        Submit('submit', 'Filter', css_class='btn-sm btn-primary'),
                        css_class='form-group mb-0'
                    ),
                    css_class='form-group col-md-3 mb-0'
                ),
                css_class='form-row'
            )
        )


class UserSearchForm(forms.Form):
    """Form for searching and filtering users."""
    
    search = forms.CharField(
        max_length=255,
        required=False,
        help_text="Search by email, name, or tenant"
    )
    role = forms.ChoiceField(
        choices=[('', 'All Roles')] + User._meta.get_field('role').choices,
        required=False
    )
    tenant = forms.ModelChoiceField(
        queryset=Tenant.objects.all(),
        empty_label="All Tenants",
        required=False
    )
    status = forms.ChoiceField(
        choices=[('', 'All Status'), ('active', 'Active'), ('inactive', 'Inactive')],
        required=False
    )
    order_by = forms.ChoiceField(
        choices=[
            ('-date_joined', 'Newest First'),
            ('date_joined', 'Oldest First'),
            ('email', 'Email (A-Z)'),
            ('-email', 'Email (Z-A)'),
            ('first_name', 'First Name (A-Z)'),
            ('-first_name', 'First Name (Z-A)'),
        ],
        required=False,
        initial='-date_joined'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.form_method = 'get'
        self.helper.form_class = 'form-inline'
        self.helper.layout = Layout(
            Row(
                Column('search', css_class='form-group col-md-3 mb-0'),
                Column('role', css_class='form-group col-md-2 mb-0'),
                Column('tenant', css_class='form-group col-md-2 mb-0'),
                Column('status', css_class='form-group col-md-2 mb-0'),
                Column('order_by', css_class='form-group col-md-1 mb-0'),
                Column(
                    FormActions(
                        Submit('submit', 'Filter', css_class='btn-sm btn-primary'),
                        css_class='form-group mb-0'
                    ),
                    css_class='form-group col-md-2 mb-0'
                ),
                css_class='form-row'
            )
        )


class DateRangeForm(forms.Form):
    """Form for date range filtering."""
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.helper = FormHelper()
        self.helper.form_method = 'get'
        self.helper.form_class = 'form-inline'
        self.helper.layout = Layout(
            Row(
                Column('date_from', css_class='form-group col-md-4 mb-0'),
                Column('date_to', css_class='form-group col-md-4 mb-0'),
                Column(
                    FormActions(
                        Submit('submit', 'Filter', css_class='btn-sm btn-primary'),
                        css_class='form-group mb-0'
                    ),
                    css_class='form-group col-md-4 mb-0'
                ),
                css_class='form-row'
            )
        )
    
    def clean(self):
        """Validate that date_from is before date_to."""
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError("Start date must be before end date.")
        
        return cleaned_data