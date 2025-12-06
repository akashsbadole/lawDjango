"""
Forms for multi-tenant application.

This module provides forms that handle tenant-specific functionality,
including tenant registration, settings, and management.
"""

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from allauth.account.forms import SignupForm as BaseSignupForm
from .models import Tenant, TenantSettings


User = get_user_model()


class TenantSignupForm(BaseSignupForm):
    """
    Sign-up form that includes tenant selection.
    
    This form extends the django-allauth signup form
    to include tenant selection for multi-tenant applications.
    """
    
    tenant = forms.ModelChoiceField(
        queryset=Tenant.objects.filter(status='active', is_active=True),
        empty_label=_("Select a law firm"),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the tenant signup form.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        # Get the request from kwargs
        self.request = kwargs.pop('request', None)
        
        # Initialize the parent form
        super().__init__(*args, **kwargs)
        
        # If we have a tenant in the request, set it as the initial value
        if self.request and hasattr(self.request, 'tenant'):
            self.fields['tenant'].initial = self.request.tenant.pk
            self.fields['tenant'].widget = forms.HiddenInput()
    
    def clean_tenant(self):
        """
        Validate the tenant field.
        
        Returns:
            The cleaned tenant value
            
        Raises:
            ValidationError: If the tenant is invalid
        """
        tenant = self.cleaned_data.get('tenant')
        
        if not tenant:
            raise forms.ValidationError(_("Please select a law firm."))
        
        # Check if the tenant is active
        if tenant.status != 'active' or not tenant.is_active:
            raise forms.ValidationError(_("This law firm is not currently accepting new users."))
        
        # Check if the tenant has reached its user limit
        if not tenant.can_add_users_by_plan():
            raise forms.ValidationError(_("This law firm has reached its user limit."))
        
        return tenant
    
    def save(self, request):
        """
        Save the user with tenant context.
        
        Args:
            request: The HTTP request object
            
        Returns:
            The saved user instance
        """
        # Get the tenant from the form
        tenant = self.cleaned_data['tenant']
        
        # Create the user with the tenant
        user = super().save(request)
        user.tenant = tenant
        user.save()
        
        return user


class TenantSettingsForm(forms.ModelForm):
    """
    Form for editing tenant settings.
    
    This form handles all tenant-specific settings,
    including branding, preferences, and configuration.
    """
    
    class Meta:
        model = TenantSettings
        fields = [
            'logo', 'logo_dark', 'favicon', 'login_background_image',
            'primary_color', 'secondary_color', 'accent_color', 'text_color', 'background_color',
            'company_name', 'company_tagline', 'company_website', 'company_address',
            'company_phone', 'company_email', 'email_from_name', 'email_from_address',
            'email_reply_to', 'date_format', 'time_format', 'timezone',
            'default_currency', 'tax_rate', 'invoice_prefix', 'payment_terms',
            'default_categories', 'retention_days', 'email_notifications',
            'sms_notifications', 'in_app_notifications', 'password_policy',
            'two_factor_required', 'session_timeout', 'enable_client_portal',
            'enable_document_sharing', 'enable_time_tracking', 'email_header',
            'email_footer', 'theme_mode', 'font_family', 'font_heading_family',
            'custom_css', 'login_message', 'dashboard_welcome_message',
            'dashboard_widgets', 'dashboard_layout', 'dashboard_date_range_days',
            'dashboard_auto_refresh', 'dashboard_auto_refresh_interval',
        ]
        widgets = {
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'logo_dark': forms.FileInput(attrs={'class': 'form-control'}),
            'favicon': forms.FileInput(attrs={'class': 'form-control'}),
            'login_background_image': forms.FileInput(attrs={'class': 'form-control'}),
            'primary_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'secondary_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'accent_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'text_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'background_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'company_tagline': forms.TextInput(attrs={'class': 'form-control'}),
            'company_website': forms.URLInput(attrs={'class': 'form-control'}),
            'company_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'company_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'company_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'email_from_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email_from_address': forms.EmailInput(attrs={'class': 'form-control'}),
            'email_reply_to': forms.EmailInput(attrs={'class': 'form-control'}),
            'date_format': forms.Select(attrs={'class': 'form-control'}),
            'time_format': forms.Select(attrs={'class': 'form-control'}),
            'timezone': forms.Select(attrs={'class': 'form-control'}),
            'default_currency': forms.Select(attrs={'class': 'form-control'}),
            'tax_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'invoice_prefix': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_terms': forms.Select(attrs={'class': 'form-control'}),
            'default_categories': forms.TextInput(attrs={'class': 'form-control'}),
            'retention_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'sms_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'in_app_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'password_policy': forms.Select(attrs={'class': 'form-control'}),
            'two_factor_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'session_timeout': forms.Select(attrs={'class': 'form-control'}),
            'enable_client_portal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_document_sharing': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'enable_time_tracking': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_header': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'email_footer': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'theme_mode': forms.Select(attrs={'class': 'form-control'}),
            'font_family': forms.TextInput(attrs={'class': 'form-control'}),
            'font_heading_family': forms.TextInput(attrs={'class': 'form-control'}),
            'custom_css': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'login_message': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'dashboard_welcome_message': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'dashboard_widgets': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'dashboard_layout': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'dashboard_date_range_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'dashboard_auto_refresh': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'dashboard_auto_refresh_interval': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the tenant settings form.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        super().__init__(*args, **kwargs)
        
        # Add help text for color fields
        self.fields['primary_color'].help_text = _("Primary brand color (e.g., #4e73df)")
        self.fields['secondary_color'].help_text = _("Secondary brand color (e.g., #858796)")
        self.fields['accent_color'].help_text = _("Accent color (e.g., #1cc88a)")
        self.fields['text_color'].help_text = _("Text color (e.g., #5a5c69)")
        self.fields['background_color'].help_text = _("Background color (e.g., #f8f9fc)")
        
        # Add help text for file fields
        self.fields['logo'].help_text = _("Company logo (recommended size: 300x300px)")
        self.fields['logo_dark'].help_text = _("Company logo for dark theme (recommended size: 300x300px)")
        self.fields['favicon'].help_text = _("Favicon icon (required size: 32x32px)")
        self.fields['login_background_image'].help_text = _("Background image for login page")
        
        # Add help text for dashboard fields
        self.fields['dashboard_widgets'].help_text = _(
            "JSON format: [{'widget': 'name', 'config': {...}, 'position': {...}}]"
        )
        self.fields['dashboard_layout'].help_text = _(
            "JSON format: {'section': {'widgets': [...], 'layout': '...'}}"
        )
        self.fields['dashboard_auto_refresh_interval'].help_text = _(
            "Auto-refresh interval in seconds (minimum: 30, maximum: 3600)"
        )


class TenantForm(forms.ModelForm):
    """
    Form for creating and editing tenants.
    
    This form handles tenant information and configuration.
    """
    
    class Meta:
        model = Tenant
        fields = [
            'name', 'slug', 'plan', 'max_users', 'max_storage_mb',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'plan': forms.Select(attrs={'class': 'form-control'}),
            'max_users': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_storage_mb': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the tenant form.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        super().__init__(*args, **kwargs)
        
        # Add help text
        self.fields['name'].help_text = _("The name of the law firm")
        self.fields['slug'].help_text = _(
            "URL-friendly name (letters, numbers, and hyphens only)"
        )
        self.fields['plan'].help_text = _("Subscription plan for this law firm")
        
        # Only add help text for fields that exist in the form
        if 'max_users' in self.fields:
            self.fields['max_users'].help_text = _("Maximum number of users allowed")
        if 'max_storage_mb' in self.fields:
            self.fields['max_storage_mb'].help_text = _("Maximum storage space in MB")
    
    def clean_slug(self):
        """
        Validate the slug field.
        
        Returns:
            The cleaned slug value
            
        Raises:
            ValidationError: If the slug is invalid
        """
        slug = self.cleaned_data.get('slug')
        
        if not slug:
            return slug
        
        # Check for invalid characters
        import re
        if not re.match(r'^[a-z0-9-]+$', slug):
            raise forms.ValidationError(
                _("Slug can only contain lowercase letters, numbers, and hyphens.")
            )
        
        # Check if the slug is reserved
        reserved_slugs = ['www', 'mail', 'ftp', 'admin', 'api', 'app']
        if slug in reserved_slugs:
            raise forms.ValidationError(_("'{slug}' is a reserved word.").format(slug=slug))
        
        return slug
    
    def clean_max_users(self):
        """
        Validate the max_users field.
        
        Returns:
            The cleaned max_users value
            
        Raises:
            ValidationError: If the value is invalid
        """
        max_users = self.cleaned_data.get('max_users')
        
        if not max_users or max_users < 1:
            raise forms.ValidationError(_("Maximum users must be at least 1."))
        
        if max_users > 1000:
            raise forms.ValidationError(_("Maximum users cannot exceed 1000."))
        
        return max_users
    
    def clean_max_storage_mb(self):
        """
        Validate the max_storage_mb field.
        
        Returns:
            The cleaned max_storage_mb value
            
        Raises:
            ValidationError: If the value is invalid
        """
        max_storage_mb = self.cleaned_data.get('max_storage_mb')
        
        if not max_storage_mb or max_storage_mb < 100:
            raise forms.ValidationError(_("Maximum storage must be at least 100 MB."))
        
        if max_storage_mb > 102400:  # 100 GB
            raise forms.ValidationError(_("Maximum storage cannot exceed 102400 MB (100 GB)."))
        
        return max_storage_mb


class TenantUserForm(forms.ModelForm):
    """
    Form for managing tenant users.
    
    This form handles user management within a tenant context.
    """
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'role', 'is_active',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the tenant user form.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        # Get the tenant from kwargs
        self.tenant = kwargs.pop('tenant', None)
        
        super().__init__(*args, **kwargs)
        
        # If we have a tenant, filter role choices
        if self.tenant:
            # Customize role choices based on tenant plan
            role_choices = [
                ('lawyer', _('Lawyer')),
                ('paralegal', _('Paralegal')),
                ('assistant', _('Assistant')),
                ('admin', _('Administrator')),
            ]
            
            # Remove admin choice for non-admin users
            if not kwargs.get('is_superuser', False):
                role_choices = [choice for choice in role_choices if choice[0] != 'admin']
            
            self.fields['role'].choices = role_choices
    
    def clean_email(self):
        """
        Validate the email field.
        
        Returns:
            The cleaned email value
            
        Raises:
            ValidationError: If the email is invalid
        """
        email = self.cleaned_data.get('email')
        
        if not email:
            return email
        
        # Check if the email is already in use by another user in the same tenant
        if self.tenant:
            existing_user = User.objects.filter(
                email=email,
                tenant=self.tenant
            ).exclude(pk=self.instance.pk).first()
            
            if existing_user:
                raise forms.ValidationError(
                    _("A user with this email already exists in your law firm.")
                )
        
        return email


class TenantUpdateForm(TenantForm):
    """
    Form for updating existing tenants.
    
    This form extends TenantForm with additional validation for updates.
    """
    
    class Meta(TenantForm.Meta):
        fields = [
            'name', 'plan', 'max_users', 'max_storage_mb',
        ]
        # Note: slug is excluded from update form to prevent URL changes
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the tenant update form.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        super().__init__(*args, **kwargs)
        
        # Note: slug field is excluded from update form to prevent URL changes
        # No need to check for slug field since it's excluded from Meta.fields


class TenantRegistrationForm(TenantForm):
    """
    Form for tenant registration that creates both tenant and admin user.
    
    This form handles tenant creation along with the initial admin user setup.
    """
    
    admin_email = forms.EmailField(
        label=_("Admin Email"),
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        help_text=_("Email address for the admin user of this law firm")
    )
    
    admin_first_name = forms.CharField(
        label=_("Admin First Name"),
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    admin_last_name = forms.CharField(
        label=_("Admin Last Name"),
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    admin_password = forms.CharField(
        label=_("Admin Password"),
        min_length=8,
        required=True,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text=_("Password for the admin user (minimum 8 characters)")
    )
    
    admin_password_confirm = forms.CharField(
        label=_("Confirm Admin Password"),
        min_length=8,
        required=True,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text=_("Confirm the admin password")
    )
    
    agree_terms = forms.BooleanField(
        label=_("I agree to the Terms of Service and Privacy Policy"),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta(TenantForm.Meta):
        fields = [
            'name', 'slug', 'plan',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'slug': forms.TextInput(attrs={'class': 'form-control'}),
            'plan': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the tenant registration form.
        
        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        super(TenantRegistrationForm, self).__init__(*args, **kwargs)
        
        # Add help text for the fields that are included in this form
        self.fields['name'].help_text = _("The name of your law firm")
        self.fields['slug'].help_text = _(
            "URL-friendly name (letters, numbers, and hyphens only)"
        )
        self.fields['plan'].help_text = _("Subscription plan for your law firm")
    
    def clean_admin_password_confirm(self):
        """
        Validate that the admin password confirmation matches.
        
        Returns:
            The confirmed password
            
        Raises:
            ValidationError: If passwords don't match
        """
        password = self.cleaned_data.get('admin_password')
        password_confirm = self.cleaned_data.get('admin_password_confirm')
        
        if password and password_confirm and password != password_confirm:
            raise forms.ValidationError(_("The passwords do not match."))
        
        return password_confirm
    
    def clean_admin_email(self):
        """
        Validate that the admin email is not already in use.
        
        Returns:
            The cleaned email
            
        Raises:
            ValidationError: If email is already in use
        """
        email = self.cleaned_data.get('admin_email')
        
        if email:
            User = get_user_model()
            if User.objects.filter(email=email).exists():
                raise forms.ValidationError(_("A user with this email already exists."))
        
        return email
    
    def save(self, commit=True):
        """
        Save the form and create the tenant and admin user.
        
        Args:
            commit: Whether to commit the save to the database
            
        Returns:
            The created tenant instance
        """
        # First, save the tenant
        tenant = super().save(commit=False)
        
        # Set max_users and max_storage_mb based on plan
        plan = self.cleaned_data.get('plan', 'free')
        plan_limits = {
            'free': {'max_users': 3, 'max_storage_mb': 100},
            'basic': {'max_users': 10, 'max_storage_mb': 1024},
            'pro': {'max_users': 50, 'max_storage_mb': 10240},
            'enterprise': {'max_users': 1000, 'max_storage_mb': 102400},
        }
        
        limits = plan_limits.get(plan, plan_limits['free'])
        tenant.max_users = limits['max_users']
        tenant.max_storage_mb = limits['max_storage_mb']
        
        if commit:
            tenant.save()
            
            # Create the admin user
            User = get_user_model()
            admin_user = User.objects.create_user(
                username=self.cleaned_data['admin_email'],  # username is required
                email=self.cleaned_data['admin_email'],
                first_name=self.cleaned_data['admin_first_name'],
                last_name=self.cleaned_data['admin_last_name'],
                password=self.cleaned_data['admin_password'],
                tenant=tenant,
                role='admin',
                is_staff=True,
                is_active=True
            )
        
        return tenant


class TenantSettingsReadOnlyForm(forms.ModelForm):
    """
    Read-only form for displaying tenant settings.
    
    This form is used to display tenant settings without allowing edits.
    """
    
    class Meta:
        model = TenantSettings
        fields = [
            'logo', 'logo_dark', 'favicon', 'login_background_image',
            'primary_color', 'secondary_color', 'accent_color', 'text_color', 'background_color',
            'company_name', 'company_tagline', 'company_website', 'company_address',
            'company_phone', 'company_email', 'email_from_name', 'email_from_address',
            'email_reply_to', 'date_format', 'time_format', 'timezone',
            'default_currency', 'tax_rate', 'invoice_prefix', 'payment_terms',
            'default_categories', 'retention_days', 'email_notifications',
            'sms_notifications', 'in_app_notifications', 'password_policy',
            'two_factor_required', 'session_timeout', 'enable_client_portal',
            'enable_document_sharing', 'enable_time_tracking', 'email_header',
            'email_footer', 'theme_mode', 'font_family', 'font_heading_family',
            'custom_css', 'login_message', 'dashboard_welcome_message',
            'dashboard_widgets', 'dashboard_layout', 'dashboard_date_range_days',
            'dashboard_auto_refresh', 'dashboard_auto_refresh_interval',
        ]
        widgets = {
            # File fields - display as static text
            'logo': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'logo_dark': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'favicon': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'login_background_image': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            
            # Color fields - display as text with color preview
            'primary_color': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'secondary_color': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'accent_color': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'text_color': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'background_color': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            
            # Text fields
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'company_tagline': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'company_website': forms.URLInput(attrs={'class': 'form-control', 'readonly': True}),
            'company_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'readonly': True}),
            'company_phone': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'company_email': forms.EmailInput(attrs={'class': 'form-control', 'readonly': True}),
            'email_from_name': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'email_from_address': forms.EmailInput(attrs={'class': 'form-control', 'readonly': True}),
            'email_reply_to': forms.EmailInput(attrs={'class': 'form-control', 'readonly': True}),
            
            # Select fields
            'date_format': forms.Select(attrs={'class': 'form-control', 'disabled': True}),
            'time_format': forms.Select(attrs={'class': 'form-control', 'disabled': True}),
            'timezone': forms.Select(attrs={'class': 'form-control', 'disabled': True}),
            'default_currency': forms.Select(attrs={'class': 'form-control', 'disabled': True}),
            'payment_terms': forms.Select(attrs={'class': 'form-control', 'disabled': True}),
            'password_policy': forms.Select(attrs={'class': 'form-control', 'disabled': True}),
            'session_timeout': forms.Select(attrs={'class': 'form-control', 'disabled': True}),
            'theme_mode': forms.Select(attrs={'class': 'form-control', 'disabled': True}),
            
            # Number fields
            'tax_rate': forms.NumberInput(attrs={'class': 'form-control', 'readonly': True}),
            'invoice_prefix': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'default_categories': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'retention_days': forms.NumberInput(attrs={'class': 'form-control', 'readonly': True}),
            'dashboard_date_range_days': forms.NumberInput(attrs={'class': 'form-control', 'readonly': True}),
            'dashboard_auto_refresh_interval': forms.NumberInput(attrs={'class': 'form-control', 'readonly': True}),
            
            # Checkbox fields
            'email_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input', 'disabled': True}),
            'sms_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input', 'disabled': True}),
            'in_app_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input', 'disabled': True}),
            'two_factor_required': forms.CheckboxInput(attrs={'class': 'form-check-input', 'disabled': True}),
            'enable_client_portal': forms.CheckboxInput(attrs={'class': 'form-check-input', 'disabled': True}),
            'enable_document_sharing': forms.CheckboxInput(attrs={'class': 'form-check-input', 'disabled': True}),
            'enable_time_tracking': forms.CheckboxInput(attrs={'class': 'form-check-input', 'disabled': True}),
            'dashboard_auto_refresh': forms.CheckboxInput(attrs={'class': 'form-check-input', 'disabled': True}),
            
            # Textarea fields
            'email_header': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'readonly': True}),
            'email_footer': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'readonly': True}),
            'font_family': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'font_heading_family': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'custom_css': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'readonly': True}),
            'login_message': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'readonly': True}),
            'dashboard_welcome_message': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'readonly': True}),
            'dashboard_widgets': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'readonly': True}),
            'dashboard_layout': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'readonly': True}),
        }
