from django.contrib import admin
from .models import TenantPermission, Role, UserRole


@admin.register(TenantPermission)
class TenantPermissionAdmin(admin.ModelAdmin):
    list_display = ['name', 'codename', 'module', 'created_at']
    list_filter = ['module', 'created_at']
    search_fields = ['name', 'codename', 'description']
    ordering = ['module', 'name']
    readonly_fields = ['created_at']


class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 1
    readonly_fields = ['assigned_at', 'assigned_by']
    raw_id_fields = ['user', 'assigned_by']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'tenant', 'is_system_role', 'permission_count', 'created_at']
    list_filter = ['is_system_role', 'created_at', 'tenant']
    search_fields = ['name', 'description', 'tenant__name']
    readonly_fields = ['created_at', 'updated_at']
    filter_horizontal = ['permissions']
    inlines = [UserRoleInline]
    
    def permission_count(self, obj):
        return obj.permissions.count()
    permission_count.short_description = 'Permissions'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by tenant for non-superusers
        if hasattr(request.user, 'tenant'):
            return qs.filter(tenant=request.user.tenant)
        return qs.none()
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if hasattr(request.user, 'tenant') and 'tenant' in form.base_fields:
            form.base_fields['tenant'].queryset = form.base_fields['tenant'].queryset.filter(
                id=request.user.tenant.id
            )
            if not obj:
                form.base_fields['tenant'].initial = request.user.tenant
        return form
    
    def save_model(self, request, obj, form, change):
        if hasattr(request.user, 'tenant') and not obj.tenant_id:
            obj.tenant = request.user.tenant
        super().save_model(request, obj, form, change)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'tenant', 'assigned_at', 'assigned_by']
    list_filter = ['role', 'tenant', 'assigned_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'role__name', 'tenant__name']
    readonly_fields = ['assigned_at']
    raw_id_fields = ['user', 'assigned_by']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Filter by tenant for non-superusers
        if hasattr(request.user, 'tenant'):
            return qs.filter(tenant=request.user.tenant)
        return qs.none()
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if hasattr(request.user, 'tenant'):
            # Filter by tenant
            if 'tenant' in form.base_fields:
                form.base_fields['tenant'].queryset = form.base_fields['tenant'].queryset.filter(
                    id=request.user.tenant.id
                )
                if not obj:
                    form.base_fields['tenant'].initial = request.user.tenant
            
            if 'user' in form.base_fields:
                form.base_fields['user'].queryset = form.base_fields['user'].queryset.filter(
                    tenant=request.user.tenant
                )
            
            if 'role' in form.base_fields:
                form.base_fields['role'].queryset = form.base_fields['role'].queryset.filter(
                    tenant=request.user.tenant
                )
            
            if 'assigned_by' in form.base_fields:
                form.base_fields['assigned_by'].queryset = form.base_fields['assigned_by'].queryset.filter(
                    tenant=request.user.tenant
                )
                if not obj:
                    form.base_fields['assigned_by'].initial = request.user
        return form
    
    def save_model(self, request, obj, form, change):
        if hasattr(request.user, 'tenant'):
            if not obj.tenant_id:
                obj.tenant = request.user.tenant
            if not obj.assigned_by_id:
                obj.assigned_by = request.user
        super().save_model(request, obj, form, change)
