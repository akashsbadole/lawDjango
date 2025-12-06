from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.db.models import Count, Sum
from .models import (
    SystemSettings, PlatformMetrics, AdminNote, SystemAnnouncement,
    SystemHealthCheck, AdminActivityLog
)


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    """Admin configuration for SystemSettings."""
    
    list_display = [
        'platform_name', 'platform_version', 'support_email',
        'allow_public_registration', 'maintenance_mode'
    ]
    search_fields = ['platform_name', 'support_email']
    list_filter = [
        'allow_public_registration', 'require_admin_approval',
        'maintenance_mode', 'auto_backup_enabled'
    ]
    
    fieldsets = (
        ('Platform Information', {
            'fields': ('platform_name', 'platform_version')
        }),
        ('Contact Information', {
            'fields': ('support_email', 'support_phone')
        }),
        ('Registration Settings', {
            'fields': (
                'allow_public_registration', 'require_admin_approval',
                'default_trial_days'
            )
        }),
        ('System Limits', {
            'fields': ('max_tenants', 'max_users_per_tenant')
        }),
        ('Security Settings', {
            'fields': ('enforce_2fa_for_admins', 'session_timeout_minutes')
        }),
        ('Backup Settings', {
            'fields': ('auto_backup_enabled', 'backup_retention_days')
        }),
        ('Notification Settings', {
            'fields': ('system_alerts_enabled', 'email_notifications_enabled')
        }),
        ('Maintenance Mode', {
            'fields': ('maintenance_mode', 'maintenance_message')
        }),
        ('Custom Styling', {
            'fields': ('custom_css', 'custom_js'),
            'classes': ('collapse',)
        }),
        ('API Settings', {
            'fields': ('api_rate_limit_enabled', 'api_rate_limit_requests')
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow one instance of SystemSettings
        return not SystemSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of SystemSettings
        return False


@admin.register(PlatformMetrics)
class PlatformMetricsAdmin(admin.ModelAdmin):
    """Admin configuration for PlatformMetrics."""
    
    list_display = [
        'metric_type', 'date', 'total_tenants', 'active_tenants',
        'total_users', 'active_subscriptions', 'total_revenue'
    ]
    list_filter = ['metric_type', 'date']
    search_fields = ['date']
    date_hierarchy = 'date'
    
    fieldsets = (
        ('Metric Information', {
            'fields': ('metric_type', 'date')
        }),
        ('Tenant Metrics', {
            'fields': (
                'total_tenants', 'active_tenants', 'new_tenants',
                'churned_tenants'
            )
        }),
        ('User Metrics', {
            'fields': ('total_users', 'active_users', 'new_users')
        }),
        ('Subscription Metrics', {
            'fields': (
                'total_subscriptions', 'active_subscriptions',
                'trial_subscriptions', 'expired_subscriptions'
            )
        }),
        ('Revenue Metrics', {
            'fields': (
                'total_revenue', 'monthly_recurring_revenue',
                'average_revenue_per_tenant'
            )
        }),
        ('Storage Metrics', {
            'fields': (
                'total_storage_used_mb', 'average_storage_per_tenant_mb'
            )
        }),
        ('Performance Metrics', {
            'fields': (
                'average_response_time_ms', 'uptime_percentage',
                'error_rate_percentage'
            )
        }),
        ('Feature Usage Metrics', {
            'fields': (
                'documents_created', 'cases_created',
                'clients_created', 'invoices_generated'
            )
        }),
        ('Additional Metrics', {
            'fields': ('additional_metrics',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = [
        'metric_type', 'date', 'total_tenants', 'active_tenants',
        'new_tenants', 'churned_tenants', 'total_users', 'active_users',
        'new_users', 'total_subscriptions', 'active_subscriptions',
        'trial_subscriptions', 'expired_subscriptions', 'total_revenue',
        'monthly_recurring_revenue', 'average_revenue_per_tenant',
        'total_storage_used_mb', 'average_storage_per_tenant_mb',
        'average_response_time_ms', 'uptime_percentage',
        'error_rate_percentage', 'documents_created', 'cases_created',
        'clients_created', 'invoices_generated', 'additional_metrics'
    ]
    
    def has_add_permission(self, request):
        # Metrics should be generated automatically, not manually
        return False
    
    def has_change_permission(self, request, obj=None):
        # Metrics should be generated automatically, not edited manually
        return False


@admin.register(AdminNote)
class AdminNoteAdmin(admin.ModelAdmin):
    """Admin configuration for AdminNote."""
    
    list_display = [
        'title', 'note_type', 'tenant', 'admin_user', 'is_resolved',
        'requires_follow_up', 'created_at'
    ]
    list_filter = [
        'note_type', 'is_private', 'is_resolved', 'requires_follow_up',
        'created_at'
    ]
    search_fields = ['title', 'content', 'tenant__name', 'admin_user__email']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Note Information', {
            'fields': ('title', 'note_type', 'content')
        }),
        ('Target Information', {
            'fields': ('tenant', 'related_user')
        }),
        ('Status and Flags', {
            'fields': (
                'is_private', 'is_resolved', 'requires_follow_up',
                'follow_up_date'
            )
        }),
        ('Metadata', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['admin_user']
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set on creation
            obj.admin_user = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            # Non-superusers can only see their own notes and non-private notes
            qs = qs.filter(
                Q(admin_user=request.user) | Q(is_private=False)
            )
        return qs


@admin.register(SystemAnnouncement)
class SystemAnnouncementAdmin(admin.ModelAdmin):
    """Admin configuration for SystemAnnouncement."""
    
    list_display = [
        'title', 'announcement_type', 'is_active', 'priority',
        'start_date', 'end_date', 'created_by'
    ]
    list_filter = [
        'announcement_type', 'is_active', 'show_on_login',
        'show_on_dashboard', 'show_as_banner', 'is_dismissible'
    ]
    search_fields = ['title', 'content', 'created_by__email']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Announcement Information', {
            'fields': ('title', 'content', 'announcement_type', 'priority')
        }),
        ('Targeting', {
            'fields': (
                'target_all_tenants', 'target_tenants', 'target_roles'
            )
        }),
        ('Scheduling', {
            'fields': ('is_active', 'start_date', 'end_date')
        }),
        ('Display Options', {
            'fields': (
                'show_on_login', 'show_on_dashboard',
                'show_as_banner', 'is_dismissible'
            )
        }),
    )
    
    readonly_fields = ['created_by']
    filter_horizontal = ['target_tenants']
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set on creation
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('created_by')


@admin.register(SystemHealthCheck)
class SystemHealthCheckAdmin(admin.ModelAdmin):
    """Admin configuration for SystemHealthCheck."""
    
    list_display = [
        'check_type', 'status', 'message', 'check_duration_ms',
        'next_check_due', 'created_at'
    ]
    list_filter = ['check_type', 'status', 'created_at']
    search_fields = ['message', 'check_type']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Check Information', {
            'fields': ('check_type', 'status', 'message')
        }),
        ('Timing Information', {
            'fields': ('check_duration_ms', 'next_check_due')
        }),
        ('Additional Details', {
            'fields': ('details',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = [
        'check_type', 'status', 'message', 'check_duration_ms',
        'next_check_due', 'details', 'created_at'
    ]
    
    def has_add_permission(self, request):
        # Health checks should be generated automatically
        return False
    
    def has_change_permission(self, request, obj=None):
        # Health checks should be generated automatically
        return False


@admin.register(AdminActivityLog)
class AdminActivityLogAdmin(admin.ModelAdmin):
    """Admin configuration for AdminActivityLog."""
    
    list_display = [
        'admin_user', 'action_type', 'action_description',
        'tenant', 'ip_address', 'created_at'
    ]
    list_filter = [
        'action_type', 'created_at', 'admin_user'
    ]
    search_fields = [
        'admin_user__email', 'action_description', 'tenant__name',
        'target_user__email', 'ip_address'
    ]
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Activity Information', {
            'fields': ('admin_user', 'action_type', 'action_description')
        }),
        ('Target Information', {
            'fields': ('tenant', 'target_user')
        }),
        ('Request Information', {
            'fields': ('ip_address', 'user_agent')
        }),
        ('Additional Details', {
            'fields': ('details',),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = [
        'admin_user', 'action_type', 'action_description',
        'tenant', 'target_user', 'ip_address', 'user_agent',
        'details', 'created_at'
    ]
    
    def has_add_permission(self, request):
        # Activity logs should be generated automatically
        return False
    
    def has_change_permission(self, request, obj=None):
        # Activity logs should be generated automatically
        return False
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('admin_user', 'tenant', 'target_user')


# Customize admin site header and title
admin.site.site_header = "Law Firm Platform Administration"
admin.site.site_title = "Platform Admin"
admin.site.index_title = "Welcome to Law Firm Platform Administration"
