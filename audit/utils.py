import json
import decimal
from functools import wraps
from contextlib import contextmanager
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.http import HttpRequest
from .models import AuditLog, ActivityLog, SecurityEvent, LoginLog


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects and model instances."""
    def default(self, o):
        # Handle datetime objects
        if hasattr(o, 'isoformat'):
            return o.isoformat()
        # Handle ImageFieldFile and FileField objects - skip serialization entirely
        # to avoid issues with empty file fields
        if hasattr(o, '__class__') and o.__class__.__name__ in ['ImageFieldFile', 'FileField']:
            return ''
        # Handle Decimal objects
        if isinstance(o, decimal.Decimal):
            return float(o)
        # Handle UUID objects
        if hasattr(o, 'hex'):
            return str(o)
        # Handle model instances
        if hasattr(o, '_meta'):
            return str(o)
        return super().default(o)


def get_client_ip(request):
    """
    Extract client IP address from request, considering proxies.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """
    Extract user agent from request.
    """
    return request.META.get('HTTP_USER_AGENT', '')


def get_request_info(request):
    """
    Extract common request information for logging.
    """
    return {
        'ip_address': get_client_ip(request),
        'user_agent': get_user_agent(request),
        'request_path': request.path,
        'request_method': request.method,
        'session_key': request.session.session_key if hasattr(request, 'session') else None,
    }


def log_audit_event(tenant, user, action, model_instance=None, old_values=None, 
                   new_values=None, request=None, **kwargs):
    """
    Create an audit log entry.
    """
    if not tenant:
        return None
    
    # Prepare data
    model_name = ''
    object_id = None
    object_repr = ''
    content_type = None
    
    if model_instance:
        model_name = model_instance.__class__.__name__
        object_id = str(model_instance.pk)
        object_repr = str(model_instance)
        content_type = ContentType.objects.get_for_model(model_instance)
    
    # Calculate changed fields
    changed_fields = []
    if old_values and new_values:
        changed_fields = [field for field in new_values.keys() 
                         if field in old_values and old_values[field] != new_values[field]]
    
    # Get request info
    request_info = {}
    if request:
        request_info = get_request_info(request)
    
    # Create audit log
    audit_log = AuditLog.objects.create(
        tenant=tenant,
        user=user,
        action=action,
        model_name=model_name,
        object_id=object_id,
        object_repr=object_repr,
        content_type=content_type,
        old_values=json.dumps(old_values, cls=DateTimeEncoder) if old_values else None,
        new_values=json.dumps(new_values, cls=DateTimeEncoder) if new_values else None,
        changed_fields=changed_fields,
        **request_info,
        **kwargs
    )
    
    return audit_log


def log_activity(tenant, user, activity_type, description, related_object=None, 
                request=None, **kwargs):
    """
    Create an activity log entry.
    """
    if not tenant:
        return None
    
    # Prepare related object data
    related_content_type = None
    related_object_id = None
    
    if related_object:
        related_content_type = ContentType.objects.get_for_model(related_object)
        related_object_id = str(related_object.pk)
    
    # Get request info
    request_info = {}
    if request:
        request_info = {
            'ip_address': get_client_ip(request),
            'user_agent': get_user_agent(request),
            'request_path': request.path,
        }
    
    # Create activity log
    activity_log = ActivityLog.objects.create(
        tenant=tenant,
        user=user,
        activity_type=activity_type,
        description=description,
        related_content_type=related_content_type,
        related_object_id=related_object_id,
        **request_info,
        **kwargs
    )
    
    return activity_log


def log_security_event(tenant, user, event_type, description, severity='medium', 
                      request=None, **kwargs):
    """
    Create a security event entry.
    """
    if not tenant:
        return None
    
    # Get request info
    request_info = {}
    if request:
        request_info = {
            'source_ip': get_client_ip(request),
            'user_agent': get_user_agent(request),
            'request_path': request.path,
            'request_method': request.method,
        }
    
    # Create security event
    security_event = SecurityEvent.objects.create(
        tenant=tenant,
        user=user,
        event_type=event_type,
        description=description,
        severity=severity,
        **request_info,
        **kwargs
    )
    
    return security_event


def log_login_event(tenant, user, successful=True, failure_reason=None, request=None):
    """
    Create a login log entry.
    """
    if not tenant:
        return None
    
    # Get request info
    request_info = {}
    if request:
        request_info = {
            'ip_address': get_client_ip(request),
            'user_agent': get_user_agent(request),
            'session_key': request.session.session_key if hasattr(request, 'session') else None,
        }
    
    # Create login log
    login_log = LoginLog.objects.create(
        tenant=tenant,
        user=user,
        login_successful=successful,
        failure_reason=failure_reason,
        **request_info
    )
    
    return login_log


def audit_action(action, model_name=None):
    """
    Decorator to automatically log actions.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Try to extract request and tenant from arguments
            request = None
            tenant = None
            user = None
            
            # Check if first argument is a view with request
            if args and hasattr(args[0], 'request'):
                request = args[0].request
                tenant = getattr(request, 'tenant', None)
                user = request.user if request.user.is_authenticated else None
            elif args and isinstance(args[0], HttpRequest):
                request = args[0]
                tenant = getattr(request, 'tenant', None)
                user = request.user if request.user.is_authenticated else None
            
            # Get old values if we have a model instance
            old_values = None
            if args and len(args) > 1 and hasattr(args[1], '__dict__'):
                instance = args[1]
                if hasattr(instance, '_state') and instance._state.adding is False:
                    # This is an update, get old values
                    old_values = {}
                    for field in instance._meta.fields:
                        old_values[field.name] = getattr(instance, field.name)
            
            # Execute the function
            result = func(*args, **kwargs)
            
            # Get new values if we have a model instance
            new_values = None
            model_instance = None
            if args and len(args) > 1 and hasattr(args[1], '__dict__'):
                model_instance = args[1]
                new_values = {}
                for field in model_instance._meta.fields:
                    new_values[field.name] = getattr(model_instance, field.name)
            
            # Log the action
            if tenant:
                log_audit_event(
                    tenant=tenant,
                    user=user,
                    action=action,
                    model_instance=model_instance,
                    old_values=json.dumps(old_values, cls=DateTimeEncoder) if old_values else None,
                    new_values=json.dumps(new_values, cls=DateTimeEncoder) if new_values else None,
                    request=request
                )
            
            return result
        return wrapper
    return decorator


@contextmanager
def audit_context(tenant, user, action, model_instance=None, request=None):
    """
    Context manager for auditing operations.
    """
    if not tenant:
        yield
        return
    
    # Get old values if we have a model instance
    old_values = None
    if model_instance and hasattr(model_instance, '_state') and model_instance._state.adding is False:
        old_values = {}
        for field in model_instance._meta.fields:
            old_values[field.name] = getattr(model_instance, field.name)
    
    try:
        yield
        # Get new values after the operation
        new_values = None
        if model_instance:
            new_values = {}
            for field in model_instance._meta.fields:
                new_values[field.name] = getattr(model_instance, field.name)
        
        # Log the successful operation
        log_audit_event(
            tenant=tenant,
            user=user,
            action=action,
            model_instance=model_instance,
            old_values=json.dumps(old_values, cls=DateTimeEncoder) if old_values else None,
            new_values=json.dumps(new_values, cls=DateTimeEncoder) if new_values else None,
            request=request
        )
    except Exception as e:
        # Log the failed operation
        log_audit_event(
            tenant=tenant,
            user=user,
            action=f"{action}_failed",
            model_instance=model_instance,
            old_values=json.dumps(old_values, cls=DateTimeEncoder) if old_values else None,
            new_values=None,
            request=request,
            additional_data={'error': str(e)}
        )
        raise


def track_model_changes(sender, instance, created, **kwargs):
    """
    Signal handler to track model changes.
    """
    # Get tenant and user from the instance if available
    tenant = getattr(instance, 'tenant', None)
    user = None  # We'll need to get this from thread-local storage or middleware
    
    if not tenant:
        return
    
    action = 'create' if created else 'update'
    
    # For updates, we need to get the old values
    old_values = None
    if not created:
        # This is a simplified approach - in a real implementation,
        # you'd want to store the old values before the update
        pass
    
    # Get new values
    new_values = {}
    for field in instance._meta.fields:
        # Skip file fields as they can't be serialized
        if field.__class__.__name__ in ['ImageFieldFile', 'FileField']:
            continue
        new_values[field.name] = getattr(instance, field.name)
    
    # Log the change
    log_audit_event(
        tenant=tenant,
        user=user,
        action=action,
        model_instance=instance,
        old_values=json.dumps(old_values, cls=DateTimeEncoder) if old_values else None,
        new_values=json.dumps(new_values, cls=DateTimeEncoder)
    )


def track_model_deletion(sender, instance, **kwargs):
    """
    Signal handler to track model deletions.
    """
    # Get tenant from the instance if available
    tenant = getattr(instance, 'tenant', None)
    user = None  # We'll need to get this from thread-local storage or middleware
    
    if not tenant:
        return
    
    # Get current values before deletion
    old_values = {}
    for field in instance._meta.fields:
        old_values[field.name] = getattr(instance, field.name)
    
    # Log the deletion
    log_audit_event(
        tenant=tenant,
        user=user,
        action='delete',
        model_instance=instance,
        old_values=json.dumps(old_values, cls=DateTimeEncoder),
        new_values=None
    )


class AuditContext:
    """
    Thread-local storage for audit context.
    """
    _context = {}
    
    @classmethod
    def set_user(cls, user):
        cls._context['user'] = user
    
    @classmethod
    def get_user(cls):
        return cls._context.get('user')
    
    @classmethod
    def set_tenant(cls, tenant):
        cls._context['tenant'] = tenant
    
    @classmethod
    def get_tenant(cls):
        return cls._context.get('tenant')
    
    @classmethod
    def set_request(cls, request):
        cls._context['request'] = request
    
    @classmethod
    def get_request(cls):
        return cls._context.get('request')
    
    @classmethod
    def clear(cls):
        cls._context.clear()


def get_current_user():
    """
    Get the current user from audit context.
    """
    return AuditContext.get_user()


def get_current_tenant():
    """
    Get the current tenant from audit context.
    """
    return AuditContext.get_tenant()


def get_current_request():
    """
    Get the current request from audit context.
    """
    return AuditContext.get_request()