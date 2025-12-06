from django.db.models.signals import post_save, post_delete, pre_save
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.contrib.auth import get_user_model
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from .models import AuditLog, ActivityLog, SecurityEvent, LoginLog
from .utils import log_audit_event, log_activity, log_security_event, log_login_event, get_client_ip, get_user_agent, AuditContext

User = get_user_model()


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """
    Log successful user login.
    """
    tenant = getattr(user, 'tenant', None)
    if tenant:
        log_login_event(
            tenant=tenant,
            user=user,
            successful=True,
            request=request
        )
        
        # Log activity
        log_activity(
            tenant=tenant,
            user=user,
            activity_type='security_event',
            description=f"User {user.email} logged in successfully",
            request=request
        )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """
    Log user logout.
    """
    if not user:
        return
        
    tenant = getattr(user, 'tenant', None)
    if tenant:
        # Update the login log with logout time
        try:
            login_log = LoginLog.objects.filter(
                tenant=tenant,
                user=user,
                logout_time__isnull=True
            ).latest('login_time')
            login_log.logout_time = timezone.now()
            login_log.save()
        except LoginLog.DoesNotExist:
            pass
        
        # Log activity
        log_activity(
            tenant=tenant,
            user=user,
            activity_type='security_event',
            description=f"User {user.email} logged out",
            request=request
        )


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request, **kwargs):
    """
    Log failed login attempts.
    """
    username = credentials.get('username', '')
    
    # Try to get user and tenant
    try:
        user = User.objects.get(username=username)
        tenant = getattr(user, 'tenant', None)
    except User.DoesNotExist:
        user = None
        tenant = None
    
    # If we can't determine tenant, we can't log it
    if not tenant:
        return
    
    # Log failed login
    log_login_event(
        tenant=tenant,
        user=user,
        successful=False,
        failure_reason="Invalid credentials",
        request=request
    )
    
    # Log security event for failed login
    log_security_event(
        tenant=tenant,
        user=user,
        event_type='failed_login',
        description=f"Failed login attempt for username: {username}",
        severity='low',
        request=request
    )
    
    # Check for multiple failed attempts
    recent_failures = LoginLog.objects.filter(
        tenant=tenant,
        user=user,
        login_successful=False,
        login_time__gte=timezone.now() - timezone.timedelta(minutes=15)
    ).count()
    
    if recent_failures >= 5:
        log_security_event(
            tenant=tenant,
            user=user,
            event_type='multiple_failed_logins',
            description=f"Multiple failed login attempts detected for user: {username}",
            severity='high',
            request=request
        )


@receiver(pre_save)
def track_model_changes_before(sender, instance, **kwargs):
    """
    Store old values before model is updated.
    """
    # Skip if this is a new instance
    if instance._state.adding:
        return
    
    # Skip audit models to avoid infinite recursion
    if sender in [AuditLog, ActivityLog, SecurityEvent, LoginLog]:
        return
    
    # Get tenant from instance
    tenant = getattr(instance, 'tenant', None)
    if not tenant:
        return
    
    # Store old values in instance for post_save to use
    try:
        old_instance = sender.objects.get(pk=instance.pk)
        instance._audit_old_values = {}
        for field in instance._meta.fields:
            instance._audit_old_values[field.name] = getattr(old_instance, field.name)
    except sender.DoesNotExist:
        pass


@receiver(post_save)
def track_model_changes_after(sender, instance, created, **kwargs):
    """
    Track model creation and updates.
    """
    # Skip audit models to avoid infinite recursion
    if sender in [AuditLog, ActivityLog, SecurityEvent, LoginLog]:
        return
    
    # Get tenant from instance
    tenant = getattr(instance, 'tenant', None)
    if not tenant:
        return
    
    # Get current user from context
    user = AuditContext.get_user()
    request = AuditContext.get_request()
    
    action = 'create' if created else 'update'
    
    # Get old and new values
    old_values = getattr(instance, '_audit_old_values', None)
    new_values = {}
    for field in instance._meta.fields:
        new_values[field.name] = getattr(instance, field.name)
    
    # Log the change
    log_audit_event(
        tenant=tenant,
        user=user,
        action=action,
        model_instance=instance,
        old_values=old_values,
        new_values=new_values,
        request=request
    )
    
    # Log activity for important changes
    if created:
        log_activity(
            tenant=tenant,
            user=user,
            activity_type='other',
            description=f"Created new {sender.__name__}: {instance}",
            related_object=instance,
            request=request
        )


@receiver(post_delete)
def track_model_deletion(sender, instance, **kwargs):
    """
    Track model deletions.
    """
    # Skip audit models to avoid infinite recursion
    if sender in [AuditLog, ActivityLog, SecurityEvent, LoginLog]:
        return
    
    # Get tenant from instance
    tenant = getattr(instance, 'tenant', None)
    if not tenant:
        return
    
    # Get current user from context
    user = AuditContext.get_user()
    request = AuditContext.get_request()
    
    # Get old values before deletion
    old_values = {}
    for field in instance._meta.fields:
        old_values[field.name] = getattr(instance, field.name)
    
    # Log the deletion
    log_audit_event(
        tenant=tenant,
        user=user,
        action='delete',
        model_instance=instance,
        old_values=old_values,
        new_values=None,
        request=request
    )
    
    # Log activity for important deletions
    log_activity(
        tenant=tenant,
        user=user,
        activity_type='other',
        description=f"Deleted {sender.__name__}: {instance}",
        request=request
    )


def register_model_for_audit(model):
    """
    Register a model for audit tracking.
    """
    post_save.connect(track_model_changes_after, sender=model, dispatch_uid=f'audit_{model.__name__}_post_save')
    pre_save.connect(track_model_changes_before, sender=model, dispatch_uid=f'audit_{model.__name__}_pre_save')
    post_delete.connect(track_model_deletion, sender=model, dispatch_uid=f'audit_{model.__name__}_post_delete')


def register_models_for_audit(*models):
    """
    Register multiple models for audit tracking.
    """
    for model in models:
        register_model_for_audit(model)


# Auto-register important models
def auto_register_models():
    """
    Automatically register important models for audit tracking.
    """
    from django.apps import apps
    
    # Models to automatically register for auditing
    models_to_register = [
        'clients.Client',
        'cases.Case',
        'documents.Document',
        'billing.Invoice',
        'billing.Payment',
        'billing.TimeEntry',
        'accounts.CustomUser',
        'permissions.TenantPermission',
        'permissions.UserRole',
    ]
    
    for model_path in models_to_register:
        try:
            app_label, model_name = model_path.split('.')
            model = apps.get_model(app_label, model_name)
            register_model_for_audit(model)
        except (LookupError, ValueError):
            # Model doesn't exist, skip it
            pass