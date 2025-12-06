from django.utils import timezone
from datetime import timedelta
from .models import AuditLog, ActivityLog, SecurityEvent, LoginLog


def audit_context(request):
    """
    Add audit-related context to templates.
    """
    context = {}
    
    # Get tenant from request if available
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        return context
    
    # Get recent audit statistics
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    
    # Recent audit logs
    recent_audit_logs = AuditLog.objects.filter(
        tenant=tenant,
        timestamp__gte=last_24h
    ).select_related('user').order_by('-timestamp')[:5]
    
    # Recent security events (unresolved)
    recent_security_events = SecurityEvent.objects.filter(
        tenant=tenant,
        resolved=False,
        timestamp__gte=last_24h
    ).select_related('user').order_by('-timestamp')[:5]
    
    # Failed login attempts (last 24 hours)
    failed_logins = LoginLog.objects.filter(
        tenant=tenant,
        login_successful=False,
        login_time__gte=last_24h
    ).count()
    
    # Total counts for dashboard
    total_audit_logs = AuditLog.objects.filter(tenant=tenant).count()
    total_security_events = SecurityEvent.objects.filter(tenant=tenant).count()
    unresolved_security_events = SecurityEvent.objects.filter(
        tenant=tenant,
        resolved=False
    ).count()
    
    context.update({
        'audit_stats': {
            'total_audit_logs': total_audit_logs,
            'total_security_events': total_security_events,
            'unresolved_security_events': unresolved_security_events,
            'failed_logins_24h': failed_logins,
            'recent_audit_logs': recent_audit_logs,
            'recent_security_events': recent_security_events,
        }
    })
    
    return context