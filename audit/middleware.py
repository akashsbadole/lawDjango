import time
import logging
from django.utils import timezone
from django.http import JsonResponse
from django.urls import resolve, Resolver404
from django.contrib.auth import get_user_model
from django.db import models
from .models import AuditLog, ActivityLog, SecurityEvent
from .utils import get_client_ip, get_user_agent, AuditContext

User = get_user_model()

logger = logging.getLogger('audit')


class AuditMiddleware:
    """
    Middleware to capture all requests for audit logging.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Store request start time
        start_time = time.time()
        
        # Set audit context
        self._set_audit_context(request)
        
        # Get response
        response = self.get_response(request)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Log the request
        self._log_request(request, response, processing_time)
        
        # Check for suspicious activity
        self._check_suspicious_activity(request, response)
        
        # Clear audit context
        AuditContext.clear()
        
        return response
    
    def _set_audit_context(self, request):
        """
        Set audit context for the current request.
        """
        tenant = getattr(request, 'tenant', None)
        # Safely get user with fallback to None if not available
        user = getattr(request, 'user', None)
        if user and hasattr(user, 'is_authenticated') and user.is_authenticated:
            # User is authenticated
            pass
        else:
            # User is not authenticated or not available
            user = None
        
        AuditContext.set_tenant(tenant)
        AuditContext.set_user(user)
        AuditContext.set_request(request)
    
    def _log_request(self, request, response, processing_time):
        """
        Log the request details.
        """
        tenant = getattr(request, 'tenant', None)
        # Safely get user with fallback to None if not available
        user = getattr(request, 'user', None)
        if user and hasattr(user, 'is_authenticated') and user.is_authenticated:
            # User is authenticated
            pass
        else:
            # User is not authenticated or not available
            user = None
        
        if not tenant:
            return
        
        # Skip certain paths
        skip_paths = [
            '/static/',
            '/media/',
            '/favicon.ico',
            '/health/',
            '/ping/',
        ]
        
        if any(request.path.startswith(path) for path in skip_paths):
            return
        
        # Log API requests separately
        if request.path.startswith('/api/'):
            self._log_api_request(request, response, processing_time)
        else:
            self._log_page_request(request, response, processing_time)
    
    def _log_page_request(self, request, response, processing_time):
        """
        Log page requests.
        """
        tenant = getattr(request, 'tenant', None)
        # Safely get user with fallback to None if not available
        user = getattr(request, 'user', None)
        if user and hasattr(user, 'is_authenticated') and user.is_authenticated:
            # User is authenticated
            pass
        else:
            # User is not authenticated or not available
            user = None
        
        if not tenant:
            return
        
        # Determine action based on method and response status
        action = 'view'
        if request.method == 'POST':
            action = 'create'
        elif request.method in ['PUT', 'PATCH']:
            action = 'update'
        elif request.method == 'DELETE':
            action = 'delete'
        
        # Skip successful GET requests to reduce noise
        if request.method == 'GET' and 200 <= response.status_code < 300:
            return
        
        # Log the request
        AuditLog.objects.create(
            tenant=tenant,
            user=user,
            action=action,
            model_name='HTTP Request',
            object_id=request.path,
            object_repr=f"{request.method} {request.path}",
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            session_key=request.session.session_key if hasattr(request, 'session') else None,
            request_path=request.path,
            request_method=request.method,
            additional_data={
                'status_code': response.status_code,
                'processing_time': processing_time,
                'content_type': response.get('Content-Type', ''),
            }
        )
    
    def _log_api_request(self, request, response, processing_time):
        """
        Log API requests with additional details.
        """
        tenant = getattr(request, 'tenant', None)
        # Safely get user with fallback to None if not available
        user = getattr(request, 'user', None)
        if user and hasattr(user, 'is_authenticated') and user.is_authenticated:
            # User is authenticated
            pass
        else:
            # User is not authenticated or not available
            user = None
        
        if not tenant:
            return
        
        # Log API access
        ActivityLog.objects.create(
            tenant=tenant,
            user=user,
            activity_type='api_access',
            description=f"API {request.method} request to {request.path}",
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
            request_path=request.path,
            metadata={
                'method': request.method,
                'status_code': response.status_code,
                'processing_time': processing_time,
                'content_type': response.get('Content-Type', ''),
                'is_json': response.get('Content-Type', '').startswith('application/json'),
            }
        )
    
    def _check_suspicious_activity(self, request, response):
        """
        Check for suspicious activity patterns.
        """
        tenant = getattr(request, 'tenant', None)
        # Safely get user with fallback to None if not available
        user = getattr(request, 'user', None)
        if user and hasattr(user, 'is_authenticated') and user.is_authenticated:
            # User is authenticated
            pass
        else:
            # User is not authenticated or not available
            user = None
        
        if not tenant:
            return
        
        ip_address = get_client_ip(request)
        
        # Check for too many requests from same IP
        self._check_rate_limit(request, tenant, ip_address)
        
        # Check for suspicious user agents
        self._check_user_agent(request, tenant, ip_address)
        
        # Check for unusual access patterns
        self._check_access_patterns(request, tenant, user, ip_address)
        
        # Check for permission violations
        if response.status_code == 403:
            self._log_permission_denied(request, tenant, user, ip_address)
    
    def _check_rate_limit(self, request, tenant, ip_address):
        """
        Check for rate limit violations.
        """
        # Count requests in the last minute
        one_minute_ago = timezone.now() - timezone.timedelta(minutes=1)
        recent_requests = AuditLog.objects.filter(
            tenant=tenant,
            ip_address=ip_address,
            timestamp__gte=one_minute_ago
        ).count()
        
        # If more than 100 requests in a minute, flag as suspicious
        if recent_requests > 100:
            SecurityEvent.objects.create(
                tenant=tenant,
                user=getattr(request, 'user', None),
                event_type='suspicious_activity',
                description=f"High rate of requests from IP {ip_address}: {recent_requests} requests in last minute",
                severity='medium',
                source_ip=ip_address,
                user_agent=get_user_agent(request),
                request_path=request.path,
                request_method=request.method,
                event_data={
                    'requests_per_minute': recent_requests,
                    'threshold': 100,
                }
            )
    
    def _check_user_agent(self, request, tenant, ip_address):
        """
        Check for suspicious user agents.
        """
        user_agent = get_user_agent(request)
        
        # Common patterns for bots/scanners
        suspicious_patterns = [
            'sqlmap',
            'nikto',
            'nmap',
            'masscan',
            'zap',
            'burp',
            'scanner',
            'crawler',
            'bot',
        ]
        
        user_agent_lower = user_agent.lower()
        if any(pattern in user_agent_lower for pattern in suspicious_patterns):
            SecurityEvent.objects.create(
                tenant=tenant,
                user=getattr(request, 'user', None),
                event_type='suspicious_activity',
                description=f"Suspicious user agent detected: {user_agent}",
                severity='low',
                source_ip=ip_address,
                user_agent=user_agent,
                request_path=request.path,
                request_method=request.method,
            )
    
    def _check_access_patterns(self, request, tenant, user, ip_address):
        """
        Check for unusual access patterns.
        """
        if not user:
            return
        
        # Check for access from unusual locations
        # This is a simplified version - in production, you'd use a geoIP service
        recent_ips = AuditLog.objects.filter(
            tenant=tenant,
            user=user,
            timestamp__gte=timezone.now() - timezone.timedelta(days=7)
        ).values_list('ip_address', flat=True).distinct()
        
        # If user has accessed from more than 5 different IPs in a week, flag it
        if len(recent_ips) > 5:
            SecurityEvent.objects.create(
                tenant=tenant,
                user=user,
                event_type='unusual_location',
                description=f"User accessed from multiple IPs: {len(recent_ips)} different IPs in last week",
                severity='medium',
                source_ip=ip_address,
                user_agent=get_user_agent(request),
                request_path=request.path,
                request_method=request.method,
                event_data={
                    'recent_ips': list(recent_ips),
                    'ip_count': len(recent_ips),
                }
            )
    
    def _log_permission_denied(self, request, tenant, user, ip_address):
        """
        Log permission denied events.
        """
        try:
            # Try to resolve the URL to get more context
            try:
                resolved = resolve(request.path)
                view_name = resolved.view_name
            except Resolver404:
                view_name = "Unknown"
            
            SecurityEvent.objects.create(
                tenant=tenant,
                user=user,
                event_type='permission_denied',
                description=f"Permission denied for {view_name}",
                severity='low',
                source_ip=ip_address,
                user_agent=get_user_agent(request),
                request_path=request.path,
                request_method=request.method,
                event_data={
                    'view_name': view_name,
                    'user_agent': get_user_agent(request),
                }
            )
        except Exception as e:
            logger.error(f"Error logging permission denied: {e}")


class SuspiciousActivityDetector:
    """
    Utility class for detecting suspicious activity patterns.
    """
    
    @staticmethod
    def detect_brute_force(tenant, user, ip_address):
        """
        Detect brute force login attempts.
        """
        from .models import LoginLog
        
        # Count failed logins in last hour
        one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
        failed_logins = LoginLog.objects.filter(
            tenant=tenant,
            user=user,
            login_successful=False,
            ip_address=ip_address,
            login_time__gte=one_hour_ago
        ).count()
        
        # If more than 10 failed attempts, flag as brute force
        if failed_logins >= 10:
            SecurityEvent.objects.create(
                tenant=tenant,
                user=user,
                event_type='brute_force_attempt',
                description=f"Brute force attack detected: {failed_logins} failed login attempts in last hour",
                severity='high',
                source_ip=ip_address,
                event_data={
                    'failed_attempts': failed_logins,
                    'timeframe': '1 hour',
                }
            )
            return True
        
        return False
    
    @staticmethod
    def detect_data_exfiltration(tenant, user, request):
        """
        Detect potential data exfiltration patterns.
        """
        # Check for large downloads
        if request.method == 'GET' and 'download' in request.path:
            # Count downloads in last hour
            one_hour_ago = timezone.now() - timezone.timedelta(hours=1)
            downloads = ActivityLog.objects.filter(
                tenant=tenant,
                user=user,
                activity_type='data_export',
                timestamp__gte=one_hour_ago
            ).count()
            
            # If more than 50 downloads in an hour, flag it
            if downloads >= 50:
                SecurityEvent.objects.create(
                    tenant=tenant,
                    user=user,
                    event_type='data_exfiltration',
                    description=f"Potential data exfiltration: {downloads} downloads in last hour",
                    severity='high',
                    source_ip=get_client_ip(request),
                    user_agent=get_user_agent(request),
                    request_path=request.path,
                    event_data={
                        'downloads': downloads,
                        'timeframe': '1 hour',
                    }
                )
                return True
        
        return False
    
    @staticmethod
    def detect_unusual_access_times(tenant, user, request):
        """
        Detect access at unusual times.
        """
        current_hour = timezone.now().hour
        
        # Check if access is outside normal business hours (9 AM - 6 PM)
        if current_hour < 9 or current_hour > 18:
            # Check if this is unusual for this user
            # Get user's typical access hours
            typical_hours = ActivityLog.objects.filter(
                tenant=tenant,
                user=user,
                timestamp__gte=timezone.now() - timezone.timedelta(days=30)
            ).extra(
                select={'hour': "strftime('%%H', timestamp)"}
            ).values('hour').annotate(count=models.Count('id')).order_by('-count')
            
            # If user rarely accesses at this hour, flag it
            if typical_hours and typical_hours[0]['hour'] != str(current_hour):
                SecurityEvent.objects.create(
                    tenant=tenant,
                    user=user,
                    event_type='unusual_access_time',
                    description=f"Unusual access time: {current_hour}:00",
                    severity='low',
                    source_ip=get_client_ip(request),
                    user_agent=get_user_agent(request),
                    request_path=request.path,
                    event_data={
                        'access_hour': current_hour,
                        'typical_hour': typical_hours[0]['hour'] if typical_hours else None,
                    }
                )
                return True
        
        return False