from django.contrib import admin
from .models import Case, CaseEvent


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Case model.
    """
    list_display = [
        'case_number', 'title', 'client', 'status', 'case_type',
        'start_date', 'get_assigned_lawyers', 'tenant'
    ]
    list_filter = [
        'status', 'case_type', 'start_date', 'created_at', 'tenant'
    ]
    search_fields = [
        'title', 'case_number', 'description', 'client__first_name', 
        'client__last_name', 'client__email', 'notes'
    ]
    filter_horizontal = ['assigned_lawyers']
    date_hierarchy = 'start_date'
    readonly_fields = ['created_at', 'updated_at', 'deleted_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'case_number', 'description', 'tenant')
        }),
        ('Case Classification', {
            'fields': ('status', 'case_type')
        }),
        ('Relationships', {
            'fields': ('client', 'assigned_lawyers')
        }),
        ('Important Dates', {
            'fields': ('start_date', 'end_date')
        }),
        ('Case Outcome and Notes', {
            'fields': ('outcome', 'notes')
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Filter cases by tenant for non-superusers."""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs.none()
    
    def get_form(self, request, obj=None, **kwargs):
        """Filter form fields based on user's tenant."""
        form = super().get_form(request, obj, **kwargs)
        
        if not request.user.is_superuser and hasattr(request.user, 'tenant'):
            # Filter client choices by tenant
            from clients.models import Client
            form.base_fields['client'].queryset = Client.objects.active_for_tenant(
                request.user.tenant
            )
            
            # Filter assigned lawyers by tenant
            from django.contrib.auth import get_user_model
            User = get_user_model()
            form.base_fields['assigned_lawyers'].queryset = User.objects.filter(
                tenant=request.user.tenant,
                is_active=True
            )
            
            # Set tenant field to user's tenant and make it read-only
            form.base_fields['tenant'].initial = request.user.tenant
            form.base_fields['tenant'].disabled = True
        
        return form
    
    def save_model(self, request, obj, form, change):
        """Set created_by and tenant for new cases."""
        if not change:  # Only for new cases
            obj.created_by = request.user
            if hasattr(request.user, 'tenant') and not obj.tenant:
                obj.tenant = request.user.tenant
        super().save_model(request, obj, form, change)
    
    def get_assigned_lawyers(self, obj):
        """Display assigned lawyers in admin list view."""
        return ", ".join([lawyer.get_full_name() or lawyer.email for lawyer in obj.assigned_lawyers.all()])
    get_assigned_lawyers.short_description = 'Assigned Lawyers'


@admin.register(CaseEvent)
class CaseEventAdmin(admin.ModelAdmin):
    """
    Admin configuration for the CaseEvent model.
    """
    list_display = [
        'title', 'event_type', 'case', 'event_date', 'created_by', 'tenant'
    ]
    list_filter = [
        'event_type', 'event_date', 'created_at', 'tenant'
    ]
    search_fields = [
        'title', 'description', 'case__title', 'case__case_number'
    ]
    date_hierarchy = 'event_date'
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Event Information', {
            'fields': ('event_type', 'title', 'description', 'event_date', 'tenant')
        }),
        ('Relationships', {
            'fields': ('case', 'created_by')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Filter case events by tenant for non-superusers."""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if hasattr(request.user, 'tenant') and request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        return qs.none()
    
    def get_form(self, request, obj=None, **kwargs):
        """Filter form fields based on user's tenant."""
        form = super().get_form(request, obj, **kwargs)
        
        if not request.user.is_superuser and hasattr(request.user, 'tenant'):
            # Filter case choices by tenant
            form.base_fields['case'].queryset = Case.objects.active_for_tenant(
                request.user.tenant
            )
            
            # Set tenant field to user's tenant and make it read-only
            form.base_fields['tenant'].initial = request.user.tenant
            form.base_fields['tenant'].disabled = True
        
        return form
    
    def save_model(self, request, obj, form, change):
        """Set created_by and tenant for new case events."""
        if not change:  # Only for new events
            obj.created_by = request.user
            if hasattr(request.user, 'tenant') and not obj.tenant:
                obj.tenant = request.user.tenant
        super().save_model(request, obj, form, change)
