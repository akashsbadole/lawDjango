from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied

def can_import_data(user):
    """Check if user has permission to import data."""
    return user.is_authenticated and (
        user.is_superuser or 
        user.role in ['admin', 'manager'] or
        user.has_perm('import_export.add_importjob')
    )

def can_export_data(user):
    """Check if user has permission to export data."""
    return user.is_authenticated and (
        user.is_superuser or 
        user.role in ['admin', 'manager'] or
        user.has_perm('import_export.add_exportjob')
    )

def can_manage_templates(user):
    """Check if user has permission to manage import templates."""
    return user.is_authenticated and (
        user.is_superuser or 
        user.role in ['admin', 'manager'] or
        user.has_perm('import_export.add_importtemplate')
    )

def can_view_import_jobs(user):
    """Check if user can view import jobs."""
    return user.is_authenticated and (
        user.is_superuser or 
        user.role in ['admin', 'manager'] or
        user.has_perm('import_export.view_importjob')
    )

def can_view_export_jobs(user):
    """Check if user can view export jobs."""
    return user.is_authenticated and (
        user.is_superuser or 
        user.role in ['admin', 'manager'] or
        user.has_perm('import_export.view_exportjob')
    )

# Decorators for use in views
import_permission_required = user_passes_test(can_import_data, login_url='/accounts/login/')
export_permission_required = user_passes_test(can_export_data, login_url='/accounts/login/')
template_permission_required = user_passes_test(can_manage_templates, login_url='/accounts/login/')
import_view_permission_required = user_passes_test(can_view_import_jobs, login_url='/accounts/login/')
export_view_permission_required = user_passes_test(can_view_export_jobs, login_url='/accounts/login/')


class ImportExportPermissionsMixin:
    """Mixin to check import/export permissions in class-based views."""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        
        # Check specific permissions based on the view
        if hasattr(self, 'permission_type'):
            if self.permission_type == 'import':
                if not can_import_data(request.user):
                    raise PermissionDenied("You don't have permission to import data.")
            elif self.permission_type == 'export':
                if not can_export_data(request.user):
                    raise PermissionDenied("You don't have permission to export data.")
            elif self.permission_type == 'template':
                if not can_manage_templates(request.user):
                    raise PermissionDenied("You don't have permission to manage templates.")
            elif self.permission_type == 'import_view':
                if not can_view_import_jobs(request.user):
                    raise PermissionDenied("You don't have permission to view import jobs.")
            elif self.permission_type == 'export_view':
                if not can_view_export_jobs(request.user):
                    raise PermissionDenied("You don't have permission to view export jobs.")
        
        return super().dispatch(request, *args, **kwargs)