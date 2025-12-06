from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Tenant, TenantSettings, TenantStatusHistory


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'slug',
        'status_display',
        'plan',
        'user_count',
        'storage_display',
        'is_active',
        'created_at'
    ]
    list_filter = ['status', 'plan', 'is_active', 'created_at']
    search_fields = ['name', 'slug']
    readonly_fields = ['created_at', 'updated_at', 'deleted_at', 'suspended_at', 'user_count', 'storage_display']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'status', 'is_active')
        }),
        ('Plan Information', {
            'fields': ('plan', 'max_users', 'max_storage_mb')
        }),
        ('Status Information', {
            'fields': ('deleted_at', 'suspended_at', 'suspension_reason'),
            'classes': ('collapse',)
        }),
        ('Usage Statistics', {
            'fields': ('user_count', 'storage_display'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_display(self, obj):
        """Display tenant status with appropriate icon."""
        return format_html(obj.get_status_display_with_icon())
    status_display.short_description = 'Status'
    
    def user_count(self, obj):
        """Display the current number of users for this tenant."""
        count = obj.get_current_user_count()
        max_users = obj.max_users
        
        if count >= max_users:
            color = 'red'
        elif count >= max_users * 0.8:
            color = 'orange'
        else:
            color = 'green'
            
        return format_html(
            '<span style="color: {};">{}/{} users</span>',
            color, count, max_users
        )
    user_count.short_description = 'User Count'
    
    def storage_display(self, obj):
        """Display the current storage usage for this tenant."""
        used = obj.get_storage_used()
        max_storage = obj.max_storage_mb
        
        if max_storage > 0:
            percentage = (used / max_storage) * 100
            if percentage >= 90:
                color = 'red'
            elif percentage >= 70:
                color = 'orange'
            else:
                color = 'green'
                
            return format_html(
                '<span style="color: {};">{} MB / {} MB ({:.1f}%)</span>',
                color, used, max_storage, percentage
            )
        return format_html('{} MB / {} MB', used, max_storage)
    storage_display.short_description = 'Storage Usage'
    
    actions = ['soft_delete_selected', 'restore_selected', 'suspend_selected', 'unsuspend_selected', 'expire_trial_selected']
    
    def soft_delete_selected(self, request, queryset):
        """Soft delete selected tenants."""
        count = 0
        for tenant in queryset:
            if not tenant.is_deleted:
                tenant.soft_delete(changed_by=request.user)
                count += 1
        self.message_user(request, f'{count} tenant(s) have been soft deleted.')
    soft_delete_selected.short_description = 'Soft delete selected tenants'
    
    def restore_selected(self, request, queryset):
        """Restore selected soft-deleted tenants."""
        count = 0
        for tenant in queryset:
            if tenant.is_deleted:
                tenant.restore(changed_by=request.user)
                count += 1
        self.message_user(request, f'{count} tenant(s) have been restored.')
    restore_selected.short_description = 'Restore selected tenants'
    
    def suspend_selected(self, request, queryset):
        """Suspend selected tenants."""
        count = 0
        for tenant in queryset:
            if tenant.status == 'active':
                tenant.suspend(reason="Suspended by admin", changed_by=request.user)
                count += 1
        self.message_user(request, f'{count} tenant(s) have been suspended.')
    suspend_selected.short_description = 'Suspend selected tenants'
    
    def unsuspend_selected(self, request, queryset):
        """Unsuspend selected tenants."""
        count = 0
        for tenant in queryset:
            if tenant.status == 'suspended':
                tenant.unsuspend(changed_by=request.user)
                count += 1
        self.message_user(request, f'{count} tenant(s) have been unsuspended.')
    unsuspend_selected.short_description = 'Unsuspend selected tenants'
    
    def expire_trial_selected(self, request, queryset):
        """Mark trial as expired for selected tenants."""
        count = 0
        for tenant in queryset:
            if tenant.status == 'active':
                tenant.expire_trial(changed_by=request.user)
                count += 1
        self.message_user(request, f'{count} tenant(s) trials have been expired.')
    expire_trial_selected.short_description = 'Mark trial as expired for selected tenants'
    
    def get_queryset(self, request):
        """Customize the queryset to include soft-deleted tenants with an option to filter."""
        qs = super().get_queryset(request)
        
        # Add a parameter to show deleted tenants
        if request.GET.get('show_deleted') == '1':
            return qs
        else:
            return qs.filter(deleted_at__isnull=True)
    
    def changelist_view(self, request, extra_context=None):
        """Add custom context to the changelist view."""
        extra_context = extra_context or {}
        extra_context['show_deleted'] = request.GET.get('show_deleted') == '1'
        return super().changelist_view(request, extra_context)


@admin.register(TenantSettings)
class TenantSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'tenant',
        'company_name',
        'primary_color',
        'default_currency',
        'enable_client_portal',
        'enable_document_sharing',
        'enable_time_tracking',
        'updated_at'
    ]
    list_filter = [
        'default_currency',
        'timezone',
        'enable_client_portal',
        'enable_document_sharing',
        'enable_time_tracking',
        'email_notifications',
        'two_factor_required',
        'updated_at'
    ]
    search_fields = ['tenant__name', 'company_name']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-updated_at']
    
    fieldsets = (
        ('Tenant Information', {
            'fields': ('tenant',)
        }),
        ('Branding Settings', {
            'fields': ('logo', 'primary_color', 'secondary_color', 'company_name'),
            'classes': ('collapse',)
        }),
        ('Date and Time Preferences', {
            'fields': ('date_format', 'time_format', 'timezone'),
            'classes': ('collapse',)
        }),
        ('Billing Settings', {
            'fields': ('default_currency', 'tax_rate', 'invoice_prefix', 'payment_terms'),
            'classes': ('collapse',)
        }),
        ('Document Settings', {
            'fields': ('default_categories', 'retention_days'),
            'classes': ('collapse',)
        }),
        ('Notification Preferences', {
            'fields': ('email_notifications', 'sms_notifications', 'in_app_notifications'),
            'classes': ('collapse',)
        }),
        ('Security Settings', {
            'fields': ('password_policy', 'two_factor_required', 'session_timeout'),
            'classes': ('collapse',)
        }),
        ('Feature Toggles', {
            'fields': ('enable_client_portal', 'enable_document_sharing', 'enable_time_tracking'),
            'classes': ('collapse',)
        }),
        ('Email Template Customization', {
            'fields': ('email_header', 'email_footer'),
            'classes': ('collapse',)
        }),
        ('Custom Fields Configuration', {
            'fields': ('custom_fields',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Customize the queryset to filter by tenant if user is not superuser."""
        qs = super().get_queryset(request)
        
        # If user is not superuser, only show settings for their tenant
        if not request.user.is_superuser and hasattr(request.user, 'tenant'):
            qs = qs.filter(tenant=request.user.tenant)
            
        return qs
    
    def get_form(self, request, obj=None, **kwargs):
        """Customize the form to filter tenant field if user is not superuser."""
        form = super().get_form(request, obj, **kwargs)
        
        # If user is not superuser, filter tenant field
        if not request.user.is_superuser and hasattr(request.user, 'tenant'):
            if 'tenant' in form.base_fields:
                form.base_fields['tenant'].queryset = form.base_fields['tenant'].queryset.filter(
                    id=request.user.tenant.id
                )
                form.base_fields['tenant'].initial = request.user.tenant
        
        return form
    
    def save_model(self, request, obj, form, change):
        """Set tenant for non-superuser users."""
        if not request.user.is_superuser and hasattr(request.user, 'tenant'):
            obj.tenant = request.user.tenant
        super().save_model(request, obj, form, change)


@admin.register(TenantStatusHistory)
class TenantStatusHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'tenant',
        'old_status',
        'new_status',
        'reason',
        'changed_by',
        'changed_at'
    ]
    list_filter = [
        'new_status',
        'old_status',
        'changed_at'
    ]
    search_fields = [
        'tenant__name',
        'reason'
    ]
    readonly_fields = [
        'tenant',
        'old_status',
        'new_status',
        'changed_by',
        'changed_at'
    ]
    ordering = ['-changed_at']
    
    fieldsets = (
        ('Status Change Information', {
            'fields': ('tenant', 'old_status', 'new_status', 'reason')
        }),
        ('Audit Information', {
            'fields': ('changed_by', 'changed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Disable manual addition of status history records."""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Status history should be read-only."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of status history records."""
        return request.user.is_superuser