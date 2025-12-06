from django.contrib import admin
from .models import BackupJob, RestoreJob, BackupSchedule


@admin.register(BackupJob)
class BackupJobAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'backup_type', 'status', 'tenant', 'created_by',
        'file_size_mb', 'progress_percentage', 'created_at'
    ]
    list_filter = ['status', 'backup_type', 'tenant', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = [
        'file_path', 'file_name', 'file_size', 'file_hash',
        'progress_percentage', 'current_step', 'error_message',
        'started_at', 'completed_at'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'backup_type', 'status')
        }),
        ('Backup Options', {
            'fields': (
                'include_database', 'include_media', 'include_documents', 'include_settings',
                'compress', 'encrypted', 'parent_backup'
            )
        }),
        ('File Information', {
            'fields': ('file_path', 'file_name', 'file_size', 'file_hash'),
            'classes': ('collapse',)
        }),
        ('Progress Information', {
            'fields': (
                'progress_percentage', 'current_step', 'error_message',
                'started_at', 'completed_at'
            ),
            'classes': ('collapse',)
        }),
        ('Tenant Information', {
            'fields': ('tenant', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(tenant=request.user.tenant)
    
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj and obj.status in ['running', 'completed', 'failed']:
            readonly.extend(['backup_type', 'include_database', 'include_media', 
                          'include_documents', 'include_settings', 'compress', 'encrypted'])
        return readonly
    
    def file_size_mb(self, obj):
        """Display file size in MB."""
        if obj.file_size:
            return f"{obj.file_size_mb} MB"
        return "N/A"
    
    def tenant(self, obj):
        """Display tenant name."""
        return obj.tenant.name if obj.tenant else "N/A"
    
    def created_by(self, obj):
        """Display created by user."""
        return obj.created_by.email if obj.created_by else "System"


@admin.register(RestoreJob)
class RestoreJobAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'status', 'tenant', 'created_by',
        'conflict_resolution', 'records_restored', 'created_at'
    ]
    list_filter = ['status', 'conflict_resolution', 'tenant', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = [
        'backup_file', 'backup_job', 'preview_data', 'conflicts',
        'progress_percentage', 'current_step', 'error_message',
        'records_restored', 'records_skipped', 'records_failed',
        'started_at', 'completed_at'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'status', 'conflict_resolution')
        }),
        ('Restore Options', {
            'fields': (
                'restore_database', 'restore_media', 'restore_documents', 'restore_settings'
            )
        }),
        ('Backup Information', {
            'fields': ('backup_file', 'backup_job'),
            'classes': ('collapse',)
        }),
        ('Preview Information', {
            'fields': ('preview_data', 'conflicts'),
            'classes': ('collapse',)
        }),
        ('Progress Information', {
            'fields': (
                'progress_percentage', 'current_step', 'error_message',
                'records_restored', 'records_skipped', 'records_failed',
                'started_at', 'completed_at'
            ),
            'classes': ('collapse',)
        }),
        ('Tenant Information', {
            'fields': ('tenant', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(tenant=request.user.tenant)
    
    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)
        if obj and obj.status in ['running', 'completed', 'failed']:
            readonly.extend(['restore_database', 'restore_media', 'restore_documents', 'restore_settings'])
        return readonly
    
    def tenant(self, obj):
        """Display tenant name."""
        return obj.tenant.name if obj.tenant else "N/A"
    
    def created_by(self, obj):
        """Display created by user."""
        return obj.created_by.email if obj.created_by else "System"


@admin.register(BackupSchedule)
class BackupScheduleAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'frequency', 'backup_type', 'is_active',
        'tenant', 'next_run', 'last_run', 'created_at'
    ]
    list_filter = ['frequency', 'backup_type', 'is_active', 'tenant', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = [
        'last_run', 'next_run', 'last_backup_job'
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'frequency', 'backup_type', 'is_active')
        }),
        ('Schedule Configuration', {
            'fields': ('run_at', 'run_day', 'run_weekday')
        }),
        ('Retention Policy', {
            'fields': ('retention_days', 'retention_count')
        }),
        ('Backup Options', {
            'fields': (
                'include_database', 'include_media', 'include_documents', 'include_settings',
                'compress', 'encrypt'
            )
        }),
        ('Notification Settings', {
            'fields': ('email_notification', 'email_recipients')
        }),
        ('Execution Information', {
            'fields': ('last_run', 'next_run', 'last_backup_job'),
            'classes': ('collapse',)
        }),
        ('Tenant Information', {
            'fields': ('tenant', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(tenant=request.user.tenant)
    
    def tenant(self, obj):
        """Display tenant name."""
        return obj.tenant.name if obj.tenant else "N/A"
    
    def created_by(self, obj):
        """Display created by user."""
        return obj.created_by.email if obj.created_by else "System"