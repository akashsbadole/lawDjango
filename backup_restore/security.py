"""
Security features for backup and restore operations.

This module handles access control, audit logging,
and security checks for backup/restore operations.
"""

import logging
from datetime import datetime
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db import transaction
from .models import BackupJob, RestoreJob, BackupSchedule
from audit.models import AuditLog

User = get_user_model()
logger = logging.getLogger(__name__)


class BackupRestorePermissions:
    """
    Permission constants for backup and restore operations.
    """
    VIEW_BACKUP = 'backup_restore.view_backup'
    CREATE_BACKUP = 'backup_restore.create_backup'
    EXECUTE_BACKUP = 'backup_restore.execute_backup'
    DELETE_BACKUP = 'backup_restore.delete_backup'
    DOWNLOAD_BACKUP = 'backup_restore.download_backup'
    
    VIEW_RESTORE = 'backup_restore.view_restore'
    CREATE_RESTORE = 'backup_restore.create_restore'
    EXECUTE_RESTORE = 'backup_restore.execute_restore'
    DELETE_RESTORE = 'backup_restore.delete_restore'
    
    VIEW_SCHEDULE = 'backup_restore.view_schedule'
    CREATE_SCHEDULE = 'backup_restore.create_schedule'
    UPDATE_SCHEDULE = 'backup_restore.update_schedule'
    DELETE_SCHEDULE = 'backup_restore.delete_schedule'
    EXECUTE_SCHEDULE = 'backup_restore.execute_schedule'


def check_backup_permission(user, backup_job, permission):
    """
    Check if a user has permission to access a specific backup job.
    """
    # Check basic permission
    if not user.has_perm(permission):
        return False
    
    # Check tenant ownership
    if backup_job.tenant != user.tenant:
        return False
    
    # Additional checks for sensitive operations
    if permission in [
        BackupRestorePermissions.DELETE_BACKUP,
        BackupRestorePermissions.DOWNLOAD_BACKUP,
        BackupRestorePermissions.EXECUTE_BACKUP
    ]:
        # Only allow if user is the creator or has admin role
        if backup_job.created_by != user and not user.has_role('Admin'):
            return False
    
    return True


def check_restore_permission(user, restore_job, permission):
    """
    Check if a user has permission to access a specific restore job.
    """
    # Check basic permission
    if not user.has_perm(permission):
        return False
    
    # Check tenant ownership
    if restore_job.tenant != user.tenant:
        return False
    
    # Additional checks for sensitive operations
    if permission in [
        BackupRestorePermissions.DELETE_RESTORE,
        BackupRestorePermissions.EXECUTE_RESTORE
    ]:
        # Only allow if user is the creator or has admin role
        if restore_job.created_by != user and not user.has_role('Admin'):
            return False
    
    return True


def check_schedule_permission(user, schedule, permission):
    """
    Check if a user has permission to access a specific backup schedule.
    """
    # Check basic permission
    if not user.has_perm(permission):
        return False
    
    # Check tenant ownership
    if schedule.tenant != user.tenant:
        return False
    
    # Additional checks for sensitive operations
    if permission in [
        BackupRestorePermissions.DELETE_SCHEDULE,
        BackupRestorePermissions.UPDATE_SCHEDULE,
        BackupRestorePermissions.EXECUTE_SCHEDULE
    ]:
        # Only allow if user is the creator or has admin role
        if schedule.created_by != user and not user.has_role('Admin'):
            return False
    
    return True


def log_backup_access(user, backup_job, action, details=None):
    """
    Log access to backup jobs for audit purposes.
    """
    try:
        with transaction.atomic():
            AuditLog.objects.create(
                user=user,
                tenant=user.tenant,
                action=f"backup_{action}",
                object_type='backup_job',
                object_id=backup_job.pk,
                object_repr=str(backup_job),
                details=details or f"User {user.email} {action} backup job {backup_job.name}",
                ip_address=get_client_ip(user),
                timestamp=timezone.now()
            )
    except Exception as e:
        logger.error(f"Error logging backup access: {str(e)}")


def log_restore_access(user, restore_job, action, details=None):
    """
    Log access to restore jobs for audit purposes.
    """
    try:
        with transaction.atomic():
            AuditLog.objects.create(
                user=user,
                tenant=user.tenant,
                action=f"restore_{action}",
                object_type='restore_job',
                object_id=restore_job.pk,
                object_repr=str(restore_job),
                details=details or f"User {user.email} {action} restore job {restore_job.name}",
                ip_address=get_client_ip(user),
                timestamp=timezone.now()
            )
    except Exception as e:
        logger.error(f"Error logging restore access: {str(e)}")


def log_schedule_access(user, schedule, action, details=None):
    """
    Log access to backup schedules for audit purposes.
    """
    try:
        with transaction.atomic():
            AuditLog.objects.create(
                user=user,
                tenant=user.tenant,
                action=f"schedule_{action}",
                object_type='backup_schedule',
                object_id=schedule.pk,
                object_repr=str(schedule),
                details=details or f"User {user.email} {action} backup schedule {schedule.name}",
                ip_address=get_client_ip(user),
                timestamp=timezone.now()
            )
    except Exception as e:
        logger.error(f"Error logging schedule access: {str(e)}")


def get_client_ip(user):
    """
    Get the client IP address for the current request.
    """
    try:
        # Try to get from request thread local
        from threading import current_thread
        
        request = getattr(current_thread(), 'request', None)
        if request:
            # Get IP from request
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
            
            return ip
    except Exception:
        pass
    
    return None


def require_backup_permission(permission):
    """
    Decorator to require specific backup permission.
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required")
            
            # Get backup job from kwargs
            backup_id = kwargs.get('pk') or kwargs.get('backup_id')
            if not backup_id:
                raise PermissionDenied("Backup job ID required")
            
            try:
                backup_job = BackupJob.objects.get(pk=backup_id)
            except BackupJob.DoesNotExist:
                raise PermissionDenied("Backup job not found")
            
            # Check permission
            if not check_backup_permission(request.user, backup_job, permission):
                raise PermissionDenied("Insufficient permissions")
            
            # Log access
            log_backup_access(request.user, backup_job, 'access', 
                          f"Accessed backup job with permission: {permission}")
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def require_restore_permission(permission):
    """
    Decorator to require specific restore permission.
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required")
            
            # Get restore job from kwargs
            restore_id = kwargs.get('pk') or kwargs.get('restore_id')
            if not restore_id:
                raise PermissionDenied("Restore job ID required")
            
            try:
                restore_job = RestoreJob.objects.get(pk=restore_id)
            except RestoreJob.DoesNotExist:
                raise PermissionDenied("Restore job not found")
            
            # Check permission
            if not check_restore_permission(request.user, restore_job, permission):
                raise PermissionDenied("Insufficient permissions")
            
            # Log access
            log_restore_access(request.user, restore_job, 'access', 
                           f"Accessed restore job with permission: {permission}")
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def require_schedule_permission(permission):
    """
    Decorator to require specific schedule permission.
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required")
            
            # Get schedule from kwargs
            schedule_id = kwargs.get('pk') or kwargs.get('schedule_id')
            if not schedule_id:
                raise PermissionDenied("Schedule ID required")
            
            try:
                schedule = BackupSchedule.objects.get(pk=schedule_id)
            except BackupSchedule.DoesNotExist:
                raise PermissionDenied("Backup schedule not found")
            
            # Check permission
            if not check_schedule_permission(request.user, schedule, permission):
                raise PermissionDenied("Insufficient permissions")
            
            # Log access
            log_schedule_access(request.user, schedule, 'access', 
                           f"Accessed backup schedule with permission: {permission}")
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def validate_backup_access(user, backup_job):
    """
    Validate if a user can access a backup job.
    """
    # Check if user is authenticated
    if not user.is_authenticated:
        return False, "Authentication required"
    
    # Check if user belongs to the same tenant
    if backup_job.tenant != user.tenant:
        return False, "Access denied: tenant mismatch"
    
    # Check if user has view permission
    if not user.has_perm(BackupRestorePermissions.VIEW_BACKUP):
        return False, "Access denied: insufficient permissions"
    
    # Check if user is the creator or has admin role
    if backup_job.created_by != user and not user.has_role('Admin'):
        return False, "Access denied: only creator or admin can access"
    
    return True, "Access granted"


def validate_restore_access(user, restore_job):
    """
    Validate if a user can access a restore job.
    """
    # Check if user is authenticated
    if not user.is_authenticated:
        return False, "Authentication required"
    
    # Check if user belongs to the same tenant
    if restore_job.tenant != user.tenant:
        return False, "Access denied: tenant mismatch"
    
    # Check if user has view permission
    if not user.has_perm(BackupRestorePermissions.VIEW_RESTORE):
        return False, "Access denied: insufficient permissions"
    
    # Check if user is the creator or has admin role
    if restore_job.created_by != user and not user.has_role('Admin'):
        return False, "Access denied: only creator or admin can access"
    
    return True, "Access granted"


def validate_schedule_access(user, schedule):
    """
    Validate if a user can access a backup schedule.
    """
    # Check if user is authenticated
    if not user.is_authenticated:
        return False, "Authentication required"
    
    # Check if user belongs to the same tenant
    if schedule.tenant != user.tenant:
        return False, "Access denied: tenant mismatch"
    
    # Check if user has view permission
    if not user.has_perm(BackupRestorePermissions.VIEW_SCHEDULE):
        return False, "Access denied: insufficient permissions"
    
    # Check if user is the creator or has admin role
    if schedule.created_by != user and not user.has_role('Admin'):
        return False, "Access denied: only creator or admin can access"
    
    return True, "Access granted"


def secure_backup_filename(backup_job):
    """
    Generate a secure filename for backup downloads.
    """
    # Use timestamp and backup ID to prevent guessing
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    return f"backup_{backup_job.pk}_{timestamp}.tar.gz"


def secure_restore_filename(restore_job):
    """
    Generate a secure filename for restore operations.
    """
    # Use timestamp and restore ID to prevent guessing
    timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
    return f"restore_{restore_job.pk}_{timestamp}.log"