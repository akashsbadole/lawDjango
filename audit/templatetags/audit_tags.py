from django import template
from django.utils import timezone
from datetime import timedelta
from audit.models import AuditLog, ActivityLog, SecurityEvent, LoginLog


register = template.Library()


@register.simple_tag
def get_audit_stats(tenant):
    """
    Get audit statistics for the dashboard.
    """
    if not tenant:
        return {}
    
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)
    
    # Basic counts
    total_audit_logs = AuditLog.objects.filter(tenant=tenant).count()
    total_activities = ActivityLog.objects.filter(tenant=tenant).count()
    total_security_events = SecurityEvent.objects.filter(tenant=tenant).count()
    unresolved_security_events = SecurityEvent.objects.filter(
        tenant=tenant, resolved=False
    ).count()
    
    # Recent counts (last 24 hours)
    recent_audit_logs = AuditLog.objects.filter(
        tenant=tenant, timestamp__gte=last_24h
    ).count()
    recent_activities = ActivityLog.objects.filter(
        tenant=tenant, timestamp__gte=last_24h
    ).count()
    recent_security_events = SecurityEvent.objects.filter(
        tenant=tenant, timestamp__gte=last_24h
    ).count()
    
    # Failed logins (last 7 days)
    failed_logins = LoginLog.objects.filter(
        tenant=tenant, login_successful=False, login_time__gte=last_7d
    ).count()
    
    return {
        'total_audit_logs': total_audit_logs,
        'total_activities': total_activities,
        'total_security_events': total_security_events,
        'unresolved_security_events': unresolved_security_events,
        'recent_audit_logs': recent_audit_logs,
        'recent_activities': recent_activities,
        'recent_security_events': recent_security_events,
        'failed_logins': failed_logins,
    }


@register.simple_tag
def get_security_severity_badge(severity):
    """
    Get Bootstrap badge class for security event severity.
    """
    severity_classes = {
        'low': 'badge-secondary',
        'medium': 'badge-warning',
        'high': 'badge-danger',
        'critical': 'badge-dark',
    }
    return severity_classes.get(severity, 'badge-secondary')


@register.simple_tag
def get_action_badge(action):
    """
    Get Bootstrap badge class for audit action.
    """
    action_classes = {
        'create': 'badge-success',
        'update': 'badge-info',
        'delete': 'badge-danger',
        'view': 'badge-primary',
        'login': 'badge-success',
        'logout': 'badge-secondary',
        'export': 'badge-warning',
        'import': 'badge-info',
        'approve': 'badge-success',
        'reject': 'badge-danger',
    }
    return action_classes.get(action, 'badge-secondary')


@register.simple_tag
def get_activity_icon(activity_type):
    """
    Get icon class for activity type.
    """
    icon_classes = {
        'document_access': 'fas fa-file-alt',
        'case_view': 'fas fa-briefcase',
        'client_view': 'fas fa-users',
        'billing_action': 'fas fa-dollar-sign',
        'permission_change': 'fas fa-key',
        'user_management': 'fas fa-user-cog',
        'system_config': 'fas fa-cogs',
        'data_export': 'fas fa-download',
        'report_generation': 'fas fa-chart-bar',
        'security_event': 'fas fa-shield-alt',
        'api_access': 'fas fa-code',
        'bulk_operation': 'fas fa-tasks',
        'search': 'fas fa-search',
        'filter': 'fas fa-filter',
        'other': 'fas fa-circle',
    }
    return icon_classes.get(activity_type, 'fas fa-circle')


@register.simple_tag
def format_duration(duration):
    """
    Format duration in a human-readable way.
    """
    if not duration:
        return 'N/A'
    
    total_seconds = int(duration.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


@register.simple_tag
def get_login_status_icon(successful):
    """
    Get icon for login status.
    """
    return 'fas fa-check-circle text-success' if successful else 'fas fa-times-circle text-danger'


@register.simple_tag
def get_audit_log_changes(audit_log):
    """
    Get formatted changes for audit log.
    """
    if not audit_log.changed_fields:
        return []
    
    changes = []
    for field in audit_log.changed_fields:
        old_value = audit_log.old_values.get(field, '') if audit_log.old_values else ''
        new_value = audit_log.new_values.get(field, '') if audit_log.new_values else ''
        
        # Truncate long values
        if len(str(old_value)) > 100:
            old_value = str(old_value)[:100] + '...'
        if len(str(new_value)) > 100:
            new_value = str(new_value)[:100] + '...'
        
        changes.append({
            'field': field.replace('_', ' ').title(),
            'old_value': old_value,
            'new_value': new_value,
        })
    
    return changes


@register.simple_tag
def get_ip_location_info(ip_address):
    """
    Get basic location info for IP address (placeholder for now).
    """
    # This is a placeholder - in production, you'd use a GeoIP service
    if not ip_address:
        return {'city': 'Unknown', 'country': 'Unknown'}
    
    # Simple IP-based location detection (very basic)
    if ip_address.startswith('127.'):
        return {'city': 'Local', 'country': 'Local'}
    elif ip_address.startswith('192.168.'):
        return {'city': 'Internal', 'country': 'Internal'}
    elif ip_address.startswith('10.'):
        return {'city': 'Internal', 'country': 'Internal'}
    else:
        return {'city': 'External', 'country': 'External'}


@register.simple_tag
def get_user_agent_info(user_agent):
    """
    Get parsed user agent information.
    """
    if not user_agent:
        return {'browser': 'Unknown', 'os': 'Unknown', 'device': 'Unknown'}
    
    # Simple user agent parsing
    ua_lower = user_agent.lower()
    
    # Detect browser
    browser = 'Unknown'
    if 'chrome' in ua_lower:
        browser = 'Chrome'
    elif 'firefox' in ua_lower:
        browser = 'Firefox'
    elif 'safari' in ua_lower and 'chrome' not in ua_lower:
        browser = 'Safari'
    elif 'edge' in ua_lower:
        browser = 'Edge'
    elif 'opera' in ua_lower:
        browser = 'Opera'
    
    # Detect OS
    os = 'Unknown'
    if 'windows' in ua_lower:
        os = 'Windows'
    elif 'mac' in ua_lower:
        os = 'macOS'
    elif 'linux' in ua_lower:
        os = 'Linux'
    elif 'android' in ua_lower:
        os = 'Android'
    elif 'ios' in ua_lower:
        os = 'iOS'
    
    # Detect device type
    device = 'Desktop'
    if 'mobile' in ua_lower:
        device = 'Mobile'
    elif 'tablet' in ua_lower:
        device = 'Tablet'
    
    return {
        'browser': browser,
        'os': os,
        'device': device,
    }


@register.simple_tag
def get_security_event_color(event_type):
    """
    Get color for security event type.
    """
    color_map = {
        'failed_login': '#dc3545',
        'multiple_failed_logins': '#fd7e14',
        'suspicious_activity': '#ffc107',
        'permission_denied': '#6c757d',
        'unauthorized_access': '#e74c3c',
        'data_breach_attempt': '#dc3545',
        'malicious_request': '#dc3545',
        'brute_force_attempt': '#dc3545',
        'session_hijack': '#dc3545',
        'privilege_escalation': '#dc3545',
        'unusual_location': '#fd7e14',
        'unusual_device': '#fd7e14',
        'data_exfiltration': '#dc3545',
        'configuration_change': '#ffc107',
        'security_policy_violation': '#e74c3c',
        'other': '#6c757d',
    }
    return color_map.get(event_type, '#6c757d')


@register.inclusion_tag('audit/pagination.html')
def audit_pagination(page_obj, request=None):
    """
    Render pagination controls for audit pages.
    """
    return {
        'page_obj': page_obj,
        'request': request,
    }


@register.simple_tag
def get_chart_data(tenant, days=30):
    """
    Get data for audit charts.
    """
    if not tenant:
        return {}
    
    end_date = timezone.now()
    start_date = end_date - timedelta(days=days)
    
    # Activity by day
    activity_by_day = []
    for i in range(days):
        day_start = start_date + timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        
        count = ActivityLog.objects.filter(
            tenant=tenant,
            timestamp__gte=day_start,
            timestamp__lt=day_end
        ).count()
        
        activity_by_day.append({
            'date': day_start.date().isoformat(),
            'count': count,
        })
    
    # Security events by severity
    security_by_severity = SecurityEvent.objects.filter(
        tenant=tenant,
        timestamp__gte=start_date,
        timestamp__lte=end_date
    ).values('severity').annotate(count=models.Count('id'))
    
    # Top users by activity
    top_users = ActivityLog.objects.filter(
        tenant=tenant,
        timestamp__gte=start_date,
        timestamp__lte=end_date
    ).values('user__email').annotate(
        count=models.Count('id')
    ).order_by('-count')[:10]
    
    return {
        'activity_by_day': activity_by_day,
        'security_by_severity': list(security_by_severity),
        'top_users': list(top_users),
    }