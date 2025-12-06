from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import AuditLog, ActivityLog, SecurityEvent, LoginLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Admin configuration for AuditLog model.
    """
    list_display = [
        'timestamp', 'user', 'action', 'model_name', 'object_repr', 
        'ip_address', 'changes_summary'
    ]
    list_filter = [
        'action', 'model_name', 'timestamp', 'tenant'
    ]
    search_fields = [
        'user__email', 'model_name', 'object_repr', 'ip_address'
    ]
    readonly_fields = [
        'tenant', 'user', 'action', 'model_name', 'object_id', 'object_repr',
        'content_type', 'content_object', 'old_values', 'new_values',
        'changed_fields', 'ip_address', 'user_agent', 'session_key',
        'request_path', 'request_method', 'additional_data', 'timestamp'
    ]
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'user', 'timestamp', 'action')
        }),
        ('Object Information', {
            'fields': ('model_name', 'object_id', 'object_repr', 'content_type', 'content_object')
        }),
        ('Change Details', {
            'fields': ('old_values', 'new_values', 'changed_fields')
        }),
        ('Request Information', {
            'fields': ('ip_address', 'user_agent', 'session_key', 'request_path', 'request_method')
        }),
        ('Additional Data', {
            'fields': ('additional_data',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by tenant for non-superusers
        return qs.filter(tenant=request.user.tenant)
    
    def has_add_permission(self, request):
        # Audit logs should not be manually added
        return False
    
    def has_change_permission(self, request, obj=None):
        # Audit logs should not be changed
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Only superusers can delete audit logs
        return request.user.is_superuser


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """
    Admin configuration for ActivityLog model.
    """
    list_display = [
        'timestamp', 'user', 'activity_type', 'description', 
        'ip_address', 'related_object_link'
    ]
    list_filter = [
        'activity_type', 'timestamp', 'tenant'
    ]
    search_fields = [
        'user__email', 'activity_type', 'description', 'ip_address'
    ]
    readonly_fields = [
        'tenant', 'user', 'activity_type', 'description',
        'related_content_type', 'related_object_id', 'related_object',
        'ip_address', 'user_agent', 'request_path', 'metadata', 'timestamp'
    ]
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'user', 'timestamp', 'activity_type')
        }),
        ('Activity Details', {
            'fields': ('description', 'related_content_type', 'related_object_id', 'related_object')
        }),
        ('Request Information', {
            'fields': ('ip_address', 'user_agent', 'request_path')
        }),
        ('Metadata', {
            'fields': ('metadata',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(tenant=request.user.tenant)
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def related_object_link(self, obj):
        if obj.related_object:
            url = reverse(f'admin:{obj.related_content_type.app_label}_{obj.related_content_type.model}_change', 
                          args=[obj.related_object_id])
            return format_html(
                '<a href="{}">{}</a>', 
                url, str(obj.related_object)
            )
        return '-'
    related_object_link.short_description = 'Related Object'


@admin.register(SecurityEvent)
class SecurityEventAdmin(admin.ModelAdmin):
    """
    Admin configuration for SecurityEvent model.
    """
    list_display = [
        'timestamp', 'user', 'event_type', 'severity', 'description',
        'resolved_status', 'source_ip'
    ]
    list_filter = [
        'event_type', 'severity', 'resolved', 'timestamp', 'tenant'
    ]
    search_fields = [
        'user__email', 'event_type', 'description', 'source_ip'
    ]
    readonly_fields = [
        'tenant', 'user', 'event_type', 'description', 'severity',
        'source_ip', 'target_ip', 'user_agent', 'request_path', 'request_method',
        'related_content_type', 'related_object_id', 'related_object',
        'event_data', 'timestamp', 'created_at', 'updated_at'
    ]
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'user', 'timestamp', 'event_type', 'severity')
        }),
        ('Event Details', {
            'fields': ('description', 'source_ip', 'target_ip', 'user_agent', 
                      'request_path', 'request_method')
        }),
        ('Related Object', {
            'fields': ('related_content_type', 'related_object_id', 'related_object')
        }),
        ('Event Data', {
            'fields': ('event_data',)
        }),
        ('Resolution', {
            'fields': ('resolved', 'resolved_by', 'resolved_at', 'resolution_notes')
        }),
    )
    
    actions = ['mark_as_resolved', 'mark_as_unresolved']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(tenant=request.user.tenant)
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        # Allow changing resolution fields
        if obj:
            return request.user.is_superuser or obj.tenant == request.user.tenant
        return True
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def resolved_status(self, obj):
        if obj.resolved:
            return format_html(
                '<span style="color: green;">✓ Resolved by {}</span>',
                obj.resolved_by.email if obj.resolved_by else 'Unknown'
            )
        return format_html(
            '<span style="color: red;">✗ Unresolved</span>'
        )
    resolved_status.short_description = 'Status'
    resolved_status.admin_order_field = 'resolved'
    
    def mark_as_resolved(self, request, queryset):
        count = 0
        for event in queryset:
            if not event.resolved:
                event.resolve(request.user, "Bulk resolved via admin")
                count += 1
        self.message_user(request, f'{count} security events marked as resolved.')
    mark_as_resolved.short_description = 'Mark selected as resolved'
    
    def mark_as_unresolved(self, request, queryset):
        count = queryset.filter(resolved=True).update(
            resolved=False, resolved_by=None, resolved_at=None, resolution_notes=''
        )
        self.message_user(request, f'{count} security events marked as unresolved.')
    mark_as_unresolved.short_description = 'Mark selected as unresolved'


@admin.register(LoginLog)
class LoginLogAdmin(admin.ModelAdmin):
    """
    Admin configuration for LoginLog model.
    """
    list_display = [
        'login_time', 'user', 'login_successful', 'ip_address',
        'user_agent_short', 'session_duration'
    ]
    list_filter = [
        'login_successful', 'login_time', 'tenant'
    ]
    search_fields = [
        'user__email', 'ip_address', 'user_agent', 'failure_reason'
    ]
    readonly_fields = [
        'tenant', 'user', 'login_time', 'logout_time', 'ip_address',
        'user_agent', 'session_key', 'login_successful', 'failure_reason',
        'device_info', 'location_info'
    ]
    date_hierarchy = 'login_time'
    ordering = ['-login_time']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'user', 'login_time', 'logout_time')
        }),
        ('Login Details', {
            'fields': ('login_successful', 'failure_reason', 'session_key')
        }),
        ('Request Information', {
            'fields': ('ip_address', 'user_agent', 'device_info', 'location_info')
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(tenant=request.user.tenant)
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        # Allow updating logout time
        return True
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def user_agent_short(self, obj):
        if obj.user_agent:
            # Truncate long user agents
            if len(obj.user_agent) > 50:
                return obj.user_agent[:50] + '...'
            return obj.user_agent
        return '-'
    user_agent_short.short_description = 'User Agent'
    
    def session_duration(self, obj):
        if obj.session_duration:
            total_seconds = int(obj.session_duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return '-'
    session_duration.short_description = 'Duration'
    session_duration.admin_order_field = 'logout_time'


# Customize admin site headers for audit models
admin.site.site_header = "Law Firm Management System"
admin.site.site_title = "Law Firm Admin"
admin.site.index_title = "Welcome to Law Firm Management System"

# Add custom CSS for better display
class AuditAdminMixin:
    """
    Mixin to add custom CSS for audit admin pages.
    """
    
    class Media:
        css = {
            'all': ('admin/css/audit_admin.css',)
        }


# Apply the mixin to all audit admin classes
for admin_class in [AuditLogAdmin, ActivityLogAdmin, SecurityEventAdmin, LoginLogAdmin]:
    admin_class.__bases__ = (AuditAdminMixin,) + admin_class.__bases__