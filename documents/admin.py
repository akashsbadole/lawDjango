from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Document model.
    """
    list_display = [
        'title', 'file_name', 'category', 'access_level', 
        'file_size_mb', 'uploaded_by', 'tenant', 'created_at', 'is_deleted'
    ]
    list_filter = [
        'category', 'access_level', 'file_type', 'tenant', 
        'created_at', 'deleted_at'
    ]
    search_fields = [
        'title', 'description', 'file_name', 'tags',
        'case__title', 'case__case_number',
        'client__first_name', 'client__last_name', 'client__email',
        'uploaded_by__email', 'uploaded_by__first_name', 'uploaded_by__last_name'
    ]
    readonly_fields = [
        'file_name', 'file_size', 'file_size_mb', 'file_extension', 
        'mime_type', 'version', 'created_at', 'updated_at', 'deleted_at'
    ]
    filter_horizontal = []
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'file')
        }),
        ('File Information', {
            'fields': (
                'file_name', 'file_size', 'file_size_mb', 'file_extension',
                'mime_type', 'file_type'
            ),
            'classes': ('collapse',)
        }),
        ('Classification', {
            'fields': ('category', 'access_level', 'tags')
        }),
        ('Relationships', {
            'fields': ('tenant', 'case', 'client', 'uploaded_by')
        }),
        ('Version Tracking', {
            'fields': ('version', 'parent_document', 'is_latest_version'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """
        Filter queryset based on user permissions.
        """
        qs = super().get_queryset(request)
        
        # Superusers can see all documents
        if request.user.is_superuser:
            return qs
        
        # Staff users can only see documents from their tenant
        if hasattr(request.user, 'tenant'):
            return qs.filter(tenant=request.user.tenant)
        
        # Non-staff users can't see any documents in admin
        return qs.none()
    
    def get_form(self, request, obj=None, **kwargs):
        """
        Customize form based on user permissions.
        """
        form = super().get_form(request, obj, **kwargs)
        
        # Limit tenant choices for non-superusers
        if not request.user.is_superuser and hasattr(request.user, 'tenant'):
            form.base_fields['tenant'].queryset = form.base_fields['tenant'].queryset.filter(
                id=request.user.tenant.id
            )
            form.base_fields['tenant'].initial = request.user.tenant
        
        # Limit case and client choices to tenant's documents
        if hasattr(request.user, 'tenant'):
            form.base_fields['case'].queryset = form.base_fields['case'].queryset.filter(
                tenant=request.user.tenant, deleted_at__isnull=True
            )
            form.base_fields['client'].queryset = form.base_fields['client'].queryset.filter(
                tenant=request.user.tenant, deleted_at__isnull=True
            )
        
        return form
    
    def save_model(self, request, obj, form, change):
        """
        Set tenant and uploaded_by fields if not already set.
        """
        if not change:  # Creating new document
            if hasattr(request.user, 'tenant') and not obj.tenant:
                obj.tenant = request.user.tenant
            if not obj.uploaded_by:
                obj.uploaded_by = request.user
        
        super().save_model(request, obj, form, change)
    
    def file_size_mb(self, obj):
        """
        Display file size in MB.
        """
        if obj.file_size:
            return f"{obj.file_size / (1024 * 1024):.2f} MB"
        return "-"
    file_size_mb.short_description = "File Size"
    
    def file_extension(self, obj):
        """
        Display file extension.
        """
        if obj.file_name:
            return obj.file_name.split('.')[-1].upper()
        return "-"
    file_extension.short_description = "Extension"
    
    def is_deleted(self, obj):
        """
        Display deletion status with color coding.
        """
        if obj.deleted_at:
            return format_html(
                '<span style="color: #d32f2f; font-weight: bold;">Deleted</span>'
            )
        return format_html(
            '<span style="color: #388e3c; font-weight: bold;">Active</span>'
        )
    is_deleted.short_description = "Status"
    
    def download_link(self, obj):
        """
        Provide a download link for the document.
        """
        if obj.file:
            url = reverse('admin:documents_document_download', args=[obj.pk])
            return format_html(
                '<a href="{}" class="button" target="_blank">Download</a>', url
            )
        return "-"
    download_link.short_description = "Download"
    
    def get_actions(self, request):
        """
        Customize admin actions.
        """
        actions = super().get_actions(request)
        
        # Remove delete action for non-superusers
        if not request.user.is_superuser and 'delete_selected' in actions:
            del actions['delete_selected']
        
        return actions
    
    def response_add(self, request, obj, post_url_continue=None):
        """
        Customize response after adding a document.
        """
        self.message_user(
            request,
            f'Document "{obj.title}" has been successfully uploaded.',
            level='success'
        )
        return super().response_add(request, obj, post_url_continue)
    
    def response_change(self, request, obj):
        """
        Customize response after changing a document.
        """
        self.message_user(
            request,
            f'Document "{obj.title}" has been successfully updated.',
            level='success'
        )
        return super().response_change(request, obj)


# Custom admin site configuration
admin.site.site_header = "Law Firm Management"
admin.site.site_title = "Law Firm Admin"
admin.site.index_title = "Welcome to Law Firm Management Administration"
