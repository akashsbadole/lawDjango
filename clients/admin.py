from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Client model.
    """
    list_display = [
        'full_name',
        'email',
        'phone',
        'company',
        'tenant',
        'created_by',
        'created_at',
        'is_active_status'
    ]
    list_filter = [
        'tenant',
        'company',
        'created_at',
        'updated_at',
        'deleted_at'
    ]
    search_fields = [
        'first_name',
        'last_name',
        'email',
        'phone',
        'company',
        'occupation'
    ]
    readonly_fields = [
        'created_at',
        'updated_at',
        'deleted_at',
        'created_by'
    ]
    
    # Fieldsets for better organization in the admin form
    fieldsets = (
        ('Basic Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone', 'address')
        }),
        ('Professional Information', {
            'fields': ('company', 'occupation'),
            'classes': ('collapse',)
        }),
        ('Legal Information', {
            'fields': ('case_history', 'notes'),
            'classes': ('collapse',)
        }),
        ('Tenant Information', {
            'fields': ('tenant', 'created_by')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )
    
    # Actions for bulk operations
    actions = ['soft_delete_selected', 'restore_selected']
    
    def get_queryset(self, request):
        """
        Override queryset to handle soft deletes.
        """
        qs = super().get_queryset(request)
        
        # If user is not superuser, only show clients from their tenant
        if not request.user.is_superuser and hasattr(request.user, 'tenant'):
            qs = qs.filter(tenant=request.user.tenant)
        
        # Allow viewing deleted clients via GET parameter
        if request.GET.get('show_deleted') == '1':
            return qs
        else:
            return qs.filter(deleted_at__isnull=True)
    
    def is_active_status(self, obj):
        """
        Display active/inactive status with color coding.
        """
        if obj.is_deleted:
            return format_html(
                '<span style="color: #d32f2f; font-weight: bold;">Deleted</span>'
            )
        else:
            return format_html(
                '<span style="color: #388e3c; font-weight: bold;">Active</span>'
            )
    is_active_status.short_description = 'Status'
    is_active_status.admin_order_field = 'deleted_at'
    
    def get_actions(self, request):
        """
        Customize actions based on whether we're showing deleted clients.
        """
        actions = super().get_actions(request)
        
        # Remove delete action if we're showing deleted clients
        if request.GET.get('show_deleted') == '1':
            if 'delete_selected' in actions:
                del actions['delete_selected']
        else:
            # Remove restore action if we're not showing deleted clients
            if 'restore_selected' in actions:
                del actions['restore_selected']
        
        return actions
    
    def soft_delete_selected(self, request, queryset):
        """
        Custom action to soft delete selected clients.
        """
        count = queryset.count()
        for client in queryset:
            client.soft_delete()
        
        self.message_user(
            request,
            f'{count} client(s) have been soft deleted.',
            level='success'
        )
    soft_delete_selected.short_description = 'Soft delete selected clients'
    
    def restore_selected(self, request, queryset):
        """
        Custom action to restore selected soft-deleted clients.
        """
        count = queryset.count()
        for client in queryset:
            client.restore()
        
        self.message_user(
            request,
            f'{count} client(s) have been restored.',
            level='success'
        )
    restore_selected.short_description = 'Restore selected clients'
    
    def response_change(self, request, obj):
        """
        Customize response after changing an object.
        """
        if '_soft_delete' in request.POST:
            obj.soft_delete()
            self.message_user(
                request,
                f'Client "{obj.full_name}" has been soft deleted.',
                level='success'
            )
            return reverse('admin:clients_client_changelist')
        
        return super().response_change(request, obj)
    
    def change_view(self, request, object_id, form_url='', extra_context=None):
        """
        Customize the change view to add soft delete button.
        """
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        
        if obj and not obj.is_deleted:
            extra_context['show_soft_delete'] = True
        
        return super().change_view(
            request, object_id, form_url, extra_context=extra_context
        )
    
    def changelist_view(self, request, extra_context=None):
        """
        Customize the changelist view to show/hide deleted clients.
        """
        extra_context = extra_context or {}
        extra_context['show_deleted'] = request.GET.get('show_deleted') == '1'
        return super().changelist_view(request, extra_context=extra_context)
