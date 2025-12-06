"""
Tenant Rate Limiting Middleware
Implements Feature #14 from todo.md: Rate Limiting per Tenant
"""
from django.http import HttpResponse, JsonResponse
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import hashlib


class TenantRateLimitMiddleware:
    """
    Rate limit requests per tenant based on their subscription plan.
    Uses Redis cache for distributed rate limiting.
    """
    
    # Default rate limits per plan (requests per hour)
    PLAN_LIMITS = {
        'free': 100,
        'pro': 1000,
        'enterprise': 10000,
        'unlimited': float('inf'),
    }
    
    # Paths to exclude from rate limiting
    EXCLUDED_PATHS = [
        '/static/',
        '/media/',
        '/admin/',
        '/favicon.ico',
        '/__debug__/',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Skip rate limiting for excluded paths
        if self._is_excluded_path(request.path):
            return self.get_response(request)
        
        # Skip if no tenant (public pages)
        if not hasattr(request, 'tenant') or not request.tenant:
            return self.get_response(request)
        
        # Skip for superusers
        if hasattr(request, 'user') and request.user.is_authenticated and request.user.is_superuser:
            return self.get_response(request)
        
        # Get rate limit for tenant's plan
        max_requests = self._get_rate_limit(request.tenant)
        
        if max_requests == float('inf'):
            return self.get_response(request)
        
        # Check rate limit
        cache_key = self._get_cache_key(request)
        request_count = cache.get(cache_key, 0)
        
        if request_count >= max_requests:
            return self._rate_limit_exceeded_response(request, max_requests)
        
        # Increment counter
        cache.set(cache_key, request_count + 1, 3600)  # 1 hour TTL
        
        # Process request
        response = self.get_response(request)
        
        # Add rate limit headers
        response['X-RateLimit-Limit'] = str(int(max_requests))
        response['X-RateLimit-Remaining'] = str(int(max_requests - request_count - 1))
        response['X-RateLimit-Reset'] = str(self._get_reset_time())
        
        return response
    
    def _is_excluded_path(self, path):
        """Check if path should be excluded from rate limiting."""
        return any(path.startswith(excluded) for excluded in self.EXCLUDED_PATHS)
    
    def _get_rate_limit(self, tenant):
        """Get rate limit for tenant based on their plan."""
        plan = getattr(tenant, 'plan', 'free')
        
        # Check if tenant has a subscription with custom limits
        if hasattr(tenant, 'subscription') and tenant.subscription:
            subscription = tenant.subscription
            if hasattr(subscription, 'plan') and subscription.plan:
                plan_obj = subscription.plan
                if hasattr(plan_obj, 'max_requests_per_hour'):
                    return plan_obj.max_requests_per_hour
        
        return self.PLAN_LIMITS.get(plan, self.PLAN_LIMITS['free'])
    
    def _get_cache_key(self, request):
        """Generate cache key for rate limiting."""
        tenant_id = request.tenant.pk
        user_id = request.user.pk if request.user.is_authenticated else 'anonymous'
        
        # Create a unique key per tenant and user
        key_string = f"ratelimit:{tenant_id}:{user_id}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _get_reset_time(self):
        """Get timestamp when rate limit resets."""
        now = timezone.now()
        reset_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        return int(reset_time.timestamp())
    
    def _rate_limit_exceeded_response(self, request, max_requests):
        """Return response when rate limit is exceeded."""
        # Check if it's an AJAX/API request
        if request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'message': f'You have exceeded the rate limit of {int(max_requests)} requests per hour.',
                'retry_after': 3600,
            }, status=429)
        
        # HTML response for regular requests
        return HttpResponse(
            f'''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Rate Limit Exceeded</title>
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
                    h1 {{ color: #e74a3b; }}
                    .container {{ max-width: 600px; margin: 0 auto; }}
                    .btn {{ display: inline-block; padding: 10px 20px; background: #4e73df; color: white; text-decoration: none; border-radius: 5px; margin-top: 20px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>⚠️ Rate Limit Exceeded</h1>
                    <p>You have exceeded the rate limit of <strong>{int(max_requests)}</strong> requests per hour.</p>
                    <p>Please wait a moment before trying again, or upgrade your plan for higher limits.</p>
                    <a href="/pricing/" class="btn">Upgrade Plan</a>
                </div>
            </body>
            </html>
            ''',
            status=429,
            content_type='text/html'
        )


class APIRateLimitMiddleware:
    """
    Separate rate limiting for API endpoints with stricter limits.
    """
    
    API_PLAN_LIMITS = {
        'free': 50,
        'pro': 500,
        'enterprise': 5000,
    }
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Only apply to API paths
        if not request.path.startswith('/api/'):
            return self.get_response(request)
        
        if not hasattr(request, 'tenant') or not request.tenant:
            return self.get_response(request)
        
        # Get API rate limit
        plan = getattr(request.tenant, 'plan', 'free')
        max_requests = self.API_PLAN_LIMITS.get(plan, self.API_PLAN_LIMITS['free'])
        
        # Check rate limit
        cache_key = f"api_ratelimit:{request.tenant.pk}"
        request_count = cache.get(cache_key, 0)
        
        if request_count >= max_requests:
            return JsonResponse({
                'error': 'API rate limit exceeded',
                'message': f'API limit of {max_requests} requests per hour exceeded.',
                'retry_after': 3600,
            }, status=429)
        
        # Increment counter
        cache.set(cache_key, request_count + 1, 3600)
        
        response = self.get_response(request)
        
        # Add API rate limit headers
        response['X-API-RateLimit-Limit'] = str(max_requests)
        response['X-API-RateLimit-Remaining'] = str(max_requests - request_count - 1)
        
        return response
