from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.validators import RegexValidator
import json

User = get_user_model()


class SystemSettings(models.Model):
    """
    Model for platform-wide configuration settings.
    """
    # Platform information
    platform_name = models.CharField(
        max_length=255,
        default="Law Firm Management Platform",
        help_text="Name of the platform displayed to users"
    )
    platform_version = models.CharField(
        max_length=50,
        default="1.0.0",
        help_text="Current platform version"
    )
    
    # Contact information
    support_email = models.EmailField(
        default="support@example.com",
        help_text="Platform support email address"
    )
    support_phone = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Platform support phone number"
    )
    
    # Registration settings
    allow_public_registration = models.BooleanField(
        default=True,
        help_text="Allow public tenant registration"
    )
    require_admin_approval = models.BooleanField(
        default=False,
        help_text="Require admin approval for new tenant registrations"
    )
    default_trial_days = models.IntegerField(
        default=14,
        help_text="Default trial period for new tenants (in days)"
    )
    
    # System limits
    max_tenants = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of tenants allowed (null for unlimited)"
    )
    max_users_per_tenant = models.IntegerField(
        default=50,
        help_text="Maximum users allowed per tenant"
    )
    
    # Security settings
    enforce_2fa_for_admins = models.BooleanField(
        default=False,
        help_text="Enforce two-factor authentication for all admin users"
    )
    session_timeout_minutes = models.IntegerField(
        default=60,
        help_text="Default session timeout in minutes"
    )
    
    # Backup settings
    auto_backup_enabled = models.BooleanField(
        default=True,
        help_text="Enable automatic backups"
    )
    backup_retention_days = models.IntegerField(
        default=30,
        help_text="Number of days to retain backups"
    )
    
    # Notification settings
    system_alerts_enabled = models.BooleanField(
        default=True,
        help_text="Enable system-wide alerts and notifications"
    )
    email_notifications_enabled = models.BooleanField(
        default=True,
        help_text="Enable email notifications for system events"
    )
    
    # Maintenance settings
    maintenance_mode = models.BooleanField(
        default=False,
        help_text="Put the platform in maintenance mode"
    )
    maintenance_message = models.TextField(
        blank=True,
        null=True,
        help_text="Message to display during maintenance"
    )
    
    # Custom CSS/JS
    custom_css = models.TextField(
        blank=True,
        null=True,
        help_text="Custom CSS for platform-wide styling"
    )
    custom_js = models.TextField(
        blank=True,
        null=True,
        help_text="Custom JavaScript for platform-wide functionality"
    )
    
    # API settings
    api_rate_limit_enabled = models.BooleanField(
        default=True,
        help_text="Enable API rate limiting"
    )
    api_rate_limit_requests = models.IntegerField(
        default=1000,
        help_text="API requests per hour per user"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'platform_system_settings'
        verbose_name = 'System Settings'
        verbose_name_plural = 'System Settings'
    
    def __str__(self):
        return f"System Settings - {self.platform_name}"
    
    @classmethod
    def get_settings(cls):
        """Get or create system settings."""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings


class PlatformMetrics(models.Model):
    """
    Model for tracking system-wide statistics and metrics.
    """
    METRIC_TYPES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPES)
    date = models.DateField()
    
    # Tenant metrics
    total_tenants = models.IntegerField(default=0)
    active_tenants = models.IntegerField(default=0)
    new_tenants = models.IntegerField(default=0)
    churned_tenants = models.IntegerField(default=0)
    
    # User metrics
    total_users = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)
    new_users = models.IntegerField(default=0)
    
    # Subscription metrics
    total_subscriptions = models.IntegerField(default=0)
    active_subscriptions = models.IntegerField(default=0)
    trial_subscriptions = models.IntegerField(default=0)
    expired_subscriptions = models.IntegerField(default=0)
    
    # Revenue metrics
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    monthly_recurring_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    average_revenue_per_tenant = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Storage metrics
    total_storage_used_mb = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    average_storage_per_tenant_mb = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # System performance metrics
    average_response_time_ms = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    uptime_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    error_rate_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    # Feature usage metrics
    documents_created = models.IntegerField(default=0)
    cases_created = models.IntegerField(default=0)
    clients_created = models.IntegerField(default=0)
    invoices_generated = models.IntegerField(default=0)
    
    # Additional metrics stored as JSON
    additional_metrics = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'platform_metrics'
        verbose_name = 'Platform Metrics'
        verbose_name_plural = 'Platform Metrics'
        unique_together = ['metric_type', 'date']
        ordering = ['-date', '-metric_type']
    
    def __str__(self):
        return f"{self.get_metric_type_display()} Metrics - {self.date}"


class AdminNote(models.Model):
    """
    Model for tracking admin actions and notes on tenants.
    """
    NOTE_TYPES = [
        ('general', 'General Note'),
        ('warning', 'Warning'),
        ('action_taken', 'Action Taken'),
        ('follow_up', 'Follow Up Required'),
        ('complaint', 'Complaint'),
        ('compliment', 'Compliment'),
        ('system_alert', 'System Alert'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='admin_notes',
        null=True,
        blank=True,
        help_text="Tenant this note relates to (leave blank for platform-wide notes)"
    )
    admin_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='admin_notes',
        help_text="Admin user who created this note"
    )
    note_type = models.CharField(max_length=20, choices=NOTE_TYPES, default='general')
    title = models.CharField(max_length=255)
    content = models.TextField()
    
    # Flags and status
    is_private = models.BooleanField(
        default=False,
        help_text="Only visible to super admins"
    )
    is_resolved = models.BooleanField(
        default=False,
        help_text="Mark if the issue has been resolved"
    )
    requires_follow_up = models.BooleanField(
        default=False,
        help_text="This note requires follow-up action"
    )
    follow_up_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when follow-up is required"
    )
    
    # Related entities
    related_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='related_admin_notes',
        help_text="User this note relates to (if applicable)"
    )
    
    # Metadata
    metadata = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'platform_admin_notes'
        verbose_name = 'Admin Note'
        verbose_name_plural = 'Admin Notes'
        ordering = ['-created_at']
    
    def __str__(self):
        target = self.tenant.name if self.tenant else "Platform"
        return f"{self.get_note_type_display()}: {self.title} - {target}"
    
    @property
    def is_overdue(self):
        """Check if follow-up is overdue."""
        if not self.requires_follow_up or not self.follow_up_date:
            return False
        return timezone.now() > self.follow_up_date and not self.is_resolved


class SystemAnnouncement(models.Model):
    """
    Model for system-wide announcements and broadcasts.
    """
    ANNOUNCEMENT_TYPES = [
        ('info', 'Information'),
        ('warning', 'Warning'),
        ('maintenance', 'Maintenance'),
        ('feature', 'New Feature'),
        ('security', 'Security'),
        ('urgent', 'Urgent'),
    ]
    
    title = models.CharField(max_length=255)
    content = models.TextField()
    announcement_type = models.CharField(max_length=20, choices=ANNOUNCEMENT_TYPES, default='info')
    
    # Targeting
    target_all_tenants = models.BooleanField(default=True)
    target_tenants = models.ManyToManyField(
        'tenants.Tenant',
        blank=True,
        related_name='announcements',
        help_text="Specific tenants to target (if not targeting all)"
    )
    target_roles = models.JSONField(
        default=list,
        blank=True,
        help_text="List of user roles to target (empty = all roles)"
    )
    
    # Scheduling
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When to stop showing this announcement (leave blank for indefinite)"
    )
    
    # Display options
    show_on_login = models.BooleanField(default=True)
    show_on_dashboard = models.BooleanField(default=True)
    show_as_banner = models.BooleanField(default=False)
    is_dismissible = models.BooleanField(default=True)
    
    # Priority and ordering
    priority = models.IntegerField(
        default=0,
        help_text="Higher numbers show first (0-100)"
    )
    
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_announcements'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'platform_announcements'
        verbose_name = 'System Announcement'
        verbose_name_plural = 'System Announcements'
        ordering = ['-priority', '-created_at']
    
    def __str__(self):
        return f"{self.get_announcement_type_display()}: {self.title}"
    
    @property
    def is_current(self):
        """Check if announcement is currently active."""
        now = timezone.now()
        return (
            self.is_active and
            now >= self.start_date and
            (self.end_date is None or now <= self.end_date)
        )


class SystemHealthCheck(models.Model):
    """
    Model for tracking system health check results.
    """
    CHECK_TYPES = [
        ('database', 'Database'),
        ('storage', 'Storage'),
        ('email', 'Email Service'),
        ('backup', 'Backup System'),
        ('ssl', 'SSL Certificate'),
        ('performance', 'Performance'),
        ('security', 'Security'),
        ('external_api', 'External API'),
    ]
    
    STATUS_CHOICES = [
        ('healthy', 'Healthy'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
        ('unknown', 'Unknown'),
    ]
    
    check_type = models.CharField(max_length=20, choices=CHECK_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unknown')
    message = models.TextField(blank=True, null=True)
    details = models.JSONField(default=dict, blank=True)
    
    # Timing information
    check_duration_ms = models.IntegerField(default=0)
    next_check_due = models.DateTimeField()
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'platform_health_checks'
        verbose_name = 'System Health Check'
        verbose_name_plural = 'System Health Checks'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_check_type_display()}: {self.get_status_display()}"


class AdminActivityLog(models.Model):
    """
    Model for logging all super admin activities.
    """
    ACTION_TYPES = [
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('view', 'View'),
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('enable', 'Enable'),
        ('disable', 'Disable'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('bulk_operation', 'Bulk Operation'),
        ('system_change', 'System Change'),
    ]
    
    admin_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='platform_admin_activity_logs'
    )
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    action_description = models.CharField(max_length=255)
    
    # Target information
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admin_activity_logs'
    )
    target_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='targeted_activity_logs'
    )
    
    # Request information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    
    # Additional details
    details = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'platform_admin_activity_logs'
        verbose_name = 'Admin Activity Log'
        verbose_name_plural = 'Admin Activity Logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.admin_user.email} - {self.get_action_type_display()}: {self.action_description}"
