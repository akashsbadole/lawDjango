from typing import TYPE_CHECKING
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator
from django.contrib.staticfiles.storage import staticfiles_storage
from decimal import Decimal
from .managers import TenantManager

if TYPE_CHECKING:
    from django.db.models.manager import Manager


class Tenant(models.Model):
    """
    Model representing a tenant (law firm) in multi-tenant system.
    """
    PLAN_CHOICES = [
        ('free', 'Free'),
        ('basic', 'Basic'),
        ('pro', 'Professional'),
        ('enterprise', 'Enterprise'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('deleted', 'Deleted'),
        ('trial_expired', 'Trial Expired'),
    ]
    
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    max_users = models.IntegerField(default=3)
    max_storage_mb = models.IntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True)
    
    objects = models.Manager()
    tenant_manager = TenantManager()
    
    class Meta:
        db_table = 'tenants'
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Auto-generate slug if not provided
        if not self.slug:
            self.slug = slugify(self.name)
            # Ensure uniqueness
            counter = 1
            original_slug = self.slug
            while Tenant.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)
    
    def _record_status_change(self, new_status, reason="", changed_by=None):
        """Record a status change in history."""
        # Import here to avoid circular import
        from .models import TenantStatusHistory
        
        TenantStatusHistory.objects.create(
            tenant=self,
            old_status=self.status,
            new_status=new_status,
            reason=reason,
            changed_by=changed_by
        )
    
    def soft_delete(self, reason="", changed_by=None):
        """Mark tenant as deleted without actually removing it from database."""
        self._record_status_change('deleted', reason or "Tenant deleted", changed_by)
        self.deleted_at = timezone.now()
        self.status = 'deleted'
        self.is_active = False
        self.save()
    
    def restore(self, changed_by=None):
        """Restore a soft-deleted tenant."""
        self._record_status_change('active', "Tenant restored", changed_by)
        self.deleted_at = None
        self.status = 'active'
        self.is_active = True
        self.save()
    
    def suspend(self, reason="", changed_by=None):
        """Suspend a tenant temporarily."""
        self._record_status_change('suspended', reason or "Tenant suspended", changed_by)
        self.suspended_at = timezone.now()
        self.status = 'suspended'
        self.is_active = False
        self.suspension_reason = reason
        self.save()
    
    def unsuspend(self, changed_by=None):
        """Unsuspend a tenant."""
        self._record_status_change('active', "Tenant unsuspended", changed_by)
        self.suspended_at = None
        self.status = 'active'
        self.is_active = True
        self.suspension_reason = ""
        self.save()
    
    def expire_trial(self, changed_by=None):
        """Mark a tenant's trial as expired."""
        self._record_status_change('trial_expired', "Trial period expired", changed_by)
        self.status = 'trial_expired'
        self.is_active = False
        self.save()
    
    def permanent_delete(self):
        """Permanently delete a tenant and all related data."""
        # This should be used with caution as it removes all data
        # In a real implementation, you might want to cascade delete related data
        self.delete()
    
    @property
    def is_deleted(self):
        """Check if tenant is soft-deleted."""
        return self.deleted_at is not None
    
    @property
    def is_suspended(self):
        """Check if tenant is suspended."""
        return self.status == 'suspended'
    
    @property
    def is_trial_expired(self):
        """Check if tenant's trial has expired."""
        return self.status == 'trial_expired'
    
    def can_transition_to(self, new_status):
        """Check if tenant can transition to new status."""
        valid_transitions = {
            'active': ['suspended', 'deleted', 'trial_expired'],
            'suspended': ['active', 'deleted'],
            'trial_expired': ['active', 'deleted'],
            'deleted': ['active']  # Only restore is allowed
        }
        return new_status in valid_transitions.get(self.status, [])
    
    def get_status_display_with_icon(self):
        """Get status display with appropriate icon."""
        status_icons = {
            'active': '<span class="badge badge-success">✓ Active</span>',
            'suspended': '<span class="badge badge-warning">⚠ Suspended</span>',
            'deleted': '<span class="badge badge-danger">✗ Deleted</span>',
            'trial_expired': '<span class="badge badge-info">⏱ Trial Expired</span>'
        }
        return status_icons.get(self.status, self.status)
    
    def get_current_user_count(self):
        """Get current number of users for this tenant."""
        from accounts.models import CustomUser
        return CustomUser.objects.filter(tenant=self).count()
    
    def can_add_users_by_plan(self):
        """Check if tenant can add more users based on their plan."""
        return self.get_current_user_count() < self.max_users
    
    def get_storage_used_by_plan(self):
        """Get current storage usage in MB for this tenant."""
        # This is a placeholder - actual implementation would depend on how files are stored
        # and tracked for each tenant
        return 0  # Placeholder value
    
    def get_storage_used(self):
        """Get current storage usage in bytes for this tenant."""
        try:
            # Sum the file sizes of all non-deleted documents for this tenant
            from documents.models import Document
            
            total_storage = Document.objects.filter(
                tenant=self,
                deleted_at__isnull=True
            ).aggregate(
                total_size=models.Sum('file_size')
            )['total_size'] or 0
            
            return total_storage
        except Exception as e:
            # Log the error for debugging but return 0 to avoid breaking the application
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error calculating storage usage for tenant {self.name}: {str(e)}")
            return 0
    
    def get_settings(self):
        """Get or create tenant settings."""
        settings, created = TenantSettings.objects.get_or_create(tenant=self)
        return settings
    
    def get_current_subscription(self):
        """Get current active subscription for this tenant."""
        from subscriptions.models import TenantSubscription
        try:
            return TenantSubscription.objects.filter(tenant=self, is_active=True).first()
        except Exception:
            return None
    
    def has_active_subscription(self):
        """Check if tenant has an active subscription."""
        subscription = self.get_current_subscription()
        return subscription is not None and subscription.is_active
    
    def can_add_user(self):
        """Check if tenant can add more users based on their subscription."""
        subscription = self.get_current_subscription()
        if subscription and subscription.plan:
            current_user_count = self.get_current_user_count()
            return current_user_count < subscription.plan.max_users
        
        # Fallback to legacy plan checking
        return self.can_add_users_by_plan()
    
    def get_storage_limit(self):
        """Get storage limit based on subscription."""
        subscription = self.get_current_subscription()
        if subscription and subscription.plan:
            return subscription.plan.max_storage_mb
        
        # Fallback to legacy plan limit
        return self.max_storage_mb
    


class TenantSettings(models.Model):
    """
    Model representing settings and preferences for a tenant.
    One-to-one relationship with Tenant model.
    """
    # Date and time preferences
    DATE_FORMAT_CHOICES = [
        ('Y-m-d', 'YYYY-MM-DD'),
        ('d/m/Y', 'DD/MM/YYYY'),
        ('m/d/Y', 'MM/DD/YYYY'),
        ('d.m.Y', 'DD.MM.YYYY'),
    ]
    
    TIME_FORMAT_CHOICES = [
        ('H:i', '24-hour (HH:MM)'),
        ('g:i A', '12-hour (HH:MM AM/PM)'),
    ]
    
    TIMEZONE_CHOICES = [
        ('UTC', 'UTC'),
        ('US/Eastern', 'US/Eastern'),
        ('US/Central', 'US/Central'),
        ('US/Mountain', 'US/Mountain'),
        ('US/Pacific', 'US/Pacific'),
        ('Europe/London', 'Europe/London'),
        ('Europe/Paris', 'Europe/Paris'),
        ('Asia/Kolkata', 'Asia/Kolkata'),
        ('Asia/Tokyo', 'Asia/Tokyo'),
        ('Australia/Sydney', 'Australia/Sydney'),
    ]
    
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar ($)'),
        ('EUR', 'Euro (€)'),
        ('GBP', 'British Pound (£)'),
        ('CAD', 'Canadian Dollar ($)'),
        ('AUD', 'Australian Dollar ($)'),
        ('INR', 'Indian Rupee (₹)'),
        ('JPY', 'Japanese Yen (¥)'),
        ('CNY', 'Chinese Yuan (¥)'),
    ]
    
    PAYMENT_TERMS_CHOICES = [
        (0, 'Due on Receipt'),
        (7, 'Net 7'),
        (14, 'Net 14'),
        (30, 'Net 30'),
        (45, 'Net 45'),
        (60, 'Net 60'),
        (90, 'Net 90'),
    ]
    
    DOCUMENT_CATEGORY_CHOICES = [
        ('contract', 'Contract'),
        ('court_filing', 'Court Filing'),
        ('correspondence', 'Correspondence'),
        ('discovery', 'Discovery'),
        ('evidence', 'Evidence'),
        ('motion', 'Motion'),
        ('pleading', 'Pleading'),
        ('research', 'Research'),
        ('other', 'Other'),
    ]
    
    PASSWORD_POLICY_CHOICES = [
        ('weak', 'Weak (6 chars)'),
        ('medium', 'Medium (8 chars, letters & numbers)'),
        ('strong', 'Strong (8 chars, letters, numbers & symbols)'),
        ('very_strong', 'Very Strong (12 chars, mixed case, numbers & symbols)'),
    ]
    
    SESSION_TIMEOUT_CHOICES = [
        (15, '15 minutes'),
        (30, '30 minutes'),
        (60, '1 hour'),
        (120, '2 hours'),
        (240, '4 hours'),
        (480, '8 hours'),
    ]
    
    # One-to-one relationship with Tenant
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name='settings'
    )
    
    # Branding settings
    logo = models.ImageField(
        upload_to='tenant_logos/',
        null=True,
        blank=True,
        help_text='Upload your company logo'
    )
    logo_dark = models.ImageField(
        upload_to='tenant_logos/',
        null=True,
        blank=True,
        help_text='Upload your company logo for dark theme'
    )
    favicon = models.ImageField(
        upload_to='tenant_favicons/',
        null=True,
        blank=True,
        help_text='Upload your company favicon (32x32px)'
    )
    primary_color = models.CharField(
        max_length=7,
        default='#4e73df',
        validators=[
            RegexValidator(
                regex='^#[0-9A-Fa-f]{6}$',
                message='Enter a valid hex color code (e.g., #4e73df)'
            )
        ],
        help_text='Primary brand color in hex format'
    )
    secondary_color = models.CharField(
        max_length=7,
        default='#858796',
        validators=[
            RegexValidator(
                regex='^#[0-9A-Fa-f]{6}$',
                message='Enter a valid hex color code (e.g., #858796)'
            )
        ],
        help_text='Secondary brand color in hex format'
    )
    accent_color = models.CharField(
        max_length=7,
        default='#1cc88a',
        validators=[
            RegexValidator(
                regex='^#[0-9A-Fa-f]{6}$',
                message='Enter a valid hex color code (e.g., #1cc88a)'
            )
        ],
        help_text='Accent brand color in hex format'
    )
    text_color = models.CharField(
        max_length=7,
        default='#5a5c69',
        validators=[
            RegexValidator(
                regex='^#[0-9A-Fa-f]{6}$',
                message='Enter a valid hex color code (e.g., #5a5c69)'
            )
        ],
        help_text='Text color in hex format'
    )
    background_color = models.CharField(
        max_length=7,
        default='#f8f9fc',
        validators=[
            RegexValidator(
                regex='^#[0-9A-Fa-f]{6}$',
                message='Enter a valid hex color code (e.g., #f8f9fc)'
            )
        ],
        help_text='Background color in hex format'
    )
    company_name = models.CharField(
        max_length=255,
        blank=True,
        help_text='Display name for your company'
    )
    company_tagline = models.CharField(
        max_length=255,
        blank=True,
        help_text='Company tagline or slogan'
    )
    company_website = models.URLField(
        blank=True,
        help_text='Company website URL'
    )
    company_address = models.TextField(
        blank=True,
        help_text='Company address for invoices and documents'
    )
    company_phone = models.CharField(
        max_length=20,
        blank=True,
        help_text='Company phone number'
    )
    company_email = models.EmailField(
        blank=True,
        help_text='Company email address'
    )
    font_family = models.CharField(
        max_length=100,
        default='Inter, system-ui, sans-serif',
        help_text='Font family for application'
    )
    font_heading_family = models.CharField(
        max_length=100,
        default='Inter, system-ui, sans-serif',
        help_text='Font family for headings'
    )
    custom_css = models.TextField(
        blank=True,
        help_text='Custom CSS to inject into application'
    )
    login_background_image = models.ImageField(
        upload_to='tenant_login_bg/',
        null=True,
        blank=True,
        help_text='Background image for login page'
    )
    login_message = models.TextField(
        blank=True,
        help_text='Custom message to display on login page'
    )
    dashboard_welcome_message = models.TextField(
        blank=True,
        help_text='Custom welcome message for dashboard'
    )
    email_from_name = models.CharField(
        max_length=255,
        blank=True,
        help_text='From name for email communications'
    )
    email_from_address = models.EmailField(
        blank=True,
        help_text='From address for email communications'
    )
    email_reply_to = models.EmailField(
        blank=True,
        help_text='Reply-to address for email communications'
    )
    theme_mode = models.CharField(
        max_length=20,
        choices=[
            ('light', 'Light'),
            ('dark', 'Dark'),
            ('auto', 'Auto (system preference)'),
        ],
        default='light',
        help_text='Default theme mode'
    )
    brand_guidelines = models.JSONField(
        default=dict,
        blank=True,
        help_text='Brand guidelines and configuration (JSON format)'
    )
    
    # Date and time preferences
    date_format = models.CharField(
        max_length=10,
        choices=DATE_FORMAT_CHOICES,
        default='Y-m-d',
        help_text='Preferred date format'
    )
    time_format = models.CharField(
        max_length=10,
        choices=TIME_FORMAT_CHOICES,
        default='H:i',
        help_text='Preferred time format'
    )
    timezone = models.CharField(
        max_length=50,
        choices=TIMEZONE_CHOICES,
        default='UTC',
        help_text='Timezone for date/time display'
    )
    
    # Billing settings
    default_currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='USD',
        help_text='Default currency for billing'
    )
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Default tax rate (as percentage, e.g., 8.25 for 8.25%)'
    )
    invoice_prefix = models.CharField(
        max_length=10,
        default='INV',
        help_text='Prefix for invoice numbers'
    )
    payment_terms = models.IntegerField(
        choices=PAYMENT_TERMS_CHOICES,
        default=30,
        help_text='Default payment terms in days'
    )
    
    # Document settings
    default_categories = models.CharField(
        max_length=255,
        default='contract,court_filing,correspondence,discovery,evidence,motion,pleading,research,other',
        help_text='Comma-separated list of default document categories'
    )
    retention_days = models.IntegerField(
        default=2555,  # 7 years
        help_text='Number of days to retain documents (default: 2555 days = 7 years)'
    )
    
    # Notification preferences
    email_notifications = models.BooleanField(
        default=True,
        help_text='Enable email notifications'
    )
    sms_notifications = models.BooleanField(
        default=False,
        help_text='Enable SMS notifications'
    )
    in_app_notifications = models.BooleanField(
        default=True,
        help_text='Enable in-app notifications'
    )
    
    # Security settings
    password_policy = models.CharField(
        max_length=20,
        choices=PASSWORD_POLICY_CHOICES,
        default='medium',
        help_text='Password complexity requirements'
    )
    two_factor_required = models.BooleanField(
        default=False,
        help_text='Require two-factor authentication for all users'
    )
    session_timeout = models.IntegerField(
        choices=SESSION_TIMEOUT_CHOICES,
        default=60,
        help_text='User session timeout in minutes'
    )
    
    # Feature toggles
    enable_client_portal = models.BooleanField(
        default=False,
        help_text='Enable client portal feature'
    )
    enable_document_sharing = models.BooleanField(
        default=True,
        help_text='Enable document sharing with clients'
    )
    enable_time_tracking = models.BooleanField(
        default=True,
        help_text='Enable time tracking feature'
    )
    
    # Email template customization
    email_header = models.TextField(
        blank=True,
        help_text='Custom header for email templates'
    )
    email_footer = models.TextField(
        blank=True,
        help_text='Custom footer for email templates'
    )
    
    # Custom fields configuration (JSON field for flexibility)
    custom_fields = models.JSONField(
        default=dict,
        blank=True,
        help_text='Configuration for custom fields (JSON format)'
    )
    
    # Dashboard configuration
    dashboard_widgets = models.JSONField(
        default=list,
        blank=True,
        help_text='List of default dashboard widgets for this tenant (JSON format)'
    )
    dashboard_layout = models.JSONField(
        default=dict,
        blank=True,
        help_text='Default dashboard layout configuration (JSON format)'
    )
    dashboard_date_range_days = models.IntegerField(
        default=30,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(365)
        ],
        help_text='Default date range for dashboard widgets (in days)'
    )
    dashboard_auto_refresh = models.BooleanField(
        default=True,
        help_text='Enable auto-refresh for dashboard widgets'
    )
    dashboard_auto_refresh_interval = models.IntegerField(
        default=300,  # 5 minutes
        validators=[
            MinValueValidator(30),
            MaxValueValidator(3600)
        ],
        help_text='Auto-refresh interval in seconds'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tenant_settings'
        verbose_name = 'Tenant Settings'
        verbose_name_plural = 'Tenant Settings'
    
    def __str__(self):
        return f"{self.tenant.name} Settings"
    
    def save(self, *args, **kwargs):
        # Clear branding cache when settings are updated
        if self.pk:  # Only clear if this is an update, not a create
            from .branding_utils import clear_branding_cache
            clear_branding_cache(self.tenant)
        super().save(*args, **kwargs)
    
    def get_logo_url(self, theme='light'):
        """Get URL for tenant's logo, fallback to default if not set."""
        if theme == 'dark' and self.logo_dark:
            return self.logo_dark.url
        elif self.logo:
            return self.logo.url
        return staticfiles_storage.url('images/logo.png')
    
    def get_favicon_url(self):
        """Get URL for tenant's favicon, fallback to default if not set."""
        if self.favicon:
            return self.favicon.url
        return staticfiles_storage.url('images/favicon.ico')
    
    def get_login_background_url(self):
        """Get URL for tenant's login background image."""
        if self.login_background_image:
            return self.login_background_image.url
        return None
    
    def get_company_name(self):
        """Get company name, fallback to tenant name if not set."""
        return self.company_name or self.tenant.name
    
    def get_email_from_name(self):
        """Get email from name, fallback to company name if not set."""
        return self.email_from_name or self.get_company_name()
    
    def get_email_from_address(self):
        """Get email from address, fallback to default if not set."""
        return self.email_from_address or f"noreply@{self.tenant.slug}.lawfirm.com"
    
    def get_brand_colors(self):
        """Get all brand colors as a dictionary."""
        return {
            'primary': self.primary_color,
            'secondary': self.secondary_color,
            'accent': self.accent_color,
            'text': self.text_color,
            'background': self.background_color,
        }
    
    def get_color_variations(self, base_color):
        """Generate color variations (lighter, darker) from a base color."""
        try:
            from colorsys import rgb_to_hsv, hsv_to_rgb
            import re
            
            # Remove # if present
            hex_color = base_color.lstrip('#')
            
            # Convert hex to RGB
            r = int(hex_color[0:2], 16) / 255.0
            g = int(hex_color[2:4], 16) / 255.0
            b = int(hex_color[4:6], 16) / 255.0
            
            # Convert RGB to HSV
            h, s, v = rgb_to_hsv(r, g, b)
            
            # Create variations
            variations = {}
            
            # Lighter (increase value)
            lighter_v = min(1.0, v * 1.2)
            lighter_r, lighter_g, lighter_b = hsv_to_rgb(h, s, lighter_v)
            variations['light'] = '#{:02x}{:02x}{:02x}'.format(
                int(lighter_r * 255), int(lighter_g * 255), int(lighter_b * 255)
            )
            
            # Darker (decrease value)
            darker_v = max(0.0, v * 0.8)
            darker_r, darker_g, darker_b = hsv_to_rgb(h, s, darker_v)
            variations['dark'] = '#{:02x}{:02x}{:02x}'.format(
                int(darker_r * 255), int(darker_g * 255), int(darker_b * 255)
            )
            
            # Less saturated (for backgrounds)
            less_saturated_s = max(0.0, s * 0.3)
            less_saturated_r, less_saturated_g, less_saturated_b = hsv_to_rgb(h, less_saturated_s, v)
            variations['background'] = '#{:02x}{:02x}{:02x}'.format(
                int(less_saturated_r * 255), int(less_saturated_g * 255), int(less_saturated_b * 255)
            )
            
            return variations
            
        except Exception:
            # Fallback to simple variations if color manipulation fails
            return {
                'light': base_color,
                'dark': base_color,
                'background': base_color,
            }
    
    def get_theme_css_variables(self):
        """Generate CSS custom properties for theme."""
        colors = self.get_brand_colors()
        css_vars = {}
        
        for name, color in colors.items():
            css_vars[f'--brand-{name}'] = color
            variations = self.get_color_variations(color)
            for var_type, var_color in variations.items():
                css_vars[f'--brand-{name}-{var_type}'] = var_color
        
        # Add other theme variables
        css_vars['--brand-font-family'] = self.font_family
        css_vars['--brand-font-heading-family'] = self.font_heading_family
        
        return css_vars
    
    def get_company_info(self):
        """Get company information as a dictionary."""
        return {
            'name': self.get_company_name(),
            'tagline': self.company_tagline,
            'website': self.company_website,
            'address': self.company_address,
            'phone': self.company_phone,
            'email': self.company_email,
        }
    
    def get_email_settings(self):
        """Get email settings as a dictionary."""
        return {
            'from_name': self.get_email_from_name(),
            'from_address': self.get_email_from_address(),
            'reply_to': self.email_reply_to or self.get_email_from_address(),
            'header': self.email_header,
            'footer': self.email_footer,
        }
    
    def get_default_categories_list(self):
        """Get default document categories as a list."""
        return [cat.strip() for cat in self.default_categories.split(',')]
    
    def set_default_categories_list(self, categories_list):
        """Set default document categories from a list."""
        self.default_categories = ','.join(categories_list)
    
    def get_password_requirements(self):
        """Get password requirements based on policy."""
        requirements = {
            'weak': {'min_length': 6, 'require_letters': False, 'require_numbers': False, 'require_symbols': False},
            'medium': {'min_length': 8, 'require_letters': True, 'require_numbers': True, 'require_symbols': False},
            'strong': {'min_length': 8, 'require_letters': True, 'require_numbers': True, 'require_symbols': True},
            'very_strong': {'min_length': 12, 'require_letters': True, 'require_numbers': True, 'require_symbols': True, 'require_mixed_case': True},
        }
        return requirements.get(self.password_policy, requirements['medium'])
    
    def is_feature_enabled(self, feature_name):
        """Check if a specific feature is enabled."""
        feature_map = {
            'client_portal': self.enable_client_portal,
            'document_sharing': self.enable_document_sharing,
            'time_tracking': self.enable_time_tracking,
        }
        return feature_map.get(feature_name, False)


class TenantStatusHistory(models.Model):
    """
    Model to track the status changes of a tenant over time.
    """
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name='status_history'
    )
    old_status = models.CharField(max_length=20, choices=Tenant.STATUS_CHOICES, blank=True)
    new_status = models.CharField(max_length=20, choices=Tenant.STATUS_CHOICES)
    reason = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tenant_status_changes'
    )
    changed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'tenant_status_history'
        verbose_name = 'Tenant Status History'
        verbose_name_plural = 'Tenant Status Histories'
        ordering = ['-changed_at']
    
    def __str__(self):
        return f"{self.tenant.name}: {self.old_status or 'None'} → {self.new_status} at {self.changed_at}"