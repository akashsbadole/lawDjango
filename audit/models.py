from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
import json

User = get_user_model()


class AuditLog(models.Model):
    """
    Comprehensive audit log for all model changes and user actions.
    """
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('view', 'View'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('export', 'Export'),
        ('import', 'Import'),
        ('print', 'Print'),
        ('email', 'Email'),
        ('download', 'Download'),
        ('upload', 'Upload'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('archive', 'Archive'),
        ('restore', 'Restore'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='audit_logs'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    object_id = models.CharField(max_length=50, null=True, blank=True)
    object_repr = models.CharField(max_length=255, null=True, blank=True)
    
    # Content type fields for generic foreign key
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Change tracking
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    changed_fields = models.JSONField(null=True, blank=True, default=list)
    
    # Request information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    
    # Additional context
    request_path = models.CharField(max_length=255, null=True, blank=True)
    request_method = models.CharField(max_length=10, null=True, blank=True)
    additional_data = models.JSONField(null=True, blank=True)
    
    # Timestamp
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'audit_logs'
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['tenant', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['action']),
            models.Index(fields=['ip_address']),
        ]
    
    def __str__(self):
        user_str = f"{self.user}" if self.user else "Anonymous"
        return f"{user_str} {self.action} {self.model_name} at {self.timestamp}"
    
    @property
    def changes_summary(self):
        """Return a summary of changes made."""
        if self.action == 'create':
            return f"Created new {self.model_name}: {self.object_repr}"
        elif self.action == 'delete':
            return f"Deleted {self.model_name}: {self.object_repr}"
        elif self.action == 'update' and self.changed_fields:
            return f"Updated {self.model_name}: {', '.join(self.changed_fields)}"
        return f"{self.action.title()} {self.model_name}"


class LoginLog(models.Model):
    """
    Track user login and logout events.
    """
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='login_logs'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='login_logs'
    )
    login_time = models.DateTimeField(default=timezone.now)
    logout_time = models.DateTimeField(null=True, blank=True)
    
    # Request information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    
    # Login status
    login_successful = models.BooleanField(default=True)
    failure_reason = models.CharField(max_length=255, null=True, blank=True)
    
    # Additional context
    device_info = models.JSONField(null=True, blank=True)
    location_info = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'login_logs'
        verbose_name = 'Login Log'
        verbose_name_plural = 'Login Logs'
        ordering = ['-login_time']
        indexes = [
            models.Index(fields=['tenant', 'login_time']),
            models.Index(fields=['user', 'login_time']),
            models.Index(fields=['ip_address']),
        ]
    
    def __str__(self):
        status = "Successful" if self.login_successful else "Failed"
        return f"{self.user} - {status} login at {self.login_time}"
    
    @property
    def session_duration(self):
        """Calculate session duration if logout time is available."""
        if self.logout_time:
            return self.logout_time - self.login_time
        return None


class ActivityLog(models.Model):
    """
    Track general user activities for compliance and analytics.
    """
    ACTIVITY_TYPES = [
        ('document_access', 'Document Access'),
        ('case_view', 'Case View'),
        ('client_view', 'Client View'),
        ('billing_action', 'Billing Action'),
        ('permission_change', 'Permission Change'),
        ('user_management', 'User Management'),
        ('system_config', 'System Configuration'),
        ('data_export', 'Data Export'),
        ('report_generation', 'Report Generation'),
        ('security_event', 'Security Event'),
        ('api_access', 'API Access'),
        ('bulk_operation', 'Bulk Operation'),
        ('search', 'Search'),
        ('filter', 'Filter'),
        ('other', 'Other'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='activity_logs'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='activity_logs'
    )
    activity_type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
    description = models.TextField()
    
    # Related object (optional)
    related_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='related_activities'
    )
    related_object_id = models.CharField(max_length=50, null=True, blank=True)
    related_object = GenericForeignKey('related_content_type', 'related_object_id')
    
    # Request information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    request_path = models.CharField(max_length=255, null=True, blank=True)
    
    # Additional context
    metadata = models.JSONField(null=True, blank=True)
    
    # Timestamp
    timestamp = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'activity_logs'
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['tenant', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['activity_type']),
            models.Index(fields=['ip_address']),
        ]
    
    def __str__(self):
        user_str = f"{self.user}" if self.user else "System"
        return f"{user_str} - {self.activity_type} at {self.timestamp}"


class SecurityEvent(models.Model):
    """
    Track security-related events for monitoring and compliance.
    """
    EVENT_TYPES = [
        ('failed_login', 'Failed Login'),
        ('multiple_failed_logins', 'Multiple Failed Logins'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('permission_denied', 'Permission Denied'),
        ('unauthorized_access', 'Unauthorized Access'),
        ('data_breach_attempt', 'Data Breach Attempt'),
        ('malicious_request', 'Malicious Request'),
        ('brute_force_attempt', 'Brute Force Attempt'),
        ('session_hijack', 'Session Hijack'),
        ('privilege_escalation', 'Privilege Escalation'),
        ('unusual_location', 'Unusual Location'),
        ('unusual_device', 'Unusual Device'),
        ('data_exfiltration', 'Data Exfiltration'),
        ('configuration_change', 'Configuration Change'),
        ('security_policy_violation', 'Security Policy Violation'),
        ('other', 'Other'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='security_events'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='security_events'
    )
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, default='medium')
    
    # Event details
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    target_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    request_path = models.CharField(max_length=255, null=True, blank=True)
    request_method = models.CharField(max_length=10, null=True, blank=True)
    
    # Related object (optional)
    related_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='security_events'
    )
    related_object_id = models.CharField(max_length=50, null=True, blank=True)
    related_object = GenericForeignKey('related_content_type', 'related_object_id')
    
    # Event status
    resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_security_events'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(null=True, blank=True)
    
    # Additional context
    event_data = models.JSONField(null=True, blank=True)
    
    # Timestamps
    timestamp = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'security_events'
        verbose_name = 'Security Event'
        verbose_name_plural = 'Security Events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['tenant', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['event_type']),
            models.Index(fields=['severity']),
            models.Index(fields=['resolved']),
            models.Index(fields=['source_ip']),
        ]
    
    def __str__(self):
        return f"{self.event_type} - {self.severity.upper()} at {self.timestamp}"
    
    def resolve(self, user, notes=""):
        """Mark the security event as resolved."""
        self.resolved = True
        self.resolved_by = user
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save()